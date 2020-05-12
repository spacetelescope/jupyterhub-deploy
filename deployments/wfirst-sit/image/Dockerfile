# Copyright (c) Association of Universities for Research in Astronomy
# Distributed under the terms of the Modified BSD License.

FROM jupyter/scipy-notebook:a238993ad594
# See https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html
# for a list of what comes with the base image
# python version is: 3.6.8

LABEL maintainer="Science Platforms <cslocum@stsci.edu>"

# Use latest ubuntu from community maintained buildpack-deps
# https://hub.docker.com/_/buildpack-deps/
FROM buildpack-deps:bionic-scm

LABEL maintainer="Science Platforms <cslocum@stsci.edu>"

# We assume only one user per container, so make it unique
# UID matches GID
ARG NB_USER="jovyan"
ARG NB_UID="1000"

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# CRDS environment variables
ENV CRDS_PATH=/home/jovyan/crds_cache
ENV CRDS_SERVER_URL=https://jwst-serverless.stsci.edu
ENV CRDS_S3_ENABLED=1
ENV CRDS_S3_RETURN_URI=0
ENV CRDS_MAPPING_URI=s3://dmd-test-crds/mappings/jwst
ENV CRDS_REFERENCE_URI=s3://dmd-test-crds/references/jwst
ENV CRDS_CONFIG_URI=s3://dmd-test-crds/config/jwst
ENV CRDS_USE_PICKLES=0
ENV CRDS_DOWNLOAD_MODE=plugin
ENV CRDS_DOWNLOAD_PLUGIN='crds_s3_get ${SOURCE_URL} ${OUTPUT_PATH} ${FILE_SIZE} ${FILE_SHA1SUM}'

USER root

RUN apt-get update --yes > /dev/null && \
	apt-get install --yes curl rsync dbus-x11 firefox xfce4 xfce4-panel xfce4-session xfce4-settings xorg xubuntu-icon-theme automake libtool fftw3-dev libatlas-base-dev vim emacs gfortran

RUN mkdir /opt/bin && \
    wget https://github.com/astromatic/sextractor/archive/2.25.0.tar.gz && \
    tar xf 2.25.0.tar.gz && \
    cd sextractor-2.25.0 && \
    sh autogen.sh && \
    ./configure --prefix=/opt && \
    make && \
    make install

# Add kernel runner script that ensures conda environment is activated
COPY kernel_runner.py /opt

# Install base (common) environment
COPY base-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
conda env update --name base --file /opt/base-environment.yml

# Install wfirst-sit environment
#####################################################################
COPY wfirst-sit-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
    conda env create -f /opt/wfirst-sit-environment.yml && \
    conda activate wfirst-sit && \
    pip uninstall jwst -y && \
    pip install git+https://github.com/spacetelescope/jwst.git@0.15.0 && \
    conda deactivate

RUN mkdir -p $CONDA_DIR/envs/wfirst-sit/etc/conda/activate.d
COPY wfirst-sit-activate.sh $CONDA_DIR/envs/wfirst-sit/etc/conda/activate.d/activate.sh

RUN mkdir -p /usr/local/share/jupyter/kernels/wfirst-sit
COPY wfirst-sit-kernel.json /usr/local/share/jupyter/kernels/wfirst-sit/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/wfirst-sit
COPY logo-64x64.png /usr/local/share/jupyter/kernels/wfirst-sit

#####################################################################

# Install cvt environment
#####################################################################
#COPY cvt-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
    conda create --name cvt && \
    conda activate cvt && \
    conda config --add channels http://ssb.stsci.edu/astroconda && \
    conda install ipykernel==4.8.2 --yes && \
    conda install jwst_coronagraph_visibility==0.4.2 --yes && \
    conda install matplotlib --yes && \
    conda install pysiaf --yes && \
    conda deactivate

RUN mkdir -p /usr/local/share/jupyter/kernels/cvt
COPY cvt-kernel.json /usr/local/share/jupyter/kernels/cvt/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/cvt
COPY logo-64x64.png /usr/local/share/jupyter/kernels/cvt
#####################################################################

# Install mirage environment
#####################################################################
COPY mirage-environment.yml /opt

RUN mkdir -p $CONDA_DIR/envs/mirage/etc/conda/activate.d
COPY mirage-activate.sh $CONDA_DIR/envs/mirage/etc/conda/activate.d/activate.sh

RUN mkdir -p /usr/local/share/jupyter/kernels/mirage
COPY mirage-kernel.json /usr/local/share/jupyter/kernels/mirage/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/mirage
COPY logo-64x64.png /usr/local/share/jupyter/kernels/mirage
#####################################################################

# Clone pandeia-coronagraphy to make the example notebooks available
RUN git clone https://github.com/spacetelescope/pandeia-coronagraphy /opt/pandeia-coronagraphy
COPY update_notebook_kernel.py /opt
RUN find /opt/pandeia-coronagraphy/notebooks/ -name '*.ipynb' -exec /opt/update_notebook_kernel.py {} \
    '{"display_name": "WFIRST", "language": "python", "name": "wfirst-sit"}' \;

# Setup a notebook start hook that populates the home directory.  We do this in a roundabout
# way because the EFS mount isn't available until the server actually starts in the cluster.
RUN mkdir -p /usr/local/bin/start-notebook.d
COPY apply_home_template.sh /usr/local/bin/start-notebook.d
COPY home_template /opt/home_template

