# Overview

The principle task of this system is to use FUSE-based file systems to mount
S3 buckets as ordinary directories within JupyterHub notebook sessions.
In its initial incarnation it supports both goofys and s3fs-fuse S3
implementations.

# Pt 1 - Mounting S3 as directories on nodes

The fundamental task of the S3 FUSE programs is to make an S3 bucket and/or
prefix to appear to be a directory on a node.  Each node is required to run
each FUSE program being supported so bandwidth automatically scales up as
more nodes are added.

Although it is possible to run FUSE file systems directly within the notebook
containers, doing so requires running the container with elevated root-like
privileges which pose security concerns.  Consequently two alternative
approaches were considered:

1. Mount the S3 file systems directly on nodes where they run as services.

2. Run Daemon pods which mount the S3 file systems and make them visible
   outside the pods to the nodes.

It should be noted that for (2) elevated privileges are still required to
perform the necessary file system mounts inside the daemon containers.
However, the difference is the complexity and accessibility of the container.
The notebook container (a) gives direct access to user inputs and (b) also
contains 13G of development tools, windowing systems, etc.  The FUSE daemonset
container contains only a minimal OS and the file system programs and offers no
direct access to users.  The FUSE Docker image is less than 60M total.

The isolation and simplicity of the FUSE daemonset containers make it safer to
grant the required elevated permissions.  Moreover, running the FUSE programs
directly on the nodes doesn't really offer any improvements in isolation; the
programs still run as root, but also side-by-side with every other service on
the worker nodes.  If anything, an isolated privileged container is safer,
because there is less opportunity for cross-talk with other node services and
their dependencies.

In either case,  the end result of running a FUSE file system is a new
/s3 directory on the node which presents S3 files.

Aside from security parity and/or advantages, running in daemon pods vs.
directly on worker nodes makes it possible to deploy and undeploy using
Kubernetes and Helm instead of ssh and/or Python and/or Terraform.  We also
noted that running directly on nodes would require re-installation following
AMI rotation and hence some alteration to the AMI rotation process.  In
contrast, the containerized approach maintains the generic nature of the nodes
and eliminates the need for changes to Terraform or the AMI rotation code.
Re-deploying a new container or configuration requires a couple minutes, while
re-deploying nodegroups requires 10's of minutes.  Hence,  once implemented,
S3 daemonsets should be easier to maintain.

# Pt 2 - Mounting Node Directories in Notebook Pods

Once S3 is effectively mounted on the worker nodes as ordinary directories,
using either method above, there is an additional task required of passing
those directories into notebook pods.  Whereas Docker can do something similar
with a switch as simple as `-v from:to`, Kubernetes and JupyterHub seem to
require the application of 4 different concepts and specs:

1. StorageClass
2. PersistentVolume
3. PersistentVolumeClaim
4. JupyterHub Helm config

Simply put, it's complicated, as each spec has a minimum of several settings
and there are nuances like "the PVC must be in the same namespace as
JupyterHub."  But however complex relative to Docker bind mounts, we have the
same complexity for either method of attaching S3 to the nodes for Zero-to-JH.

# Workflows

## Deployment

The following high level workflow shows deploying fuse and jupyterhub.

It also shows the reverse process of undeploying.  Because jupyterhub leaves
notebook pods untouched when the hub helm release is uninstalled,
`undeploy-jupyterhub` also deletes all notebook pods in addition to the hub.
Notebook pods are deleted because otherwise they leave dangling references to
the PVC which prevents it and the PV from being deleted during fuse-undeploy.
While possibly not required, deleting the hub prevents additional users from
logging on and adding new references to the PVC.

```
# Update setup-env and infrequent-env as needed

$ deploy-fuse          # top level deployment,  build, push, deploy, status
$ deploy-jupyterhub    # second so PVC exists to mount into notebook pods
$ fuse-check           # run automated checks on fuse s3 resources, functionality

$ undeploy-jupyterhub  # tear down hub and notebook pods dropping all fuse PVC use
$ undeploy-fuse        # tear down all fuse resources, PVC usage = 0
```

## Development

