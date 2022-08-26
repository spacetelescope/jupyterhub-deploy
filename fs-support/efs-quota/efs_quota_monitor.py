"""General scheme for quota daemons:

The architecture includes two deployments: Monitors and Reaper.

Each monitor periodically runs du and updates the quota control file
for one user at a time.  It nominally runs several copies to prevent
quota control from blocking on a single long running du.

Each active cycle, the monitor daemon rewrites the control file for a
user, updating the usage, timestamps, and output flags.

The reaper periodically loads and interprets the quota-control file,
issuing log messages and when required shutting down a users notebook
server.  Only a single reaper daemon is run.

Users to monitor are found by using the JupyterHub REST API to
download user names last_activity values.

The JH REST API access token is randomly generated and stored in the
JH secrets file.  It is registered with JH as a service token using
some config and passed into the EFS Quota daemons as a parameter.

The monitor daemon locks a file for a particular user prior to
updating quota.  Attempts to acquire a locked lock time out
immediately, skipping over that user.

If a user exceeds their fatal quota their notebook server is deleted
using the REST API.  A program /opt/common-script/check-quota is run
by the JH notebook post-startup-hook scripts to block user logins
based on their quota file mounted as /quota-control/quota.yaml.

Quota control files are created by default and edited by hand on
CI-nodes under /efs/quota-control.

Pod output is captured by DataDog,  laying a foundation for alerts.
"""


import os
import sys
import datetime
import time
import subprocess
import argparse
import traceback
import json

import yaml
import filelock
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# ========================================================================================


DEFAULT_QUOTA_G = 200
WARN_FRACTION = 0.8
PERIOD_SECS = 3600 * 4
DU_TIMEOUT_SECS = 3600
STALE_QUOTA_SECS = 3600 * 24 * 7
API_TIMEOUT = 10
NULL_TIME = "0001-01-01T01:01"
UNDEFINED_BYTES = -1
TOP_LEVEL_FAIL_WAIT = 60

# ========================================================================================


def get_pod_id():
    name = os.environ.get("POD_NAME") or "0"
    return "-".join(name.split("-")[-2:])


class Log:
    def __init__(self, name):
        self.name = name
        self.pod_id = get_pod_id()
        self.environment = os.environ["ENVIRONMENT"].replace("prod", "ops")
        self.deployment = os.environ["DEPLOYMENT_NAME"]

    def log(self, kind, *args, **keys):
        d = dict(keys)
        d["status"] = kind
        d["subsystem"] = self.name
        d["pod_id"] = self.pod_id
        d["timestamp"] = now()
        d["message"] = " ".join([str(arg) for arg in args])
        d["service"] = self.deployment  # e.g. roman
        d["env"] = "dmd-" + self.environment  # e.g. dev, test, ops
        d.update(keys)
        print(json.dumps(d))
        sys.stdout.flush()

    def debug(self, *args, **keys):
        return
        self.log("DEBUG", *args, **keys)

    def info(self, *args, **keys):
        self.log("INFO", *args, **keys)

    def warning(self, *args, **keys):
        self.log("WARN", *args, **keys)

    def error(self, *args, **keys):
        self.log("ERROR", *args, **keys)

    def critical(self, *args, **keys):
        self.log("CRITICAL", *args, **keys)

    def exception(self, exc, *args, **keys):
        keys = dict(keys)
        keys.update(
            {
                "error.stack": traceback.format_exc(),
                "error.message": " ".join([str(arg) for arg in args]),
                "error.kind": exc.__class__.__name__,
                "logger.name": "efs-quota",
                "logger.thread_name": self.pod_id,
            }
        )
        self.error(*args, **keys)


# ========================================================================================


def requests_config():
    """Return a requests configuration including automatic retries."""
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    http = requests.Session()
    http.mount("https://", adapter)
    http.mount("http://", adapter)
    return http


