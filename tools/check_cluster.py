#! /usr/bin/env python

"""Check properties of Terraformed resources and/or JupyterHub to verify good deployment.
ignore the hub since it may not be delpoyed on the cluster yet.

check creation date
check for global hammer
"""

import sys
import os
import subprocess
import argparse
import re
import json
from collections import defaultdict
import builtins
import functools
import traceback


import yaml


CLUSTER_CHECKS = """
Globals:
  environment:
    - DEPLOYMENT_NAME
    - ENVIRONMENT
    - JH_HOSTNAME
    - ADMIN_ARN
    - ACCOUNT_ID
  constants:
    V_K8S: "1.21"
    MAX_NODE_AGE: 10d
    MAX_EFS_FILE_SYSTEM_SIZE: 50000000000000
    CORE_NODES: 3
    NOTEBOOK_EC2_TYPE: r5.xlarge
    MAX_RESTARTS: 0
    LOG_REACH: 30m
Groups:
  - group: Kubernetes Pods
    command: kubectl get pods -A
    parser: named_columns
    assertions:
    - name: All pods
      all: STATUS=='Running' and int(RESTARTS)<=MAX_RESTARTS
    - name: EFS provisioner
      ok_rows==1: NAMESPACE=='support' and 'efs-provisioner' in NAME
    - name: Kube Proxy
      ok_rows>=4: NAMESPACE=='kube-system' and 'kube-proxy' in NAME
    - name: Autoscaler
      ok_rows==1: NAMESPACE=='kube-system' and 'cluster-autoscaler' in NAME
    - name: AWS Pods
      ok_rows>=4: NAMESPACE=='kube-system' and 'aws-node' in NAME
    - name: Core DNS
      ok_rows==2: NAMESPACE=='kube-system' and 'coredns' in NAME
  - group: JupyterHub Pods
    command: kubectl get pods -A
    parser: named_columns
    assertions:
    - name: Image puller
      ok_rows>=1: NAMESPACE=='default' and 'continuous-image-puller' in NAME
    - name: Hub
      ok_rows==1: NAMESPACE=='default' and 'hub' in NAME
    - name: Proxy
      ok_rows>=1: NAMESPACE=='default' and 'proxy' in NAME
    - name: User-scheduler
      ok_rows==2: NAMESPACE=='default' and 'user-scheduler' in NAME
    - name: User-placeholder
      ok_rows>=1: NAMESPACE=='default' and 'user-placeholder' in NAME
  - group: JupyterHub Nodes
    command: kubectl get nodes -A --show-labels=true
    parser: named_columns
    assertions:
    - name: At least 4 STATUS Ready new Hub AMI ID
      ok_rows>=4: STATUS=="Ready" # and HUB_AMI_ID in LABELS
    - name: All Nodes Ready Status
      all: STATUS=="Ready" or STATUS=="Ready,SchedulingDisabled"
    - name: Kubernetes Version
      all: V_K8S in VERSION
    - name: Node Age
      all: convert_age(AGE) < convert_age(MAX_NODE_AGE)
    - name: Core us-east-1a
      ok_rows==1:  "DEPLOYMENT_NAME+'-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1a' in LABELS"
    - name: Core us-east-1b
      ok_rows==1:  "DEPLOYMENT_NAME+'-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1b' in LABELS"
    - name: Core us-east-1c
      ok_rows==1:  "DEPLOYMENT_NAME+'-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1c' in LABELS"
    - name: Notebook nodes
      ok_rows>=1:  "DEPLOYMENT_NAME+'-notebook' in LABELS and NOTEBOOK_EC2_TYPE in LABELS  and 'region=us-east-1' in LABELS"
  - group: EKS Services
    command:  kubectl get services -A
    parser: named_columns
    assertions:
    - name: Datadog Cluster Agent Service
      ok_rows==1: NAMESPACE=='datadog' and NAME=='datadog-cluster-agent' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='5005/TCP'
    - name: Datadog Kube State Metrics Service
      ok_rows==1: NAMESPACE=='datadog' and NAME=='datadog-kube-state-metrics' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='8080/TCP'
    - name: Hub Service
      ok_rows==1: NAMESPACE=='default' and NAME=='hub' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='8081/TCP'
    - name: Kubernetes Service
      ok_rows==1: NAMESPACE=='default' and NAME=='kubernetes' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='443/TCP'
    - name: Proxy API Service
      ok_rows==1: NAMESPACE=='default' and NAME=='proxy-api' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='8001/TCP'
    - name: Proxy Public Service
      ok_rows==1: NAMESPACE=='default' and NAME=='proxy-public' and TYPE=='LoadBalancer' and '.elb.amazonaws.com' in _['EXTERNAL-IP'] and '443:' in _['PORT(S)'] and '80:' in _['PORT(S)'] and 'TCP' in _['PORT(S)'] and 'UDP' not in  _['PORT(S)']
    - name: Cluster Autoscaler Service
      ok_rows==1: NAMESPACE=='kube-system' and NAME=='cluster-autoscaler-aws-cluster-autoscaler' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='8085/TCP'
    - name: Kube DNS Service
      ok_rows==1: NAMESPACE=='kube-system' and NAME=='kube-dns' and TYPE=='ClusterIP' and _['EXTERNAL-IP']=='<none>' and _['PORT(S)']=='53/UDP,53/TCP'
  - group: EKS Deployments
    command:  kubectl get deployments -A
    parser: named_columns
    assertions:
    - name: Hub Deployment
      ok_rows==1: NAMESPACE=='default' and NAME=='hub' and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
    - name: Proxy Deployment
      ok_rows==1: NAMESPACE=='default' and NAME=='proxy' and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
    - name: User Scheduler Deployment
      ok_rows==1: NAMESPACE=='default' and NAME=='user-scheduler' and READY=='2/2' and _['UP-TO-DATE']=='2' and AVAILABLE=='2'
    - name: Cluster Autoscaler Deployment
      ok_rows==1: NAMESPACE=='kube-system' and 'cluster-autoscaler' in NAME and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
    - name: Core DNS Deployment
      ok_rows==1: NAMESPACE=='kube-system' and 'coredns' in NAME and READY=='2/2' and _['UP-TO-DATE']=='2' and AVAILABLE=='2'
    - name: EFS Provisioner Deployment
      ok_rows==1: NAMESPACE=='support' and 'efs-provisioner' in NAME and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
    - name: Datadog Cluster Agent Deployment
      ok_rows==1: NAMESPACE=='datadog' and 'datadog-cluster-agent' in NAME and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
    - name: Datadog Kube Metrics Deployment
      ok_rows==1: NAMESPACE=='datadog' and 'datadog-kube-state-metrics' in NAME and READY=='1/1' and _['UP-TO-DATE']=='1' and AVAILABLE=='1'
  - group: Route-53 Host
    command: "host {JH_HOSTNAME}"
    parser: raw
    assertions:
    - name: DNS Mapping
      simple: "f'{JH_HOSTNAME} is an alias for' in _"
  - group: JupyterHub Index Page
    command: "wget --no-check-certificate -O- {JH_HOSTNAME}"
    parser: raw
    assertions:
    - name: Server Index Page
      simple: "'HTTP request sent, awaiting response... 200 OK' in _"
  - group: EFS File Systems
    command: awsudo {ADMIN_ARN} aws efs describe-file-systems --output yaml --query FileSystems
    parser: yaml
    assertions:
    - name: EFS Home Dirs
      ok_rows==1: Name==DEPLOYMENT_NAME+'-home-dirs' and LifeCycleState=='available' and Encrypted==True and NumberOfMountTargets==3 and OwnerId==ACCOUNT_ID and aws_kv_dict(Tags)['stsci-backup']=='dmd-2w-sat'
    - name: EFS Max Size
      all: int(SizeInBytes['Value']) < MAX_EFS_FILE_SYSTEM_SIZE
  - group: Daemonsets named rows
    command: kubectl get daemonsets -A
    parser: named_rows
    assertions:
    - name: datadog - proxy - aws-nodes READY
      simple: _['datadog']['READY'] == _['kube-proxy']['READY'] == _['aws-node']['READY']
    - name: datadog - proxy - aws-nodes DESIRED
      simple: _['datadog']['DESIRED'] == _['kube-proxy']['DESIRED'] == _['aws-node']['DESIRED']
    - name: datadog - proxy - aws-nodes CURRENT
      simple: _['datadog']['CURRENT'] == _['kube-proxy']['CURRENT'] == _['aws-node']['CURRENT']
    - name: datadog - proxy - aws-nodes UP-TO-DATE
      simple: _['datadog']['UP-TO-DATE'] == _['kube-proxy']['UP-TO-DATE'] == _['aws-node']['UP-TO-DATE']
    - name: datadog - proxy - aws-nodes AVAILABLE
      simple: _['datadog']['AVAILABLE'] == _['kube-proxy']['AVAILABLE'] == _['aws-node']['AVAILABLE']
    - name: continuous image puller notebook nodes only
      simple: int(_['continuous-image-puller']['READY']) == int(_['aws-node']['READY']) - CORE_NODES
  - group: Daemonsets named columns
    command: kubectl get daemonsets -A
    parser: named_columns
    assertions:
    - name: continuous-image-puller
      ok_rows==1: NAMESPACE=='default' and NAME=='continuous-image-puller'
    - name: datadog
      ok_rows==1: NAMESPACE=='datadog' and NAME=='datadog'
    - name: kube-proxy
      ok_rows==1: NAMESPACE=='kube-system' and NAME=='kube-proxy'
    - name:
      ok_rows==1: NAMESPACE=='kube-system' and NAME=='aws-node'
    - name: matching daemonset states
      all: READY==DESIRED==CURRENT==AVAILABLE==_['UP-TO-DATE']
  - group: EKS AMI Rotation
    command: awsudo {ADMIN_ARN} aws eks list-nodegroups --cluster-name {DEPLOYMENT_NAME} --query nodegroups --output text
    parser: raw
    assertions:
    - name: Only rotated nodegroup names
      simple: "functools.reduce(lambda a, b: a and b, [x.count('-')!=1 for x in _.split()])"
  - group: Log Error Check
    function: pod_logs(LOG_REACH)
    parser: yaml
    assertions:
    - name: No errors in logs
      simple: ERRORS==0
  - group: Pod to Node Map
    command: kubectl get pods -A -o wide
    replace_output:
      input: NOMINATED NODE
      output: NOMINATED_NODE
    parser: node_map
    print_parsing: true
"""  # noqa: E501


