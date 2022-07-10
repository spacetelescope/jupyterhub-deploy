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
1. Deploy JupyterHub (deploy-jupyterhub)
2. Deploy DataDog    (deploy-datadog)
3. Deploy EFS Quota Monitoring  (efsq-build, efsq-push,  efsq-deploy)
4. Check EFS Quota Logging (efsq-logs;  random monitor pod)
5. Check EFS Quota Status (efsq-status; dump pod, pv, pvc status)

## EFS Quota System Components

The EFS Quota system has the following broad elements:

1. A `Dockerfile` which builds the image used to monitor and enforce quotas.  This image is used by both monitor and reaper deployments.   Run with a --reaper switch

2. An `efs_quota_monitor.py` program which implements both quota monitoring and reaping using common elements like interacting with the hub API.

3. A `Monitor deployment` which runs du for active users and stale quotas.  As shipped,  it runs 5 pods enabling it to execute 5 du's in parallel which are
coordinated using EFS file locking.  5 copies are used to avoid starving measurements of smaller quotas due to a few large quotas with long running du.
As shipped these try to run every 4 hours and update quotas once a week whether
a user is active or not...  unless quotas are disabled for them.

4. A `Reaper deployment` running one pod which reacts to measurements recorded by
the monitor pods issuing log messages and/or alerts,  and by default killing the server of users in violation of their quota.  The reaper runs every 5 minutes to
ensure timely notebook session kills if login blocking fails for some reason.  Quota events also track user activity on the same 5 minute basis as another metric on user resource consumption.

5. A `/opt/common-scripts/check-quota` program which is run by roman and tike post-startp-hooks to block users who have violated their quota, or by compliant
users to examine their quota status from a terminal window as one way of seeing warnings, unblocked violations, etc.   Blocked users can see their block status in the JH notebook server spawn log.

6. `/efs/users PV and PVC's` make a point at which the EFS quota status can be measured for each user and/or provide a claim under which user $HOME subdirectories can be mounted into notebook pods.  Created by terraform-deploy

7. `/efs/quota-control PV and PVC's` enable the storage, management, and retrieval of EFS quota status files which serve as a poor man's database.  Created by terraform-deploy

8. `DataDog Logging` as-built we have a DataDog log view `EFS Quota Monitors` which is used to view the log output from the Monitor and Reaper pods.  This includes messages for key events which include all the information of the quota control file in a JSON event format.

### User Notification & Lockout

### Maintenance Scripts

## Kubernetes Namespaces

* The EFS quota deployments are in the `efs-quota` namespace.

* Most JupyterHub objects are in the `default` namespace.

* Kubernetes system objects (and EFS CSI support) are in the `kube-system` namespace.

## EFS File System Access

EFS quotas relies on the following directory paths and permissions:

    /efs                A mount of the root of the EFS file system associated with
                         $HOME on the CI-node.
		     
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