class HubRestApi:
    """Interface for making API requests to the hub to obtain information
    about and to control users.
    """

    def __init__(self, hub_url, api_token, api_cert):
        self.api_url = hub_url + "/hub/api"
        self.api_token = api_token
        self.api_cert = api_cert if api_cert.capitalize() != "False" else False
        self.requests = requests_config()

    def last_activity(self):
        """Query JH REST API and return:

        { username : last_activity_timestamp, ... }
        """
        r = self.requests.get(
            self.api_url + "/users",
            headers={
                "Authorization": f"token {self.api_token}",
            },
            verify=self.api_cert,
            timeout=API_TIMEOUT,
        )
        r.raise_for_status()
        return {user["name"]: trim_time(user["last_activity"]) for user in r.json()}

    def delete_user_server(self, user):
        """Delete user's notebook server,  not account."""
        # user = k8s_encode(user)
        r = self.requests.delete(
            self.api_url + f"/users/{user}/server",
            headers={
                "Authorization": f"token {self.api_token}",
            },
            verify=self.api_cert,
            timeout=API_TIMEOUT,
        )
        r.raise_for_status()


# ========================================================================================


def k8s_encode(name):
    """Encode name such that it makes a suitable k8s label?  Lowercase a-z 0-9 and dash.
    (Mimic JH e-mail username encoding.)
    """
    return name.replace("-", "-2d").replace("@", "-40").replace(".", "-2e")


class QuotaFootprint:
    """Manage file and directory naming, encoding, loading, saving"""

    def __init__(self, user, home_root, control_root):
        self.user = user
        self.monitored_home = f"{home_root}/{k8s_encode(user)}"
        self.quota_file = f"{control_root}/{k8s_encode(user)}/quota.yaml"
        self.lock_file = f"{control_root}/{k8s_encode(user)}/quota.lock"

    def save(self, qdata):
        os.makedirs(os.path.dirname(self.quota_file), 0o755, exist_ok=True)
        with open(self.quota_file, "w+") as file:
            file.write(str(qdata))

    def load(self, quota_file=None):
        quota_file = quota_file or self.quota_file
        with open(quota_file) as file:
            qdata = QuotaData(self.user)
            qdata.__dict__.update(yaml.safe_load(file))
        return qdata


class QuotaData:
    """Manage quota values, times, and flags.   Handle du measurement."""

    def __init__(self, user, quota_g=DEFAULT_QUOTA_G, warn_fraction=WARN_FRACTION):
        self.user = user
        self.quota_bytes = int(quota_g * 2**30)
        self.actual_bytes = UNDEFINED_BYTES
        self.fraction_used = 0
        self.warn_fraction = warn_fraction
        self.quota_enabled = True
        self.lockout_enabled = True
        self.last_activity = NULL_TIME
        self.reaper_time = NULL_TIME
        self.active_at_reap = 0
        self.started = NULL_TIME
        self.stopped = NULL_TIME
        self.quota_state = "ok"  # nearing-limit, violation, timed-out, lockout
        self.timed_out = False

    def __str__(self):
        return yaml.dump(self.__dict__)

    def json(self):
        return json.dumps(self.__dict__)

    @property
    def attrs(self):
        return dict(self.__dict__)

    @property
    def f_actual_bytes(self):
        return human_format_number(self.actual_bytes)

    @property
    def f_quota_bytes(self):
        return human_format_number(self.quota_bytes)

    def measure_usage(self, footprint, du_timeout_secs):
        self.started = now()
        footprint.save(self)
        self.timed_out = False
        try:
            self.actual_bytes = du(footprint.monitored_home, du_timeout_secs)
        except subprocess.TimeoutExpired:
            self.timed_out = True
        self.stopped = now()
        self.check()
        footprint.save(self)

    def check(self):
        self.fraction_used = self.actual_bytes / self.quota_bytes
        if self.actual_bytes > self.quota_bytes:
            self.quota_state = "lockout" if self.lockout_enabled else "violation"
        elif self.timed_out:
            self.quota_state = "timed-out"
        elif self.actual_bytes > self.quota_bytes * self.warn_fraction:
            self.quota_state = "nearing-limit"
        else:
            self.quota_state = "ok"

    def stale(self, last_activity, stale_quota_secs):
        """If a quota hasn't been updated in a certain period,  it is stale
        and should probably be re-measured whether active or not.
        """
        return (
            dt_from_iso(last_activity) - dt_from_iso(self.started)
        ).seconds > stale_quota_secs

    def never_measured(self):
        return self.actual_bytes == UNDEFINED_BYTES or self.started == NULL_TIME


