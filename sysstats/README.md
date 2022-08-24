# Sysstats add-on

## Background

The **/proc/** directory also called the *proc file system* contains a hierarchy of special files which represent the current state of the kernel, allowing applications and users to peer into the kernel's view of the system. 

In Kubernetes, a feature gate named **ProcMountType** is required to allow mounting **/proc** from the kubernetes node into the notebook pods, which allows the end user to gather and use this information. This is valuable for performance testing and debugging.  The current state of this feature gate is *alpha* and hence not currently available in AWS EKS. For more information, check [Kubernetes Feature Gates status](https://kubernetes.io/docs/reference/command-line-tools-reference/feature-gates/)

This add-on is an alternative way to provide a somewhat similar feature without enabling the *ProcMountType* feature gate by using the opensource package [sysstats](https://github.com/sysstat/sysstat). 

It works by using the tool **sar** to start collecting system metrics in a temporary folder on the host/worker node every second. This temporary folder is then mounted into the pods, and the **sar** and **sadf** tools are used to query the metrics live from the user pods.

## Requirements


### PV/PVC mount
- A PV/PVC to mount the volume with the collected metrics to the pods
- 

### Worker node
- The [sysstats](https://github.com/sysstat/sysstat) package installed 
- A cronjob added to start the metrics collection
- A second cronjob to clear out old collected stats

### Pods
- The [sysstats](https://github.com/sysstat/sysstat) package installed 

## Implementation

### PV/PVC

Create PV and PVC
```bash
kubectl apply -f sysstats/sysstats-pv-pvc.yml
```

Add the extra volume claim and mount to the deployment config file deployments/*NAME*/config/*SDLC-LEVEL*.yaml

```yaml
jupyterhub:
  singleuser:
    storage:
      extraVolumes:
        - name: systats
          persistentVolumeClaim:
            claimName: task-pv-claim
      extraVolumeMounts:
        - name: systats
          mountPath: /sysstats
          readOnly: true

```

Then run **deploy-jupyterhub** to apply changes into the cluster
 

### Worker node

To install the sysstats package and add the cronjobs for metrics collection and cleanup,the launch template for the worker nodes needs to be updated. Add the following lines to the user data launch template, before the #EKS Start section

```bash
...
#Installing sysstat and adding cronjob to collect per-second metrics daily on /tmp/sysstats folder
sar -o /tmp/sysstats/sysstats-`/bin/date +\%Y-\%m-\%d:\%H:\%M:\%S`.sar 1 & #start collecting at boot in the background
crontask='0 0 * * * if pgrep sar; then pkill sar; fi && sar -o /tmp/sysstats/sysstats-`/bin/date +\%Y-\%m-\%d:\%H:\%M:\%S`.sar 1'
crontab -l | { cat; echo "$crontask"; } | crontab -

#Creating daily clean up job to clear out logs older by 7 days
crontask='1 0 * * * find /tmp/sysstats/ -type f -mtime +7 -name '*.sar' -execdir rm -- '{}' \;'
crontab -l | { cat; echo "$crontask"; } | crontab -

#EKS Start
...
```

After this the nodes will need to be re-instantiated so the launch template scripts are run. There are multiple ways to do this, but setting the EKS desired active worker node group size to 0, then wait for a cuple minutes, and then revert it back to whatever the desired size was seems to work.

## Usage

Login into the notebook pod, and open a terminal session.

The collected metrics are available at the folder **/sysstats/**

To check the node stats from the pod, first convert the file from old sar version to a newer format. There should be a sar file per day, starting with the date the worker node was instantiated. It will maintain files for the last 7 days given that the worker runs for that long. 

```bash
sadf -c /sysstats/[file].sar > stats
```
 

Then use the sar or sadf tools in the notebook to query the data. This [link](https://github.com/sysstat/sysstat) contains examples for the sadf and sar commands along with its different options and units.
 
### Examples

- To check CPU, every 5 second, 20 rows
 
```bash
~$ sar -f stats -u 5 20
Linux 5.4.181-99.354.amzn2.x86_64 (ip-10-143-27-136.ec2.internal)       08/18/2022      _x86_64_        (4 CPU)
03:09:55 PM     CPU     %user     %nice   %system   %iowait    %steal     %idle
03:10:00 PM     all     25.87      0.00      5.02     48.97      0.05     20.09
03:10:05 PM     all     35.80      0.00      7.16     23.03      0.00     34.00
03:10:10 PM     all     30.18      0.00      3.80     15.84      0.05     50.12
03:10:15 PM     all     14.24      0.00      1.86     17.41      0.00     66.48
03:10:20 PM     all      2.75      0.00      2.70     19.63      0.00     74.91
03:10:25 PM     all     39.01      0.00     16.68      5.08      0.00     39.22
03:10:30 PM     all     22.84      0.00     10.14     10.24      0.00     56.78
03:10:35 PM     all      8.56      0.00      3.78      2.22      0.10     85.34
03:10:40 PM     all      2.41      0.00      0.65      0.00      0.00     96.94
03:10:45 PM     all      0.35      0.00      0.40      0.00      0.00     99.25
03:10:50 PM     all      5.58      0.00      3.22      1.21      0.00     89.99
03:10:55 PM     all     53.00      0.00     28.21      7.32      0.00     11.47
03:11:00 PM     all     53.62      0.00     24.85     10.77      0.10     10.66
03:11:05 PM     all     62.37      0.00     29.29      3.07      0.05      5.22
03:11:10 PM     all     13.50      0.00      9.36     37.58      0.00     39.57
03:11:15 PM     all      6.23      0.00      4.87     20.43      0.00     68.47
03:11:20 PM     all      5.14      0.00      4.37     20.96      0.00     69.53
03:11:25 PM     all     14.01      0.00      7.28     29.77      0.00     48.95
03:11:30 PM     all     43.06      0.00     17.07     14.94      0.00     24.92
03:11:35 PM     all     39.94      0.00     18.00     16.78      0.00     25.28
Average:        all     23.83      0.00      9.88     15.27      0.02     51.00
```
 

- To check memory:
 

```bash
~$ sar -f stats -r 1 3
Linux 5.4.181-99.354.amzn2.x86_64 (ip-10-143-27-136.ec2.internal)       08/18/2022      _x86_64_        (4 CPU)
03:09:55 PM kbmemfree   kbavail kbmemused  %memused kbbuffers  kbcached  kbcommit   %commit  kbactive   kbinact   kbdirty
03:09:56 PM  15100608         0    308848      1.93      2704    621648    821912      5.13    391828    429108     87764
03:09:57 PM  15010632         0    380296      2.37      2704    640176   1203600      7.51    460656    447596     87772
03:09:58 PM  14984984         0    390076      2.43      2704    656044   1264536      7.89    471096    463396     87772
Average:     15032075         0    359740      2.24      2704    639289   1096683      6.84    441193    446700     87769
```

- To check network traffic
```bash
~$ sar -f stats -n DEV
03:46:59 PM     IFACE   rxpck/s   txpck/s    rxkB/s    txkB/s   rxcmp/s   txcmp/s  rxmcst/s   %ifutil
03:47:00 PM enief42f0b454b     19.00     17.00      6.50     95.19      0.00      0.00      0.00      0.00
03:47:00 PM enid841ab241b1      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:00 PM eni31be7da6293      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:00 PM enid374a790b73      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:01 PM enief42f0b454b     15.00     21.00      1.31     95.19      0.00      0.00      0.00      0.00
03:47:01 PM enid841ab241b1      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:01 PM eni31be7da6293      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:01 PM enid374a790b73      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:02 PM enief42f0b454b      6.00      6.00     11.34      0.91      0.00      0.00      0.00      0.00
03:47:02 PM enid841ab241b1      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:02 PM eni31be7da6293      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:02 PM enid374a790b73      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:03 PM enief42f0b454b     28.00     22.00      5.21      2.81      0.00      0.00      0.00      0.00
03:47:03 PM enid841ab241b1      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:03 PM eni31be7da6293      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:03 PM enid374a790b73      0.00      0.00      0.00      0.00      0.00      0.00      0.00      0.00
03:47:04 PM enief42f0b454b     32.00     26.00      5.47     96.95      0.00      0.00      0.00      0.00
```
 

- To generate a network interface graphi in SVG format
```bash
sadf -g stats -- -n DEV > index.svg 
```

