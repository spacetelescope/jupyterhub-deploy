# EFS User Quota Monitoring & Enforcement

## Overview

This subsystem is responsible for monitoring and enforcing the EFS
disk quota associated with each user's $HOME directory.  Because of
the current implementation of EFS, we believe the only method of
determining a user's disk usage is direct measurement,  and relying
on tried-and-true UNIX tech,  we have selected to periodically run
`du` and take appropriate actions.

## Configuration

### Environment

An extra tag definition has been added to setup-env to distinguish
between notebook images and efs quota images:

    export EFSQUOTA_TAG=unscanned-latest-efsquota-${ENVIRONMENT}

### Secrets

The EFS quota system requires a small block of extra configuration in
the hub's secrets file to define a JH service and it's API token:

    hub:
      extraConfig:
          efsquota: |
              c.JupyterHub.services = [
                  {
                  "name" : "efsquota-admin",
                  "api_token" : "<generate with 'openssl rand -hex 32'>"
                  "admin" : True,   # for JupyterHub 1.x
                  },
              ]

The `api_token` field of the config should be generated using using the
UNIX command:

    $ openssl rand -hex 32
    62b9d2b7a66e9195aeb06a81a7d35010247950bbe1b705147cc06ee467ce028e

The extra configuration is needed for EFS quota pods to interact with
the hub API to query for users, their last activity, and when needed
to shut down notebook sessions.

## Deploying / Running

Deploying the efs-quota system should be done in the following order:

0. source setup-env
1. Deploy JupyterHub (deploy-jupyterhub,  etc.)
2. Deploy DataDog    (deploy-datadog, etc.)
3. Deploy EFS Quota Monitoring  (deploy-efsq)
4. Check EFS Quota Logging (efsq-logs;  shows random monitor pod log)
5. Check EFS Quota Status (efsq-status; dump pod, pv, pvc status)

This order is important because the quota s/w relies on polling the JupyterHub API to determine the list of usernames and their last activity,  as well as to evict quota violators.  DataDog plays a key role monitoring EFS Quota operations and/or issuing alerts.

NOTE: if JupyterHub is restarted,  it will not typically restart notebook
servers.

## EFS Quota System Components

The EFS Quota system has the following broad elements:

1. A `Dockerfile` which builds the image used to monitor and enforce quotas.  This image is used by both monitor and reaper deployments.   Run with a --reaper switch

2. An `efs_quota_monitor.py` program which implements both quota monitoring and reaping using common elements like interacting with the hub API.

3. A Helm chart which configures and defines two pod deployments.

4. A `Monitor deployment` which runs du for active users and stale quotas.  As shipped,  it runs 5 pods enabling it to execute 5 du's in parallel which are
coordinated using EFS file locking.  5 copies are used to avoid starving measurements of smaller quotas due to a few large quotas with long running du.
As shipped these try to run every 4 hours and update quotas once a week whether
a user is active or not...  unless quotas are disabled for them.

5. A `Reaper deployment` running one pod which reacts to measurements recorded by
the monitor pods issuing log messages and/or alerts,  and by default killing the server of users in violation of their quota.  The reaper runs every 5 minutes to
ensure timely notebook session kills if login blocking fails for some reason.  Quota events also track user activity on the same 5 minute basis as another metric on user resource consumption.

6. A `/opt/common-scripts/check-quota` program which is run by roman and tike post-startp-hooks during JH notebook server spawning to block users who have violated their quota.  It can also be used by compliant users to examine their quota status from a terminal window as one way of seeing warnings, unblocked violations, etc.   Blocked users can see their block status in the JH notebook server spawn log.

7. `/efs/users PV and PVC's` make a point at which the EFS quota status can be measured for each user and/or provide a claim under which user $HOME subdirectories can be mounted into notebook pods.  Created by terraform-deploy

8. `/efs/quota-control PV and PVC's` enable the storage, management, and retrieval of EFS quota status files which serve as a poor man's database.  Created by terraform-deploy

9. `DataDog Logging` as-built we have a DataDog log view `EFS Quota Monitors` which is used to view the log output from the Monitor and Reaper pods.  This includes messages for key events which include all the information of the quota control file in a JSON event format.

10. `Maintenance Scripts` facilitate deploying, undeploying, redeploying, more generally working with EFS quotas by providing short cuts for common operations and easing the use
of the EFS quota namespace:

        deploy-efsq        builds, pushes, and deploys EFS Quota Monitoring
        efsq-build         build the efsq Docker image
        efsq-push          push the efsq container image
        efsq-deploy        install the efsq Helm release starting the system
        efsq-redeploy      tear down, standup the efsq system,  useful for iterative development
        efsq-first-pod     print the name of the first efs quota pod found
        efsq-exec          exec into the specified/first EFS pod for debug, e.g. check EFS dirs
        efsq-logs          print logs from the specified/first quota pod
        efsq-status        print status of various efsq-related k8s objects,  etc
        efsq-undeploy      uninstall any efsq Helm release
        efsq-api-token     prints the EFS quota JH API token to stdout

Most or all scripts can be called with no parameters.

11. Timing and System Constants