# ========================================================================================


class QuotaDaemon:
    def __init__(
        self,
        hub_url,
        api_token,
        api_cert,
        control_root,
        home_root,
        period_secs,
        stale_quota_secs,
        du_timeout_secs,
    ):
        self.hub_api = HubRestApi(hub_url, api_token, api_cert)
        self.log = Log(self.name)
        self.control_root = control_root
        self.home_root = home_root if not home_root.startswith("'") else home_root[1:-1]
        self.period_secs = period_secs
        self.stale_quota_secs = stale_quota_secs
        self.du_timeout_secs = du_timeout_secs

    def main(self):
        self.log.debug("========>", "Daemon startup.")
        while True:
            try:
                start = dt_now()
                self.monitor_active_users()
                stop = dt_now()
                self.log.debug("Elapsed time all users:", (stop - start))
                delay = self.period_secs - (stop - start).seconds
                if delay > 0:
                    self.log.info(
                        f"Waiting {delay} seconds for next {self.name} cycle."
                    )
                    time.sleep(delay)
                else:
                    self.log.warning(
                        f"Monitor cycle is {-delay} seconds too slow to sample every {self.period_secs}."
                        "  Slow sampling may be mitigated by multiple monitors or few outlying users."
                    )
            except Exception as exc:
                self.log.exception(exc, "EXCEPTION: Quota checking top level failure.")
                time.sleep(TOP_LEVEL_FAIL_WAIT)

    def monitor_active_users(self):
        self.log.debug(
            "=========>",
            "Searching for active users at REST API:",
            self.hub_api.api_url,
        )
        for user, last_activity in self.hub_api.last_activity().items():
            self.monitor_user(user, last_activity)

    def monitor_user(self, user, last_activity):
        try:
            self.log.debug(
                "--------> Hub API found user", user, " : last activity", last_activity
            )
            footprint = QuotaFootprint(user, self.home_root, self.control_root)
            os.makedirs(os.path.dirname(footprint.lock_file), 0o755, exist_ok=True)
            lock = filelock.FileLock(footprint.lock_file)
            with lock.acquire(blocking=False):
                self.operate_on_user(user, last_activity, footprint)
        except filelock.Timeout:
            self.log.debug(
                "Skipping", user, "since it is already locked for monitoring."
            )
        except Exception as exc:
            self.log.exception(
                exc, f"EXCEPTION: Quota processing failed for user {user}."
            )
            # no extra wait here


class QuotaMonitorDaemon(QuotaDaemon):

    name = "Monitor"

    def operate_on_user(self, user, last_activity, footprint):
        logger = self.log.warning if last_activity != NULL_TIME else self.log.info
        if not os.path.exists(footprint.monitored_home):
            logger(
                f"User {user} home dir {footprint.monitored_home} does not exist.  Skipping."
            )
            return
        if not os.path.exists(footprint.quota_file):
            self.log.info("Initializing quota for user", user)
            quota = QuotaData(user)
        else:
            self.log.debug("Loading quota status for user", user)
            quota = footprint.load()
        quota.last_activity = last_activity
        footprint.save(quota)
        if not quota.quota_enabled:
            self.log.info("Quota monitoring for user", user, "is disabled.  Skipping.")
            return
        if not (
            last_activity > quota.stopped  # active since last ran du
            or quota.stale(now(), self.stale_quota_secs)
            or quota.never_measured()
        ):
            self.log.info("User", user, "quota sufficiently recent.  Skipping.")
            return
        self.log.debug("Updating quota status for user", user)
        quota.measure_usage(footprint, self.du_timeout_secs)
        actual_b, quota_b = quota.f_actual_bytes, quota.f_quota_bytes
        self.log.info(
            f"Updated quota for {user} using {actual_b} of {quota_b} bytes.",
            **quota.attrs,
        )
        self.log.debug(
            "Elapsed time for user",
            user,
            "measurement",
            (dt_from_iso(quota.stopped) - dt_from_iso(quota.started)),
        )


