# Copyright (c) Association of Universities for Research in Astronomy
# Distributed under the terms of the Modified BSD License.

FROM jupyter/scipy-notebook:a238993ad594
# See https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html
# for a list of what comes with the base image
# python version is: 3.6.8

LABEL maintainer="Science Platforms <cbrasseur@stsci.edu>"

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# CRDS environment variables
ENV CRDS_PATH=/home/jovyan/crds_cache
ENV iref=${CRDS_PATH}/references/hst/iref/
ENV jref=${CRDS_PATH}/references/hst/jref/
ENV oref=${CRDS_PATH}/references/hst/oref/
ENV lref=${CRDS_PATH}/references/hst/lref/
ENV nref=${CRDS_PATH}/references/hst/nref/
ENV uref=${CRDS_PATH}/references/hst/uref/
ENV uref_linux=$uref
ENV CRDS_SERVER_URL=https://hst-serverless.stsci.edu
ENV CRDS_S3_ENABLED=1
ENV CRDS_S3_RETURN_URI=0
ENV CRDS_MAPPING_URI=s3://dmd-test-crds/mappings/hst
ENV CRDS_REFERENCE_URI=s3://dmd-test-crds/references/hst
ENV CRDS_CONFIG_URI=s3://dmd-test-crds/config/hst
ENV CRDS_USE_PICKLES=0
ENV CRDS_DOWNLOAD_MODE=plugin
ENV CRDS_DOWNLOAD_PLUGIN='crds_s3_get ${SOURCE_URL} ${OUTPUT_PATH} ${FILE_SIZE} ${FILE_SHA1SUM}'

USER root

RUN apt-get update --yes > /dev/null && \
    apt-get install --yes curl rsync

# Add kernel runner script that ensures conda environment is activated
COPY kernel_runner.py /opt

# Install hstdp conda environment
RUN conda create -n hstdp --file http://ssb.stsci.edu/releases/hstdp/2019.5/latest-linux

# Customize hstdp environment
RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
    conda activate hstdp && \
    # S3-enabled release of CRDS:
    pip install --upgrade git+https://github.com/spacetelescope/crds.git@7.4.1.4#egg=crds[aws] && \
    # Needed to use this environment as a kernel
    pip install ipykernel && notebook==5.7.8 nbgitpuller==0.7.2 nbresuse==0.3.2

# Create hstdp notebook kernel
RUN mkdir -p /usr/local/share/jupyter/kernels/hstdp
COPY hstdp-kernel.json /usr/local/share/jupyter/kernels/hstdp/kernel.json
COPY hstdp-logo-32x32.png /usr/local/share/jupyter/kernels/hstdp/logo-32x32.png
COPY hstdp-logo-64x64.png /usr/local/share/jupyter/kernels/hstdp/logo-64x64.png

# Add content to the global bashrc
COPY global_bashrc /home/jovyan
RUN cat /home/jovyan/global_bashrc >> /etc/bash.bashrc && \
    rm /home/jovyan/global_bashrc

# Clean out the home directory so it mimics a fresh EFS mount (useful for developer testing)
RUN rm -rf /home/jovyan/*
RUN rm -r /home/jovyan/.[a-zA-Z_]*

COPY VERSION /opt

USER $NB_UID