def convert_age(age_str):
    """Convert k8s abbreviated-style datetime str e.g. 14d2h to an integer."""
    # age_str_org = age_str

    def age_subst(age_str, letter, factor):
        parts = age_str.split(letter)
        if len(parts) == 2:
            age_str = parts[0] + "*" + factor + "+" + parts[1]
        return age_str

    age_str = age_subst(age_str, "d", "60*60*24")
    age_str = age_subst(age_str, "h", "60*60")
    age_str = age_subst(age_str, "m", "60")
    age_str = age_subst(age_str, "s", "1")
    age_str = age_str[:-1]
    # print(
    #    f"convert_age({repr(age_str_org)}) --> {repr(age_str)} --> {eval(age_str)}"  # nosec
    # )  # nosec
    return eval(age_str)  # nosec


def aws_kv_dict(key_value_dict_list):
    """Convert AWS dict representation [{ 'Key':k, 'Value':v}, ...] to a Python dict."""
    return {item["Key"]: item["Value"] for item in key_value_dict_list}


def run(cmd, cwd=".", timeout=10):
    """Run subprocess `cmd` in dir `cwd` failing if not completed within `timeout` seconds
    of if `cmd` returns a non-zero exit status.

    Returns both stdout+stderr from `cmd`.  (untested, verify manually if in doubt)
    """
    print(cmd)
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


