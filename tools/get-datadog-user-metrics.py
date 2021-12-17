
import os
import subprocess
import json
from time import time
from datadog import initialize, api


def get_key(key_type):
    top = os.environ.get('JUPYTERHUB_DIR')
    script = os.path.join(top, 'tools', 'get-datadog-key')
    p = subprocess.Popen(
        [script, key_type],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    out, err = p.communicate()
    return str(out).lstrip("b'").rstrip("\\n'")


def get_data(api_key, app_key):
    options = {
        'api_key': api_key,
        'app_key': app_key
    }
    initialize(**options)

    # time period over which we want data
    time_interval = 604800 # seconds in a week
    end = int(time())
    start = end - time_interval

    # TODO: get these vars elsewhere (arg? env?)
    account = 'aws-tess-tike-ops'
    cluster = 'tike'
    pod_name = 'jupyter-*'

    query = f'max:kubernetes_state.pod.count{{{account},{cluster},{pod_name}}} by {{pod_name}}'
    #max:kubernetes_state.pod.count{$account,$cluster,$pod_name} by {pod_name}
    print()
    print(query)
    print()
    print()

    results = api.Metric.query(
        query=query,
        start=start - time_interval,
        end=end
    )

    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    get_data(
        get_key('api'),
        get_key('app')
    )






