class QuotaReaperDaemon(QuotaDaemon):

    name = "Reaper"

    def operate_on_user(self, user, last_activity, footprint):
        self.log.debug("Checking", user, "for quota warning or violation.")
        logger = self.log.warning if last_activity != NULL_TIME else self.log.info
        if not os.path.exists(footprint.monitored_home):
            logger(
                f"User {user} home dir {footprint.monitored_home} does not exist. Skipping."
            )
            return
        if not os.path.exists(footprint.quota_file):
            logger(
                f"Quota file {footprint.quota_file} for user {user} does not exist. Skipping."
            )
            return
        quota = footprint.load()
        quota.last_activity = last_activity
        quota.reaper_time = now()
        if (
            dt_from_iso(quota.reaper_time) - dt_from_iso(quota.last_activity)
        ).seconds < self.period_secs:
            quota.active_at_reap = 1
        else:
            quota.active_at_reap = 0
        footprint.save(quota)
        if quota.quota_state == "lockout":
            self.lockout(user, quota)
        elif quota.quota_state == "violation":
            self.violation(user, quota)
        elif quota.quota_state == "timed-out":
            self.timed_out(user, quota)
        elif quota.quota_state == "nearing-limit":
            self.nearing_limit(user, quota)
        else:
            actual_b, quota_b = quota.f_actual_bytes, quota.f_quota_bytes
            self.log.info(
                f"Quota for {user} using {actual_b} of {quota_b} bytes.  OK.",
                **quota.attrs,
            )

    def lockout(self, user, quota):
        actual_b, quota_b = quota.f_actual_bytes, quota.f_quota_bytes
        message = f"User {user} is using {actual_b} bytes exceeding quota {quota_b} bytes.  LOCKOUT."
        self.log.critical(message, **quota.attrs)
        self.log.critical("Deleting notebook server for", user)
        self.hub_api.delete_user_server(user)

    def violation(self, user, quota):
        actual_b, quota_b = quota.f_actual_bytes, quota.f_quota_bytes
        message = f"User {user} is using {actual_b} bytes exceeding quota {quota_b} bytes.  Lockout disabled."
        self.log.error(message, **quota.attrs)

    def timed_out(self, user, quota):
        message = (
            f"Quota measurement for user {user} exceeded "
            f"timeout {self.du_timeout_secs} secs.  Usage unknown,  potentially high."
        )
        self.log.warning(message, **quota.attrs)

    def nearing_limit(self, user, quota):
        actual_b, quota_b = quota.f_actual_bytes, quota.f_quota_bytes
        message = (
            f"User {user} using {actual_b} bytes nearing limit of {quota_b} bytes."
            f"  Fraction used: {quota.fraction_used}"
        )
        self.log.warning(message, **quota.attrs)


# ========================================================================================


def now():
    return trim_time(datetime.datetime.now().isoformat("T"))


def trim_time(t):
    """Format times from JH in quota format by trimming subseconds and timezone."""
    return NULL_TIME if t is None else t[: t.index(".") + 7]


def dt_now():
    # more consistent with recorded times than datetime.datetime.now()
    return dt_from_iso(now())


