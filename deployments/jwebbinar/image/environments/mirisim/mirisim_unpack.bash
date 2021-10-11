#! /bin/bash -eux

# This script is used to run excerpts from mirism_install.bash to download
# jupyterhub-deploy compatible package lists.  It needs to be run manually as
# part of kernel maintenance to update mirisim packages.  After downloading, it
# is likely some manual adjustments will be needed to handle conflicts with
# common packages.
#
# It should be noted that conda dependencies are for reference only, our
# install of mirisim uses mirisim.yml to define the mirisim conda environment.
#
# NOTE: pay careful attention to any differences in the mirisim_install.bash
# script that this script was excerpted from.  Changes there may require
# further changes here and/or in the Dockerfile.

flavor=stable
os=linux
version=`curl https://jenkins.miricle.org/mirisim/$flavor/buildNumbers | tail -1`
pythonVersion=37  # At this time,  packages are nevertheless built for 3.8

curl https://raw.githubusercontent.com/JWST-MIRI/mirisim-Install-Scripts/master/mirisim_install.bash  >mirisim_install.bash

curl  https://jenkins.miricle.org/mirisim/$flavor/$version/conda_python_$os-stable-deps.txt >conda_python_linux-stable-deps.txt

curl https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-deps.txt >miricle-linux-deps.txt.pip

#! This is also downloaded and installed in the Dockerfile.custom
curl https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-py$pythonVersion.0.txt > miricle-$os-py$pythonVersion.0.txt

git diff
