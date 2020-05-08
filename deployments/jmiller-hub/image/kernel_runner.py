#!/usr/bin/env python
"""
Run a notebook kernel in the specified conda environment, making sure
to activate the environment first.  Intended to be called from a kernel
spec JSON.
"""
import os
import sys


def main(env_name, connection_file):
    command = f". /opt/conda/bin/activate {env_name} && exec /opt/conda/envs/{env_name}/bin/python -m ipykernel_launcher -f {connection_file}"
    os.execvp("bash", ["bash", "-c", command])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