def parse_node_map(output):
    namespaces = parse_named_columns(output)
    node_map = defaultdict(list)
    for namespace in namespaces:
        node_map[namespace["NODE"]].append(
            namespace["NAMESPACE"] + ":" + namespace["NAME"]
        )
    output = ["Mapping from Node to Pod", "-" * 80, yaml.dump(dict(node_map))]
    return "\n".join(output)


def parse_named_columns(output):
    """Return rows from a table string `output` as a sequence of dicts.
    The first row should contain whitespace delimited column names.
    Each subsequent row should contain whitespace delimited column values.

    Given tabular `output` as found in many k8s commands:

    col1_name         col2_name      ...
    col1_row1_val     col2_row1_val  ...
    col1_row2_val     col1_row2_val  ...
    ...

    Returns [ {col1_name: col1_row1_val, col2_name: col2_row1_val, ...},
              {col1_name: col1_row2_val, col2_name: col2_row2_val, ...},
              ... ]

    Each dict in the returned sequence is suitable as a namespace for eval()
    """
    lines = output.splitlines()
    columns = lines[0].split()
    rows = []
    for line in lines[1:]:
        d = dict(zip(columns, line.split()))
        d["_"] = d
        rows.append(d)
    return rows


def parse_named_rows(output, key="NAME"):
    return {"_": {row[key]: row for row in parse_named_columns(output)}}


