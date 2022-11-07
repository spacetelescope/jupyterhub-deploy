import requests.exceptions
from unittest.mock import Mock, MagicMock, patch
import traceback
import pytest
import logging

import efs_quota_monitor as efqm
import check_quota


quota_yaml = """
active_at_reap: 0
actual_bytes: 1763939
fraction_used: 0.0821398123832005
last_activity: '2022-08-29T19:49:48.890087'
lockout_enabled: true
quota_bytes: 21474836
quota_enabled: true
quota_state: ok
reaper_time: '2022-09-07T20:29:57.483469'
started: '2022-08-29T19:56:17.359858'
stopped: '2022-08-29T19:56:17.458149'
timed_out: false
user: homer@stsci.edu
warn_fraction: 0.9
"""


def get_api():
    return efqm.HubRestApi(
        "https://dev.roman.science.stsci.edu",
        "d9e7c7bfd675edfe5b2f34950497dce850215ecc0396cb59f8fefbc94664fc09",
        "/etc/ssl/jh-intermediates.pem",
    )


@patch("efs_quota_monitor.requests_config")
def test_last_activity(mock_config):

    # get_api() returns a "real" HubRestApi object with a mocked requests field.
    api = get_api()

    response_mock = MagicMock()
    response_mock.status_code = 200
    response_mock.json.return_value = [
        {
            "name": "homer@stsci.edu",
            "last_activity": "2022-09-07T12:52:24.200461999",
        }
    ]
    api.requests.get.side_effect = [
        response_mock,
        requests.exceptions.Timeout,
    ]

    api.last_activity() == {"homer@stsci.edu": "2022-09-07T12:52:24.200461999"}

    api.requests.get.assert_called_once_with(
        api.api_url + "/users",
        headers={
            "Authorization": f"token {api.api_token}",
        },
        verify=api.api_cert,
        timeout=efqm.API_TIMEOUT,
    )

    # Test that the first request raises a Timeout
    with pytest.raises(requests.exceptions.Timeout):
        api.last_activity()


@patch("efs_quota_monitor.requests_config")
def test_delete_user_server(mock_requests):

    api = get_api()

    response_mock = Mock()
    response_mock.status_code = 204
    response_mock.json.return_value = None
    api.requests.delete.side_effect = [response_mock]

    user = "homer@stsci.edu"

    api.delete_user_server(user)

    api.requests.delete.assert_called_once_with(
        api.api_url + f"/users/{user}/server",
        headers={
            "Authorization": f"token {api.api_token}",
        },
        verify=api.api_cert,
        timeout=efqm.API_TIMEOUT,
    )


def test_init_quota_data():
    quota_g = 0.01
    q = efqm.QuotaData("homer@stsci.edu", quota_g, warn_fraction=0.5)
    assert q.user == "homer@stsci.edu"
    assert q.quota_bytes == int(quota_g * 2**30)
    assert q.actual_bytes == -1
    assert q.warn_fraction == 0.5
    assert q.quota_enabled
    assert q.lockout_enabled
    assert not q.timed_out
    assert q.quota_state == "ok"


# ---------------------------------------------------------


def get_monitor(period=10, stale=3, du_timeout=3600):
    return efqm.main(
        f"""
        --hub-url https://dev.roman.science.stsci.edu
        --api-token d9e7c7bfd675edfe5b2f34950497dce850215ecc0396cb59f8fefbc94664fc09
        --api-cert /etc/ssl/jh-intermediates.pem
        --efs-quota-control efs/quota-control
        --home-root efs/users
        --period-secs {period}
        --stale-quota-secs {stale} --du-timeout-secs {du_timeout}
    """.split()
    )


def get_reaper(period=10, stale=3, du_timeout=3600):
    return efqm.main(
        f"""
        --reaper-mode
        --hub-url https://dev.roman.science.stsci.edu
        --api-token d9e7c7bfd675edfe5b2f34950497dce850215ecc0396cb59f8fefbc94664fc09
        --api-cert /etc/ssl/jh-intermediates.pem
        --efs-quota-control efs/quota-control
        --home-root efs/users
        --period-secs {period}
        --stale-quota-secs {stale} --du-timeout-secs {du_timeout}
    """.split()
    )


@patch("efs_quota_monitor.now")
@patch("efs_quota_monitor.du")
@patch("time.sleep")
def quota_daemon_main(
    get_daemon, now_stamps, la_dicts, du_values, mock_sleep, mock_du, mock_now
):
    mock_sleep.return_value = 1
    mock_now.side_effect = now_stamps
    mock_du.side_effect = du_values
    with patch.object(efqm.HubRestApi, "last_activity") as last_activity:
        with patch.object(efqm.AnnouncementRestApi, "send_message"):
            daemon = get_daemon()
            last_activity.side_effect = list(la_dicts) + [BaseException]

            def reraise(exc, *args, **keys):
                if not isinstance(exc, StopIteration):
                    traceback.print_exc()
                    daemon.log.error(*args, **keys)
                    raise

            daemon.log.dd_mode = True
            daemon.log.debug_mode = False
            daemon.log.exception = reraise
            try:
                daemon.main()
            except BaseException:
                pass


NOW_STAMPS = (
    "2022-01-01T00:00:00",
    "2022-01-01T00:00:00.125000",
) * 100

LA_DICTS = ({"homer@stsci.edu": "2022-01-01T00:00:01.500000"},)

DU_VALUES = (
    3 * 10**6,
    6 * 10**6,
    10 * 10**6,
    11 * 10**6,
    3 * 10**6,
)


def quota_monitor_main(now_stamps=NOW_STAMPS, la_dicts=LA_DICTS, du_values=DU_VALUES):
    return quota_daemon_main(get_monitor, now_stamps, la_dicts, du_values)


def quota_reaper_main(now_stamps=NOW_STAMPS, la_dicts=LA_DICTS, du_values=DU_VALUES):
    return quota_daemon_main(get_reaper, now_stamps, la_dicts, du_values)

def clear_log_handlers():
    logger = logging.getLogger()
    if (logger.hasHandlers()):
        logger.handlers.clear()
    return True

def test_checker():
    clear_log_handlers()
    return check_quota.main(["efs/quota-control/homer-40stsci-2eedu/quota.yaml"])
