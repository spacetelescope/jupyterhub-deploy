import os
import subprocess
import json
import math
import random
import string
import operator
import argparse

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


def get_raw_data(query, end_date):
    end_date = f'{end_date}:23:59:59' # GMT
    to = datetime.strptime(end_date, '%Y-%m-%d:%H:%M:%S')
    _from = to + relativedelta(weeks=-1)

    configuration = Configuration()
    with ApiClient(configuration) as api_client:
        api_instance = MetricsApi(api_client)
        response = api_instance.query_metrics(
            _from=int(_from.timestamp()),
            to=int(to.timestamp()),
            query=query
        )
        return response


def parse_data(data):
    users_raw = {}
    for s in data['series']:
        user = s['tag_set'][0].lstrip('pod_name:')
        users_raw[user] = []
        for p in s['pointlist']:
            val = p.value[1]
            if val:
                users_raw[user].append(val)

    users = {}
    for u in users_raw:
        hours = math.ceil(float(len(users_raw[u])))
        #anon_user = ''.join(random.choice(u) for i in range(8))
        anon_user = ''.join(random.choice(string.ascii_letters) for i in range(6))
        users[anon_user] = hours

    return users


def print_report(data, end_date):
    _sorted = sorted(data.items(), key=operator.itemgetter(1), reverse=True)

    title = f'\nUser data for week ending on {end_date}'
    print(title)
    print('-'*len(title))
    print(f'\nNumber of unique users: {int(len(_sorted))}\n')
    print('Total usage hours per user (anonymized):')
    for (u, val) in _sorted:
        print(f'\t{u}\t{val}')
    print()







if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--end-date', type=str, required=True)
    args = parser.parse_args()

    os.environ['DD_SITE'] = 'datadoghq.com'
    os.environ['DD_API_KEY'] = get_key('api')
    os.environ['DD_APP_KEY'] = get_key('app')

    # TODO: make this an arg...
    #end_date = '2021-12-20'

    # TODO: get these vars elsewhere (arg? env?)
    account = 'aws-account-name:aws-tess-tike-ops'
    cluster = 'eks_cluster-name:tike'
    pod_name = 'pod_name:jupyter-*'
    query = f'max:kubernetes_state.pod.count{{{account},{cluster},{pod_name}}} by {{pod_name}}'

    raw_data = get_raw_data(
		query,
        args.end_date
    )

    user_data = parse_data(raw_data)

    print_report(user_data, args.end_date)






