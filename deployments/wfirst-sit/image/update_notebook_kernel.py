#!/usr/bin/env python
from argparse import ArgumentParser
import os
import json


def parse_args():
    parser = ArgumentParser("update_notebook_kernel.py", description="update a notebook's kernel in-place")
    parser.add_argument("notebook_path", help="path to the notebook file")
    parser.add_argument("kernelspec", help="JSON kernelspec definition")
    return parser.parse_args()


def main():
    args = parse_args()

    assert os.path.isfile(args.notebook_path), "missing file at specified path"

    kernelspec = json.loads(args.kernelspec)
    with open(args.notebook_path) as f:
        notebook = json.loads(f.read())

    notebook["metadata"]["kernelspec"] = kernelspec

    with open(args.notebook_path, "w") as f:
        f.write(json.dumps(notebook, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
