#! /bin/bash -eux

# The script mirisim_install.bash is the standard mirisim install script which
# was unpacked to define most of the package lists here.

# These values were used to interpret statements in the mirisim_install.bash
# script to define concrete files to download.

flavor=stable
os=linux
version=`curl https://jenkins.miricle.org/mirisim/$flavor/buildNumbers | tail -1`
pythonVersion=37  # At this time,  packages are nevertheless built for 3.8


curl  https://jenkins.miricle.org/mirisim/$flavor/$version/conda_python_$os-stable-deps.txt >conda_python_linux-stable-deps.txt

curl https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-deps.txt >miricle-linux-deps.txt.pip

#! This is also downloaded and installed in the Dockerfile.custom
curl https://jenkins.miricle.org/mirisim/$flavor/$version/miricle-$os-py$pythonVersion.0.txt > miricle-$os-py$pythonVersion.0.txt