The following commands are used as needed during iterative development:
```
# Change Dockerfile
$ fuse-build              # build Docker image
$ fuse-push               # push Docker image with fuse image tag. vs hub tag

# Change Helm files, etc.
$ fuse-deploy             # Run Helm chart creating daemonsets, storage resources
                          # Note: this is a small fraction of deploy-fuse

# Change hub config
$ deploy-jupyterhub       # Deploy the hub server


# Other useful commands
$ fuse-status             # Dump basics on all fuse resources
$ fuse-check              # Run canned checks such as they are

$ kubectl get pods -n fuse
$ kubectl get daemonsets -n fuse
$ kubectl logs -n fuse <fuse-podname>
$ kubectl describe <resource-kind: pod, daemonset, ...> -n fuse <resource-name>
$ kubectl exec -it -n fuse <fuse-podname> -- command   # use /bin/sh not bash, test commands, etc.

# NOTE:  the PVC is in the default namespace as required by Z2JH,  not fuse

$ helm uninstall -n fuse tike-fuse-dev  # Delete all fuse resources,  opposite of fuse-deploy
```

# How does it work?

Deploying a helm chart creates a new `fuse` namespace and a helm release named
e.g.  `tike-fuse-dev`.  It consists of:

1. A single daemon image.  The Dockerfile defines an image which contains the
FUSE library and both goofys and s3fs-fuse programs.  Both programs fit in <
60M.

2. Two daemonsets: one for goofys, one for fuse.  Each daemonset runs one file
system pod for each bucket on each notebook node.  Hence each notebook node
runs two additional small pods.
```
Generally the path structure is:   /s3/<file system>/<bucket>

stpubdata is mounted as /s3/gf/stpubdata in each goofys daemon pod.

stpubdata is mounted as /s3/fs/stpubdata in each s3fs-fuse daemon pod.
```

3. A local-storage StorageClass represents data which exists directly on a
node's file system.

4. A /s3 PersistentVolume represents the entire /s3 directory tree containing
all s3 file system mounts.

5. A /s3 PersistentVolumeClaim bound ReadOnlyMany to the /s3 pv and mounted on
every notebook pod in JupyterHub config files.  The same pv and pvc are used by
all notebook pods.  Each notebook pod is only configured to mount /s3.

# Organization of the FUSE S3 subsystem

At a high level,  our "fuse" source files really consist of:

1. A Dockerfile
2. A Helm chart
3. Several kubernetes specs
4. Support scripts
5. JupyterHub config

In more detail,  the source is organized like this:
```
jupyterhub-deploy/
  setup-env
  infrequent-env
  fuse/
    bin/
      deploy-fuse        -- zero to deployed tike-fuse-dev Helm release
      fuse-build         -- builds fuse Dockerfile
      fuse-push          -- pushes fuse image
      fuse-deploy        -- installs fuse Helm chart / resources
      fuse-undeploy      -- uinstalls helm chart,  force deletes storage
      fuse-status        -- displays fuse resources
      fuse-check         -- fetches fuse info and runs health assertions
    Dockerfile           -- daemonset image, contains both s3fs and goofys
    helm/
       Chart.yaml
       values.yaml
       templates/
         daemonset-gf.yaml
         daemonset-fs.yaml
         local-storage.yaml
         pv-s3.yaml
         pvc.yaml
         _helpers.tpl
  deployments/
    tike/
      config/
        common.yaml
```

# Source Projects

This effort took inputs from several similar Kubernetes projects on GitHub,
primarily:

## Goofys on Kubernetes

Primary basis for our development,  Dockerfile, Helm, etc.