The current parametrizations of the system are fairly arbitrary and may be adjusted as a result of experience and/or requirements definitions:

        DEFAULT_QUOTA_G = 200                      default user quota of 200G bytes
        WARN_FRACTION = 0.8                        default fraction to warn user about quota
        MONITOR_PERIOD_SECS = 3600 * 4             4 hours,  to limit du costs
        REAPER_PERIOD_SECS = 300                   5 min for notebook logouts, record activity
        DU_TIMEOUT_SECS = 3600                     1 hour : 1-1.5T measured before timeout?
        STALE_QUOTA_SECS = 3600 * 24 * 7           7 days
        API_TIMEOUT = 10                           secs for slow JH last activity queries
        NULL_TIME = "0001-01-01T01:01"             empty timestamps
        UNDEFINED_BYTES = -1                       empty quota counts
        TOP_LEVEL_FAIL_WAIT = 60                   1 minute wait between e.g. API fail

These are correct at the time of this writing but the source code, helm charts, and deploy
scripts should be reviewed if/when there is an issue.   Some parameters are hard coded in
helm templates potentially overriding the above as time goes on.


### User Notification & Lockout

* `Lockout` occurs during notebook spawning and may be observed in the spawn log

* `User query quota status` run /opt/common-scripts/check-quota in notebook terminal

* `Alerts` check DataDog,  TBD

## Kubernetes Namespaces

* The EFS quota deployments are in the `efs-quota` namespace.

* Most JupyterHub objects are in the `default` namespace.

* Kubernetes system objects (and EFS CSI support) are in the `kube-system` namespace.

## EFS File System Access

EFS quotas relies on the following directory paths and permissions which are a function of Terraform, CI-node, EFS Quota Helm, and JupyterHub Helm configurations:


    /efs                 Root of the JH EFS file system.                  (r/w)    CI-node
		     
    /efs/users           Subdirectory for user $HOME claims.              (r/w)    CI-node
    /efs/users           Subdirectory for user $HOME claims.              (r/o)    Quota pods
           /<encoded_username>

    /efs/quota-control   Subdirectory for user quota control dirs.        (r/w)    CI-node & Quota pods
           /<encoded_username>/quota.lock
           /<encoded_username>/quota.yaml

    /quota-control/quota.yaml    Quota info for current jovyan user       (r/o)    Single notebook user only

## Kubernetes PV's and PVC's

To support two namespaces, the following EFS PV's and associated PVC's are created:

    NAME                                       CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS   CLAIM                              STORAGECLASS   REASON   AGE
    quota-control-efsq-pv                      2Gi        RWX            Delete           Bound    efs-quota/quota-control-efsq-pvc   efs-sc                  6d1h
    quota-control-jh-pv                        2Gi        RWX            Delete           Bound    default/quota-control-jh-pvc       efs-sc                  6d1h
    users-efsq-pv                              2Gi        RWX            Delete           Bound    efs-quota/users-efsq-pvc           efs-sc                  6d1h
    users-jh-pv                                2Gi        RWX            Delete           Bound    default/users-jh-pvc               efs-sc                  6d1h

Both variations of the same PV refer to the same subdirectory of /efs:

* -jh objects are used by notebook/default pods
* -efsq objects are used by efs-quota pods

The need for multiple similar PV's + PVC's arises from:

* Accessing EFS from both efs-quota and default namespaces.
* A PVC can only be attached to a pod in the same namespace.
* One PV can only be bound to one PVC.


## Quota Control File (quota.yaml)

An example of the current quota control file is shown below:

    actual_bytes: 2469232
    fraction_used: 1.1498257517814636e-05
    last_activity: '2022-08-15T20:52:14.403000'
    lockout_enabled: true
    quota_bytes: 214748364800
    quota_enabled: true
    quota_state: ok
    reaper_time: '2022-08-15T20:52:58.469571'
    started: '2022-08-15T20:27:57.049991'
    stopped: '2022-08-15T20:27:57.527531'
    timed_out: false
    user: jmiller@stsci.edu
    warn_fraction: 0.8

The quota file is used to record, communicate, and manage EFS quota monitoring.

        actual_bytes        total bytes of files in a user's $HOME
        fraction_used       fraction of a user's quota already used, actual_bytes/quota_bytes
        last_activity       time reported by JH API of a user's last activity
        lockout_enabled     if `false`,  violations do not result in lockouts
        quota_bytes         total bytes a user can allocate under $HOME
        quota_enabled       if `false`, user is exempt from monitoring and lockout
        quota_state
            ok              user's $HOME allocations are fine
            nearing-limit   user's $HOME allocations have exceeded their warning threshold
            violation       user's $HOME allocations exceed quota, lockout_enabled=false
            lockout         user's $HOME allocations exceed quota, lockout_enabled=true
            timed-out       du ran too long and was aborted for user, currently warning only
        reaper_time         timestamp Reaper last evaluated user's quota for lockout / reporting
        started             start time for du for user
        stopped             stop time for du for user
        timed_out           if `true`,  last run of du timed_out so quota is stale,  warning
        user                JH user this quota applies to
        warn_fraction       fraction of quota usage at which to warn user,  0 <= x <= 1