
import os
import subprocess
import json
#from time import time
#from datadog import initialize, api

from datetime import datetime
from dateutil.relativedelta import relativedelta
from datadog_api_client.v1 import ApiClient, Configuration
from datadog_api_client.v1.api.metrics_api import MetricsApi


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
    os.environ['DD_SITE'] = 'datadoghq.com'
    os.environ['DD_API_KEY'] = api_key
    os.environ['DD_APP_KEY'] = app_key

    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = MetricsApi(api_client)
        response = api_instance.query_metrics(
            _from=int((datetime.now() + relativedelta(days=-1)).timestamp()),
            to=int(datetime.now().timestamp()),
            query="system.cpu.idle{*}",
        )

        print(response)

    #options = {
    #    'api_key': api_key,
    #    'app_key': app_key
    #}
    #initialize(**options)

    # time period over which we want data
    #time_interval = 604800 # seconds in a week
    #end = int(time())
    #start = end - time_interval

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

    #results = api.Metric.query(
    #    query=query,
    #    start=start - time_interval,
    #    end=end
    #)

    #print(json.dumps(results, indent=2))


if __name__ == '__main__':
    get_data(
        get_key('api'),
        get_key('app')
    )






















