# ================ vvvvv Generic Image vvvvv ==================

# Use latest ubuntu LTS from community maintained buildpack-deps
# https://hub.docker.com/_/buildpack-deps/
# FROM buildpack-deps:focal-scm AS build

FROM jupyter/scipy-notebook:42f4c82a07ff

# ------------------------------------------------------------------------

LABEL maintainer="Science Platforms <dmd_octarine@stsci.edu>"

# We assume only one user per container, so make it unique
# UID matches GID
# --- ARG NB_USER="jovyan"
# --- ARG NB_UID="1000"

# --- ENV NB_USER=$NB_USER
# --- ENV NB_UID=$NB_UID
# --- ENV NB_GID=$NB_UID

ARG USE_FROZEN=1
ENV USE_FROZEN=$USE_FROZEN

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# conda related env vars
ENV CONDA_DIR=/opt/conda
ENV SHELL=/bin/bash
ENV PATH=${CONDA_DIR}/bin:${PATH}

ENV REQUESTS_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
ENV CURL_CA_BUNDLE=/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

# ------------------------------------------------------------------------
USER root

# Install apt packages, without any questions asked

RUN    apt-get update --yes && \
       DEBIAN_FRONTEND=noninteractive apt-get install --yes \
        curl \
        wget \
        rsync \
        locales \
        less \
        ssh \
        htop \
        sysstat \
        imagemagick \
        \
        build-essential \
        gfortran \
        automake \
        libtool \
        make \
        vim \
        emacs-nox \
        fftw3-dev \
        libatlas-base-dev \
        libcurl4-openssl-dev \
        libxml2 \
        libxml2-dev \
        libxslt1.1 \
        libxslt1-dev \
        python-libxml2 \
        python-dev \
        python-setuptools \
        \
        dbus-x11 \
        firefox \
        xfce4 \
        xfce4-panel \
        xfce4-session \
        xfce4-settings \
        xorg \
        xubuntu-icon-theme \
        \
        file \
        libcfitsio-bin \
        libcfitsio-dev \
        apt-file \
        texlive-latex-recommended \
        cm-super \
        libxpa-dev \
        libxt-dev \
        && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ------------------------------------------------------------------------
# SSL/TLS cert setup for STScI AWS firewalling

USER root

RUN mkdir -p /etc/ssl/certs && \
    mkdir -p /etc/pki/ca-trust/extracted/pem
COPY tls-ca-bundle.pem /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem
RUN ln -s /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem  /etc/ssl/certs/ca-bundle.crt && \
    mv /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt.org && \
    ln -s /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem  /etc/ssl/certs/ca-certificates.crt && \
    mkdir -p /etc/pki/ca-trust/extracted/openssl

# ------------------------------------------------------------------------
USER root

# Load conda profile scripts by default,  symlink target doesn't exist for a bit
RUN ln -s ${CONDA_DIR}/etc/profile.d/conda.sh /etc/profile.d/conda.sh

USER ${NB_UID}
COPY base.yml /tmp/base.yml
RUN conda update --quiet --name base conda && \
    conda env update --name base -f /tmp/base.yml && \
    conda init --all     && \
    conda install --quiet conda-build && \
    conda build purge-all

USER root
RUN npm config set cafile /etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem

USER ${NB_UID}
RUN ${CONDA_DIR}/bin/jupyter labextension install @jupyterlab/server-proxy && \
    ${CONDA_DIR}/bin/jupyter nbextension enable --py --sys-prefix ipyevents && \
    jupyter lab build -y && \
    jupyter lab clean -y && \
    npm cache clean --force && \
    rm -rf "/home/${NB_USER}/.cache/yarn" && \
    rm -rf "/home/${NB_USER}/.node-gyp"

# ------------------------------------------------------------------------
# More SSL/TLS cert setup,  add server-proxy labextension

USER root

# Keep Xfce directories out of home and set up shortcuts for DS9 and CVT.
COPY user-dirs.defaults /etc/xdg/user-dirs.defaults

COPY common-scripts/ /opt/common-scripts
COPY common-env/ /opt/common-env
RUN cat /opt/common-scripts/global_bashrc >> /etc/bash.bashrc

USER ${NB_UID}
