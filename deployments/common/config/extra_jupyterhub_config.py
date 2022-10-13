from kubespawner import KubeSpawner
from jupyterhub.utils import exponential_backoff
from functools import partial
from tornado import gen
from kubespawner.objects import make_owner_reference

# Based on kubespawner 1.1.0
class CustomSpawner(KubeSpawner):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def is_pod_running_or_failed(self, pod):
        """
        Check if the given pod is running or failed
        pod must be a dictionary representing a Pod kubernetes API object.
        """
        is_running = (
            pod is not None
            and pod["status"]["phase"] == "Running"
            and pod["status"]["podIP"] is not None
            and "deletionTimestamp" not in pod["metadata"]
            and all([cs["ready"] for cs in pod["status"]["containerStatuses"]])
        )
        # Raise error and stop the spawning process if the pod failed
        # or if one or more of its containers are stuck in a crash loop
        if pod["status"]["phase"] == "Failed":
            raise Exception("Pod status = Failed")
        try:
            if any(
                [
                    (
                        cs["state"]["waiting"]["reason"] == "CrashLoopBackOff"
                        and cs["restartCount"] > 3
                    )
                    for cs in pod["status"]["containerStatuses"]
                ]
            ):
                raise Exception(
                    "One or more containers crashed more than three times in a crash loop"
                )
        except KeyError:
            pass
        return is_running

    async def _start(self):
        """Start the user's pod"""

        # load user options (including profile)
        await self.load_user_options()

        # If we have user_namespaces enabled, create the namespace.
        #  It's fine if it already exists.
        if self.enable_user_namespaces:
            await self._ensure_namespace()

        # record latest event so we don't include old
        # events from previous pods in self.events
        # track by order and name instead of uid
        # so we get events like deletion of a previously stale
        # pod if it's part of this spawn process
        events = self.events
        if events:
            self._last_event = events[-1]["metadata"]["uid"]

        if self.storage_pvc_ensure:
            pvc = self.get_pvc_manifest()

            # If there's a timeout, just let it propagate
            await exponential_backoff(
                partial(
                    self._make_create_pvc_request, pvc, self.k8s_api_request_timeout
                ),
                f"Could not create PVC {self.pvc_name}",
                # Each req should be given k8s_api_request_timeout seconds.
                timeout=self.k8s_api_request_retry_timeout,
            )

        # If we run into a 409 Conflict error, it means a pod with the
        # same name already exists. We stop it, wait for it to stop, and
        # try again. We try 4 times, and if it still fails we give up.
        pod = await self.get_pod_manifest()
        if self.modify_pod_hook:
            pod = await gen.maybe_future(self.modify_pod_hook(self, pod))

        ref_key = "{}/{}".format(self.namespace, self.pod_name)
        # If there's a timeout, just let it propagate
        await exponential_backoff(
            partial(self._make_create_pod_request, pod, self.k8s_api_request_timeout),
            f"Could not create pod {ref_key}",
            timeout=self.k8s_api_request_retry_timeout,
        )

        if self.internal_ssl:
            try:
                # wait for pod to have uid,
                # required for creating owner reference
                await exponential_backoff(
                    lambda: self.pod_has_uid(
                        self.pod_reflector.pods.get(ref_key, None)
                    ),
                    f"pod/{ref_key} does not have a uid!",
                )

                pod = self.pod_reflector.pods[ref_key]
                owner_reference = make_owner_reference(
                    self.pod_name, pod["metadata"]["uid"]
                )

                # internal ssl, create secret object
                secret_manifest = self.get_secret_manifest(owner_reference)
                await exponential_backoff(
                    partial(
                        self._ensure_not_exists, "secret", secret_manifest.metadata.name
                    ),
                    f"Failed to delete secret {secret_manifest.metadata.name}",
                )
                await exponential_backoff(
                    partial(
                        self._make_create_resource_request, "secret", secret_manifest
                    ),
                    f"Failed to create secret {secret_manifest.metadata.name}",
                )

                service_manifest = self.get_service_manifest(owner_reference)
                await exponential_backoff(
                    partial(
                        self._ensure_not_exists,
                        "service",
                        service_manifest.metadata.name,
                    ),
                    f"Failed to delete service {service_manifest.metadata.name}",
                )
                await exponential_backoff(
                    partial(
                        self._make_create_resource_request, "service", service_manifest
                    ),
                    f"Failed to create service {service_manifest.metadata.name}",
                )
            except Exception:
                # cleanup on failure and re-raise
                await self.stop(True)
                raise

        # we need a timeout here even though start itself has a timeout
        # in order for this coroutine to finish at some point.
        # using the same start_timeout here
        # essentially ensures that this timeout should never propagate up
        # because the handler will have stopped waiting after
        # start_timeout, starting from a slightly earlier point.
        try:
            await exponential_backoff(
                lambda: self.is_pod_running_or_failed(
                    self.pod_reflector.pods.get(ref_key, None)
                ),
                "pod %s did not start in %s seconds!" % (ref_key, self.start_timeout),
                timeout=self.start_timeout,
            )
        except TimeoutError:
            if ref_key not in self.pod_reflector.pods:
                # if pod never showed up at all,
                # restart the pod reflector which may have become disconnected.
                self.log.error(
                    "Pod %s never showed up in reflector, restarting pod reflector",
                    ref_key,
                )
                self.log.error("Pods: {}".format(self.pod_reflector.pods))
                self._start_watching_pods(replace=True)
            raise

        pod = self.pod_reflector.pods[ref_key]
        self.pod_id = pod["metadata"]["uid"]
        if self.event_reflector:
            self.log.debug(
                "pod %s events before launch: %s",
                ref_key,
                "\n".join(
                    [
                        "%s [%s] %s"
                        % (
                            event["lastTimestamp"] or event["eventTime"],
                            event["type"],
                            event["message"],
                        )
                        for event in self.events
                    ]
                ),
            )

        return self._get_pod_url(pod)