RUN jupyter labextension install jupyterlab-server-proxy

# Add content to the global bashrc
COPY global_bashrc /home/jovyan
RUN cat /home/jovyan/global_bashrc >> /etc/bash.bashrc && \
    rm /home/jovyan/global_bashrc

# Keep Xfce directories out of home and set up shortcuts for DS9 and CVT.
COPY user-dirs.defaults /etc/xdg/user-dirs.defaults

# Clean out the home directory so it mimics a fresh EFS mount (useful for developer testing)
#RUN rm -rf /home/jovyan/*
#RUN rm -r /home/jovyan/.[a-zA-Z_]*

COPY VERSION /opt

USER $NB_UID
ENV CRDS_PATH=/home/jovyan/crds_cache \
    CRDS_SERVER_URL=https://jwst-serverless.stsci.edu \
    CRDS_S3_ENABLED=1 \
    CRDS_S3_RETURN_URI=0 \
    CRDS_MAPPING_URI=s3://dmd-test-crds/mappings/jwst \
    CRDS_REFERENCE_URI=s3://dmd-test-crds/references/jwst \
    CRDS_CONFIG_URI=s3://dmd-test-crds/config/jwst \
    CRDS_USE_PICKLES=0 \
    CRDS_DOWNLOAD_MODE=plugin \
    CRDS_DOWNLOAD_PLUGIN='crds_s3_get ${SOURCE_URL} ${OUTPUT_PATH} ${FILE_SIZE} ${FILE_SHA1SUM}'

# ENV vars set in indiidual activate scripts previously
ENV MIRAGE_DATA=/data/mirage \
    PYSYN_CDBS=/data/pysynphot \
    WEBBPSF_PATH=/data/webbpsf \
    pandeia_refdata=/data/pandeia

# conda related env vars
ENV CONDA_DIR=/opt/conda
ENV SHELL=/bin/bash
ENV DEFAULT_ENV=default
ENV PATH=${CONDA_DIR}/bin:${CONDA_DIR}/envs/${DEFAULT_ENV}/bin:${PATH}

USER root

# Create user & group jovyan
RUN groupadd --gid ${NB_UID} ${NB_USER}
RUN useradd \
    --comment 'Jupyter container user' \
    --create-home \
    --no-log-init \
    --shell /bin/bash \
    --gid ${NB_UID} \
    --uid ${NB_UID} \
    ${NB_USER}

# Make /opt writeable by ${NB_USER}
RUN mkdir -p $(dirname ${CONDA_DIR}) && chown ${NB_USER}:${NB_USER} $(dirname ${CONDA_DIR})

USER ${NB_USER}

RUN curl -sSL https://repo.anaconda.com/miniconda/Miniconda3-4.7.12.1-Linux-x86_64.sh > /tmp/miniconda-installer.sh && \
    bash /tmp/miniconda-installer.sh  -b -p ${CONDA_DIR} && \
    conda clean -tipsy

USER root
# Load conda profile scripts by default
RUN ln -s ${CONDA_DIR}/etc/profile.d/conda.sh /etc/profile.d/conda.sh

# Install apt packages, without any questions asked
ENV TZ="America/New_York"
RUN apt-get update --yes > /dev/null && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install --yes \
        curl rsync locales tzdata \
        dbus-x11 firefox xfce4 xfce4-panel xfce4-session xfce4-settings xorg xubuntu-icon-theme \
        automake libtool fftw3-dev libatlas-base-dev build-essential make > /dev/null && \
    rm -rf /var/lib/apt/lists/*

# Set up locales, and default to UTF-8
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

# Install sextractor under /usr/local
RUN cd /tmp && \
    curl -sSL https://github.com/astromatic/sextractor/archive/2.25.0.tar.gz | tar -xzf - && \
    cd sextractor-2.25.0 && \
    sh autogen.sh && \
    ./configure --prefix=/usr/local && \
    make && \
    make install

USER ${NB_USER}
# Install environments one at a time!
# Base environment has JupyterLab & related packages
COPY environments/default.yml /tmp/default.yml
RUN conda env update --name default -f /tmp/default.yml && \
    conda clean -tipsy
# FIXME: This extension doesn't support current version of lab
# RUN ${CONDA_DIR}/envs/default/bin/jupyter labextension install jupyterlab-server-proxy


COPY environments/wfirst-sit.yml /tmp/wfirst-sit.yml
RUN conda env create -f /tmp/wfirst-sit.yml && \
    conda clean -tipsy

COPY environments/cvt.yml /tmp/cvt.yml
RUN conda env create -f /tmp/cvt.yml && \
    conda clean -tipsy

COPY environments/mirage.yml /tmp/mirage.yml
RUN conda env create -f /tmp/mirage.yml && \
    conda clean -tipsy


# # Add content to the global bashrc
# COPY global_bashrc /home/jovyan
# RUN cat /home/jovyan/global_bashrc >> /etc/bash.bashrc && \
#     rm /home/jovyan/global_bashrc

# Keep Xfce directories out of home and set up shortcuts for DS9 and CVT.
# COPY user-dirs.defaults /etc/xdg/user-dirs.defaults