def parse_raw(output):
    """Just return `output` as a single string assigned to dict key '_'
    for reference in assertion expressions.

    Returns {'_': output}
    """
    return dict(_=output)


def parse_yaml(output):
    """Return the YAML parsing of `output` string.  aws commands can
    be filtered using the --query parameter to produce more manageable
    output before YAML parsing.
    """
    return yaml.safe_load(output)


def parse_json(output):
    """Return the JSON parsing of `output` string.  aws commands can
    be filtered using the --query parameter to produce more manageable
    output before JSON parsing.
    """
    return json.loads(output)


def parse_none(output):
    """Return the input as the output,  i.e. no changes."""
    return output


def test_function(parameters):
    return yaml.dump(parameters)


class Checker:
    """The Checker class runs a number of tests defined in a `test_spec` string.

    Commands
    --------

    Each Group includes a subprocess CLI command from which the output is captured,
    parsed, and checked against various assertions.

    Output Parsing
    --------------

    The command output is parsed using a parser which can be be one of
    named_rows, raw, yaml, or json.

    named_rows is ideal for parsing kubectl output in which each row
    defines a set of variables as a dict.  named_rows requires that
    column names and values do not contain spaces; generally it is not
    a problem but not all kubectl output modes work.

    raw simply returns { "_": cmd_output } so _ is used as a variable
    in assertions to refer to the entire output string.

    yaml and json return parsed command output using their respective
    loaders.  The --query parameter of the 'aws' commands can be
    useful for pre-filtering command output so that a simple direct
    parsing is usable in assertions.

    Test Assertions
    ---------------

    A series of assertions are evaluated on the parsed output from each group's command.

    Assertions take the form:

    simple: <python expression using parsed outputs to define variables, eval must pass.>

    ok_rows_expr: <python expression using parsed outputs to define row variables, ok_rows_expr must be True.>

    all: <python expression using parsed outputs to define row variables,  each row must pass.>

    Examples of ok_rows expressions might be:

    ok_rows==1
    ok_rows>=3

    Pseudo code for 'all' is:

    ok_rows==len(total output rows)

    ok_rows is assigned the number of times the assertion evaluates to True when run
    against each of the row namespace dicts.  Hence overall test success does not
    require every row to pass the assertion.

    The `test_spec` specifies a string of YAML which defines:

    Globals:
      environment:
        - env var1 needed in assertion expressions imported from os.environ
        ...
      constants:
        - VAR: VAL a VAR needed in assertion expressions with the spec'd VAL
        ...
    Groups:
    - group: <Command Group Name>
      command: <UNIX subprocess command string>
      parser: <named_rows|raw|yaml|json>
      assertions:
      - name: <Name defining check>
        <simple|all|ok_rows_expr>:  <python expression>
      - name: <Name defining check>
        <simple|all|ok_rows_expr>:  <python expression>
      ...
    ...

    NOTE: In the spec,  substitions for output vars, env vars, constants,
      variables, and built-in functions occur in two basic ways:
          - Using Python's f-string {} formatting.       (commands)
          - Treated as a variable name to be eval'ed.    (assertions)
      This is because commands are "".format()'ed but assertions are eval'ed,
      each against similar namespaces with the caveat that the command formatting
      includes no variables derived from it's own output.

    if `output_file` is specified,  commands are run and outputs are
       stored at the spec'ed path,  the checker exits w/o running tests.

    if `input_file` is specified, it is presumed to be the path to command
       output YAML stored by `output_file` and replaces running commands,
       checks are run using the stored outputs.

    input_file and output_file are mutually exclusive.

    if `verbose` is specified then additional assertion-by-assertion,
      row-by-row output is generated.

    if `groups_regex` is specified,  only the group names which can be
      searched by the regex are checked.  (case insensitive substrings
      of group names work).

    if `variables` is specified,  it should be a comma seperated string
      of VAR=VAL pairs,  i.e.  VAR1=VAL1,VAR2=VAL2,...
      These variables are added to the namespace used for running/eval'ing
      commands and assertions and override values already defined in Globals.
    """  # noqa: E501

    def __init__(
        self,
        test_spec=CLUSTER_CHECKS,
        output_file=None,
        input_file=None,
        verbose=False,
        groups_regex=".+",
        exclude_regex="^$",
        variables=None,
    ):
        self._output_file = output_file
        self._input_file = input_file
        self._verbose = verbose
        self._groups_regex = groups_regex
        self._exclude_regex = exclude_regex
        print("===> Loading test spec")
        self.loaded_spec = yaml.safe_load(test_spec)
        self.variables = (
            dict([var.split("=") for var in variables.split(",")]) if variables else []
        )
        self._outputs = {}
        self._errors = 0
        self._error_msgs = []

    @property
    def groups(self):
        return self.loaded_spec["Groups"]

    @property
    def spec_environment(self):
        return {
            var: os.environ[var]
            for var in self.loaded_spec.get("Globals", {}).get("environment", [])
        }

    @property
    def spec_constants(self):
        return self.loaded_spec.get("Globals", {}).get("constants", {})

    @property
    def builtins(self):
        result = {
            key: getattr(builtins, key) for key in dir(builtins)
        }  # Python builtins
        result.update(
            dict(
                convert_age=convert_age,
                aws_kv_dict=aws_kv_dict,
                test_function=test_function,
                functools=functools,
                pod_logs=self.pod_logs,
            )
        )
        return result

    @property
    def combined_environment(self):
        env = dict()
        env.update(self.builtins)
        env.update(self.spec_constants)
        env.update(self.spec_environment)
        env.update(self.variables)
        return env

    def main(self):
        self.setup_outputs()
        for check in self.groups:
            if re.search(
                self._groups_regex, check["group"], re.IGNORECASE
            ) and not re.search(self._exclude_regex, check["group"], re.IGNORECASE):
                self.run_check(check)
        if self._output_file:
            self.store_outputs()
        return self._errors

    def setup_outputs(self):
        """Fetch saved commands ouputs from file rather than running commands."""
        if self._input_file:
            with open(self._input_file) as file:
                self._outputs = yaml.safe_load(file)
        else:
            self._outputs = {}

    def store_outputs(self):
        """Store command outputs to file for running offline later."""
        print("=" * 80)
        print("Saving", repr(self._output_file))
        with open(self._output_file, "w+") as file:
            yaml.dump(self._outputs, file)

    def replace_output(self, check, output):
        if check.get("replace_output"):
            input_patt = check.get("replace_output").get("input")
            output_patt = check.get("replace_output").get("output")
            output = re.sub(input_patt, output_patt, output, flags=re.MULTILINE)
        return output

    def run_check(self, check):
        print("=" * 80)
        try:
            output = self.get_command_output(check)
        except Exception as exc:
            self.error(
                "Failed obtaining command output for group",
                repr(check.get("group")),
                ":",
                str(exc),
            )
            print("=" * 80)
            return
        if self._output_file:
            return
        if not output.startswith("FAILED"):
            print("-" * 80)
            print(output)
            print("=" * 80)
            self.process_output(check, output)

    def process_output(self, check, output):
        try:
            output = self.replace_output(check, output)
            parser = globals()[f"parse_{check['parser']}"]
            namespaces = parser(output)
        except Exception as exc:
            self.error("PARSER failed for", repr(check["group"]), ":", str(exc))
            return
        if check.get("print_parsing"):
            print(namespaces)
        for assertion in check.get("assertions", []):
            try:
                self.check_assertion(check["group"], assertion, namespaces)
            except Exception as exc:
                self.error(
                    "EXECUTION failed for",
                    repr(check["group"]),
                    ":",
                    repr(assertion["name"]),
                    ":",
                    str(exc),
                )

    def get_command_output(self, check):
        group = check["group"]
        if not self._input_file:
            self._outputs[group] = self.compute_outputs(group, check)
        return self._outputs[group]

    def compute_outputs(self, group, check):
        if check.get("command"):
            command = check.get("command").format(**self.combined_environment)
        elif check.get("function"):
            command = check.get("function").format(**self.combined_environment)
        else:
            raise RuntimeError(f"Group {group} doesn't define an input command.")
        print("===> Fetching", repr(group))
        print("=" * 80)
        try:
            if check.get("command"):
                outputs = run(command).strip()
            else:
                outputs = eval(  # nosec
                    command, self.combined_environment, self.combined_environment
                )
        except Exception as exc:
            traceback.print_exc()
            outputs = f"FAILED for '{group}': '{command}' : '{str(exc)}'"
            self.error(outputs)
        return outputs

    def check_assertion(self, group_name, assertion, namespaces):
        assertion = dict(assertion)
        assertion_name = assertion.pop("name")
        requirement, condition = list(assertion.items())[0]
        # condition = condition.format(**self.combined_environment)
        print(f"Checking assertion '{assertion_name}': {requirement} : {condition}")
        if requirement == "simple":
            self.verify_simple(group_name, assertion_name, namespaces, condition)
        elif requirement.startswith(("ok_rows", "all")):
            self.verify_rows(
                group_name, assertion_name, namespaces, requirement, condition
            )
        else:
            raise ValueError(
                f"Unhandled requirement: {requirement} for assertion: {assertion}"
            )
        print()

    def verify_rows(self, group_name, name, namespaces, requirement, condition):
        rows = []
        for i, namespace in enumerate(namespaces):
            self.verbose(f"Checking '{name}' #{i} : {condition} ... ", end="")
            if self.eval_condition(namespace, condition):
                rows.append(namespace)
                self.verbose("OK")
            else:
                self.verbose("FAILED on row:", namespace)
        if requirement == "all":
            requirement = f"ok_rows=={len(namespaces)}"
        if self.eval_condition(dict(ok_rows=len(rows)), requirement):  # nosec
            print(f"===> OK '{group_name}' : '{name}'")
        else:
            self.error(f"FAILED '{group_name}' : '{name}' : {condition}")

    def verify_simple(self, group_name, name, namespace, condition):
        if self.eval_condition(namespace, condition):
            print(f"===> OK '{group_name}' : '{name}'")
        else:
            self.error(f"FAILED '{group_name}' : '{name}' : {condition}")
            self.verbose("Namespace:", namespace)

    def eval_condition(self, namespace, condition):
        namespace = dict(namespace)  # local no-side-effects copy
        namespace.update(self.combined_environment)
        return eval(condition, {}, namespace)  # nosec

    def verbose(self, *args, **keys):
        if self._verbose:
            print(*args, **keys)

    def error(self, *args):
        self._errors += 1
        self._error_msgs.append(" ".join(str(arg) for arg in args))
        print("===> ERROR: ", *args)

    def show_error_status(self):
        print("=" * 80)
        print("Overall", self._errors, "errors occurred:")
        for msg in self._error_msgs:
            print(msg)

    def pod_logs(self, log_reach="30m"):
        loaded = yaml.safe_load(run("kubectl get pods -A --output yaml"))
        pods = [
            (pod["metadata"]["namespace"], pod["metadata"]["name"])
            for pod in loaded["items"]
        ]
        print("=" * 80)
        print("Fetching", len(loaded["items"]), "pod logs")
        pod_errors = dict()
        for i, (namespace, name) in enumerate(pods):
            pod = f"{namespace}:{name}"
            print()
            output = run(
                f"kubectl logs -n {namespace} {name} --since {log_reach} --all-containers --timestamps=True"
            )
            for line in output.splitlines():
                if "error" in line.lower() and "| INFO |" not in line:
                    self.error(f"FAILED Pod {pod} log:", line)
                    if pod not in pod_errors:
                        pod_errors[pod] = []
                    pod_errors[pod].append(line)
        print()
        print("-" * 80)
        return yaml.dump(
            {
                "ERRORS": len(pod_errors),
                "FAILING_PODS": sorted(list(pod_errors.keys())),
                "POD_ERRORS": pod_errors,
            }
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Perform various cluster and hub checks to automatically detect basic anomalies."
    )
    parser.add_argument(
        "--test-spec",
        dest="test_spec",
        action="store",
        default=None,
        help="Custom test specification.  Defaults to None meaning use built-in spec.",
    )
    parser.add_argument(
        "--output-file",
        dest="output_file",
        action="store",
        default=None,
        help="Filepath to store outputs of test commands.",
    )
    parser.add_argument(
        "--input-file",
        dest="input_file",
        action="store",
        default=None,
        help="Filepath to load previously stored test command results.",
    )
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Include additional output.",
    )
    parser.add_argument(
        "--groups-regex",
        dest="groups_regex",
        action="store",
        default=".+",
        help="Select groups to execute based on the specified regex,  defaulting to all groups."
        "  Unique group substrings are valid, |-or patterns together. Case is irrelevant.",
    )
    parser.add_argument(
        "--exclude-regex",
        dest="exclude_regex",
        action="store",
        default="^$",
        help="Select groups to skip based on the specified regex,  defaulting to no groups."
        "  Unique group substrings are valid, |-or patterns together. Case is irrelevant.",
    )
    parser.add_argument(
        "--variables",
        dest="variables",
        action="store",
        default=None,
        help="Custom override variables which can be used in commands, assertions, etc."
        "  --variables var1=val1,var2=val2,...",
    )
    return parser.parse_args()


def main():
    """Parse command line arguments and run the test spec.

    Return the number of failing tests or 0 if all tests pass.
    """
    args = parse_args()
    test_spec = (
        open(args.test_spec).read().strip() if args.test_spec else CLUSTER_CHECKS
    )
    checker = Checker(
        test_spec=test_spec,
        output_file=args.output_file,
        input_file=args.input_file,
        verbose=args.verbose,
        groups_regex=args.groups_regex,
        exclude_regex=args.exclude_regex,
        variables=args.variables,
    )
    errors = checker.main()
    checker.show_error_status()
    return errors


if __name__ == "__main__":
    sys.exit(main())