def dt_from_iso(iso):
    return datetime.datetime.fromisoformat(iso)


def run(cmd, cwd=".", timeout=10):
    """Run subprocess `cmd` in dir `cwd` failing if not completed within `timeout` seconds
    of if `cmd` returns a non-zero exit status.

    Returns both stdout+stderr from `cmd`.  (untested, verify manually if in doubt)
    """
    result = subprocess.run(
        cmd.split(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=True,
        cwd=cwd,
        timeout=timeout,
    )  # maybe succeeds
    return result.stdout


def du(path, timeout):
    output = run(
        f"/usr/bin/sudo /usr/bin/du --bytes --max-depth 0 {path}", timeout=timeout
    )
    bytes, path = output.strip().split()
    return int(bytes)


def human_format_number(number):
    """Reformat `number` by switching to engineering units and dropping to two fractional digits,
    10s of megs for G-scale files.
    """
    convert = [
        (2**40, "T"),
        (2**30, "G"),
        (2**20, "M"),
        (2**10, "K"),
    ]
    for limit, sym in convert:
        if isinstance(number, (float, int)) and number > limit:
            number /= limit
            break
    else:
        sym = ""
    if isinstance(number, int):
        # numstr = "%d" % number
        numstr = "{}".format(number)
    else:
        numstr = "{:0.1f}{}".format(number, sym)
    return "{!s:>7}".format(numstr)


# ========================================================================================


def parse_args():
    parser = argparse.ArgumentParser(
        description="Periodically compute/check quotas for active users or take actions based on quota state."
    )
    parser.add_argument(
        "--reaper-mode    ",
        dest="reaper_mode",
        action="store_true",
        help="If specified, act on quota status.  If not specified, monitor/update quota status.",
    )
    parser.add_argument(
        "--hub-url",
        dest="hub_url",
        action="store",
        help="Base URL of this JupyterHub server.",
    )
    parser.add_argument(
        "--api-token",
        dest="api_token",
        action="store",
        help="Token authorizing use of JupyterHub REST API.",
    )
    parser.add_argument(
        "--api-cert",
        dest="api_cert",
        action="store",
        help="Path for EFS Quota cert for calls to JupyterHub REST API.",
    )
    parser.add_argument(
        "--efs-quota-control",
        dest="efs_quota_control",
        default="/efs/quota-control",
        action="store",
        help="Root path for user quota control directories on EFS.",
    )
    parser.add_argument(
        "--home-root",
        dest="home_root",
        action="store",
        default="/efs/users",
        help="Top level directory for all user $HOME,  effectively /home.",
    )
    parser.add_argument(
        "--period-secs",
        dest="period_secs",
        type=float,
        action="store",
        default=PERIOD_SECS,
        help="Period in seconds at which to run control loop.",
    )
    parser.add_argument(
        "--stale-quota-secs",
        dest="stale_quota_secs",
        type=float,
        action="store",
        default=STALE_QUOTA_SECS,
        help="Seconds until a quota should be scanned even if inactive.",
    )
    parser.add_argument(
        "--du-timeout-secs",
        dest="du_timeout_secs",
        type=float,
        action="store",
        default=DU_TIMEOUT_SECS,
        help="Seconds until du will time out resulting in no measurement.",
    )
    return parser.parse_args()


def main():
    """Parse command line arguments and run the test spec.

    Return the number of failing tests or 0 if all tests pass.
    """
    args = parse_args()
    if args.reaper_mode:
        daemon_class = QuotaReaperDaemon
    else:
        daemon_class = QuotaMonitorDaemon
    daemon = daemon_class(
        args.hub_url,
        args.api_token,
        args.api_cert,
        args.efs_quota_control,
        args.home_root,
        args.period_secs,
        args.stale_quota_secs,
        args.du_timeout_secs,
    )
    return daemon.main()


if __name__ == "__main__":
    sys.exit(main())