* [Blog](https://dev.to/otomato_io/mount-s3-objects-to-kubernetes-pods-12f5)
* [GitHub Project](https://github.com/otomato-gh/s3-mounter)

## s3fs-fuse on Kubernetes

Additional nuances like `tini`,  s3fs mount options, etc.

* [Blog](https://icicimov.github.io/blog/virtualization/Kubernetes-shared-storage-with-S3-backend/)

## Our Changes

Using the above as examples and a starting point, I customized it/them for the
following and integrated the result directly with our jupyterhub-deploy repo:

* Modified Dockerfile to install both goofys and s3fs-fuse in same image
* Modified Dockerfile to handle STScI SSL cert requirements
* Modified goofys and s3fs-fuse mount options
* Forked the daemonset spec into two:  one for goofys,  one for s3fs-fuse
* Hardwired /s3/fs/<bucket> and /s3/gf/<bucket> into daemonsets, simplifying params
* Added "tini" to the Dockerfile as an "init" substitute to reap orphans
* Adjusted Helm chart as different project
* Updated values.yaml to reflect changes in parameters
* Removed security resources in favor of implied tike-worker instance role
* Added the k8s storage resources/specs required to mount /s3 inside JupyterHub
* Wrote helper scripts to simplify development and deployment
* Added a deployment checker based on the jupyterhub cluster checker.

# More Information

This presentation compares several FUSE file systems, including goofys and
s3fs-fuse:

http://gaul.org/talks/s3fs-tradeoffs/#16

A few things of note:

1. It echoes the idea that s3fs-fuse may have too many options making it
difficult to know when it is configured correctly.

2. It exposes the reason why s3fs-fuse is ~40x slower than goofys for the task
of listing out s3://stpubdata/hst/public.  While goofys performs a single
S3 operation, s3fs-fuse performs 1 + nOBJs S3 operations needed to support
additional posix details.

3. It indicates goofys has significantly better performance in most situations.

# Observed Errors

This section goes over error messages seen habitually in file system logs.

## Goofys
None

## s3fs-fuse
The default s3fs-fuse log level is `CRIT` so the errors observed below are not
nominally seen.  I did spend half a day trying to track down fixes with Google
and GitHub but despite a few promising leads was not able to fix them.  Since
they're only seen with logging turned up, there's no reason to believe they are
not the norm in many configurations of s3fs.

### Startup IAM perms

During our development using elevated log levels, at mount time we see:
```
2022-04-15T22:57:50.209Z [ERR] curl.cpp:CurlProgress(355): timeout now: 1650063470, curl_times[curl]: 1650063409, readwrite_timeout: 60
2022-04-15T22:57:50.209Z [CURL DBG] * Callback aborted
2022-04-15T22:57:50.209Z [CURL DBG] * Closing connection 0
2022-04-15T22:57:50.209Z [ERR] curl.cpp:RequestPerform(2434): ### CURLE_ABORTED_BY_CALLBACK
2022-04-15T22:57:54.209Z [INF] curl.cpp:RequestPerform(2523): ### retrying...
2022-04-15T22:57:54.209Z [INF]       curl.cpp:RemakeHandle(1969): Retry request. [type=-1][url=http://169.254.169.254/latest/api/token][path=]
2022-04-15T22:57:54.209Z [INF] curl.cpp:RequestPerform(2526): Failed to reset handle and internal data for retrying.
2022-04-15T22:57:54.209Z [ERR] curl.cpp:GetIAMv2ApiToken(2856): Error(-5) occurred, could not get IAMv2 api token.
2022-04-15T22:57:54.209Z [ERR] s3fs_cred.cpp:GetIAMCredentialsURL(334): AWS IMDSv2 token retrieval failed: -5
2022-04-15T22:57:54.209Z [INF] curl_handlerpool.cpp:ReturnHandler(110): Pool full: destroy the oldest handler
```

That appears to happen at least twice until s3fs works out creds based on the
tike-worker role.  With the readwrite_timeout configured in mount options as 20
seconds, it adds a ~40 second latency to file system startup.  The default
timeout added 4 minutes to startup latency making initial deployment and debug
a pain.

Adding `iam_role=tike-worker` vs. `iam_role=auto` to the mount options was not
successful at eliminating this error as some GitHub conversations suggested it
might be.

### Ongoing ERRs

We observed the following on a recurring basis in the error log:
```
[ERR] s3fs.cpp:get_base_exp(2701): marker_xp->nodesetval is empty.
```

Over a modest time period of a few hours with light testing, the above string
was issued roughly 10k times.  Consequently s3fs was deployed with the default
tight lipped log settings out of a desire to avert resource leaks.
