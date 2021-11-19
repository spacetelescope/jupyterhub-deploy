#! /Usr/bin/env python

"""Check properties of Terraformed resources and/or JupyterHub to verify good deployment.
ignore the hub since it may not be delpoyed on the cluster yet.

check creation date
check for global hammer
check for datadog
"""

import sys
import os
import subprocess
import argparse
import re
import json

import yaml

TEST_SPEC = """
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
Groups:
  - group: Kubernetes Pods
    command: kubectl get pods -A -o wide
    parser: named_columns
    assertions:
    - name: All pods
      all: READY=='1/1' and STATUS=='Running' and RESTARTS=='0'
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
    command: kubectl get pods -A -o wide
    parser: named_columns
    assertions:
    - name: All pods
      all: READY=='1/1' and STATUS=='Running' and RESTARTS=='0'
    - name: Image puller
      ok_rows==1: NAMESPACE=='default' and 'continuous-image-puller' in NAME
    - name: Hub
      ok_rows==1: NAMESPACE=='default' and 'hub' in NAME
    - name: Proxy
      ok_rows==1: NAMESPACE=='default' and 'proxy' in NAME
    - name: User-scheduler
      ok_rows==2: NAMESPACE=='default' and 'user-scheduler' in NAME
    - name: User-placeholder
      ok_rows==1: NAMESPACE=='default' and 'user-placeholder' in NAME
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
      ok_rows==1:  "'roman-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1a' in LABELS"
    - name: Core us-east-1b
      ok_rows==1:  "'roman-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1b' in LABELS"
    - name: Core us-east-1c
      ok_rows==1:  "'roman-core' in LABELS and 't3.small' in LABELS and 'zone=us-east-1c' in LABELS"
    - name: Notebook nodes
      ok_rows>=1:  "'roman-notebook' in LABELS and 'r5.xlarge' in LABELS  and 'region=us-east-1' in LABELS"
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
      simple: "'{JH_HOSTNAME} is an alias for' in _"
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
"""  # noqa: E501


def convert_age(age_str):
    """Convert k8s abbreviated-style datetime str e.g. 14d2h to an integer."""
    age_str_org = age_str

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
    print(f"convert_age({repr(age_str_org)}) --> {repr(age_str)} --> {eval(age_str)}")
    return eval(age_str)


def aws_kv_dict(key_value_dict_list):
    """Convert AWS dict representation [{ 'Key':k, 'Value':v}, ...] to a Python dict."""
    return {item["Key"]: item["Value"] for item in key_value_dict_list}


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
        test_spec,
        output_file,
        input_file,
        verbose,
        groups_regex,
        variables,
    ):
        self._output_file = output_file
        self._input_file = input_file
        self._verbose = verbose
        self._groups_regex = groups_regex
        print("===> Loading test spec")
        self.loaded_spec = yaml.safe_load(test_spec)
        self.variables = (
            dict([var.split("=") for var in variables.split(",")]) if variables else []
        )
        self._outputs = {}
        self._errors = 0

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
    def builtin_functions(self):
        return dict(
            convert_age=convert_age,
            aws_kv_dict=aws_kv_dict,
        )

    @property
    def combined_environment(self):
        env = dict()
        env.update(self.spec_constants)
        env.update(self.spec_environment)
        env.update(self.variables)
        env.update(self.builtin_functions)
        return env

    def main(self):
        self.setup_outputs()
        for check in self.groups:
            if re.search(self._groups_regex, check["group"], re.IGNORECASE):
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

    def get_command_output(self, check):
        group = check["group"]
        if not self._input_file:
            command = check.get("command").format(**self.combined_environment)
            print("===> Fetching", repr(group), "with", repr(command))
            print("=" * 80)
            try:
                self._outputs[group] = run(command).strip()
            except Exception as exc:
                error = f"Command FAILED for '{group}': '{command}' : '{str(exc)}'"
                self.error(error)
                self._outputs[group] = error
        return self._outputs[group]

    def run_check(self, check):
        print("=" * 80)
        output = self.get_command_output(check)
        print(output)
        print("=" * 80)
        if self._output_file:
            return
        if not output.startswith("Command FAILED"):
            parser = globals()[f"parse_{check['parser']}"]
            namespaces = parser(output)
            assertions = check.get("assertions", [])
            self.check_assertions(check["group"], assertions, namespaces)
            if not assertions:
                print("======> No assertions defined.")

    def check_assertions(self, group, assertions, namespaces):
        for assertion in assertions:
            assertion = dict(assertion)
            name = assertion.pop("name")
            print("===> Checking", repr(group), ":", repr(name), ":", assertion)
            requirement, condition = list(assertion.items())[0]
            condition = condition.format(**self.combined_environment)
            if requirement == "simple":
                self.verify_simple(name, namespaces, condition)
            elif requirement.startswith(("ok_rows", "all")):
                self.verify_rows(name, namespaces, requirement, condition)
            else:
                raise ValueError(
                    f"Unhandled requirement: {requirement} for assertion: {assertion}"
                )
            print()

    def verify_rows(self, name, namespaces, requirement, condition):
        self.verbose(f"Checking '{name}': {repr(condition)}")
        rows = []
        for i, namespace in enumerate(namespaces):
            self.verbose(f"Checking '{name}' #{i} : {condition} ... ", end="")
            if self.eval_condition(name, namespace, condition):
                rows.append(namespace)
                self.verbose("OK")
            else:
                self.verbose("FAILED")
                self.verbose("Namespace:", namespace)
        if requirement == "all":
            requirement = f"ok_rows=={len(namespaces)}"
        if eval(requirement, {}, dict(ok_rows=len(rows))):
            print(f"===> OK overall '{name}'")
        else:
            self.error(f"overall '{name}'")
            self.verbose("Namespace:", namespace)

    def verify_simple(self, name, namespace, condition):
        if self.eval_condition(name, namespace, condition):
            print(f"===> OK '{name}'")
        else:
            self.error(f"'{name}'")
            self.verbose("Namespace:", namespace)

    def eval_condition(self, name, namespace, condition):
        namespace = dict(namespace)  # local no-side-effects copy
        namespace.update(self.combined_environment)
        return eval(condition, {}, namespace)

    def verbose(self, *args, **keys):
        if self._verbose:
            print(*args, **keys)

    def error(self, *args):
        self._errors += 1
        print("===> ERROR: ", *args)


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
    test_spec = open(args.test_spec).read().strip() if args.test_spec else TEST_SPEC
    checker = Checker(
        test_spec=test_spec,
        output_file=args.output_file,
        input_file=args.input_file,
        verbose=args.verbose,
        groups_regex=args.groups_regex,
        variables=args.variables,
    )
    errors = checker.main()
    if errors:
        print("Total Errors:", errors)
    else:
        print("No Errors Detected")
    return errors


if __name__ == "__main__":
    sys.exit(main())
