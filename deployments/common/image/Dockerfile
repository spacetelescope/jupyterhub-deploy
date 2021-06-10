# ================ vvvvv Generic Image vvvvv ==================


# If the image (jupyter/scipy-notebook) exists locally it will be used,
# otherwise the latest from https://hub.docker.com/_/buildpack-deps will be used
FROM jupyter/scipy-notebook

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

# Enable easy swap of conda with e.g. mamba
ARG CONDA_VER=conda
ENV CONDA_VER=${CONDA_VER}

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# conda related env vars
ENV CONDA_DIR=/opt/conda
ENV SHELL=/bin/bash
ENV PATH=${CONDA_DIR}/bin:${PATH}
ENV CFLAGS="-fcommon"

# ------------------------------------------------------------------------
USER root

# Install apt packages, without any questions asked

RUN    apt-get update --yes && \
       DEBIAN_FRONTEND=noninteractive apt-get install --yes \
        tree \
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
        libbz2-dev \
        nvidia-cuda-toolkit \
        autocutsel \
        gedit \
	saods9 \
	net-tools \
        && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ------------------------------------------------------------------------
# This must be run after conda installs
RUN /opt/common-scripts/fix-certs

# ------------------------------------------------------------------------
# Remove light-locker to prevent screen lock
# BUG: get rid of --no-check-certificate
RUN wget https://sourceforge.net/projects/turbovnc/files/2.2.6/turbovnc_2.2.6_amd64.deb --no-check-certificate && \
    dpkg -i turbovnc_2.2.6_amd64.deb && \
    rm turbovnc_2.2.6_amd64.deb && \
    apt-get remove -y -q light-locker

# ------------------------------------------------------------------------
USER root

# Load conda profile scripts by default, symlink target doesn't exist for a bit
RUN ln -s ${CONDA_DIR}/etc/profile.d/conda.sh /etc/profile.d/conda.sh

# ------------------------------------------------------------------------
USER ${NB_UID}

COPY base.yml /tmp/base.yml
RUN ${CONDA_VER} update --quiet --name base conda && \
    ${CONDA_VER} env update --name base -f /tmp/base.yml && \
    ${CONDA_VER} init --all     && \
    ${CONDA_VER} install --quiet conda-build && \
    ${CONDA_VER} build purge-all

# ------------------------------------------------------------------------
USER root

# Keep Xfce directories out of home and set up shortcuts for DS9.
COPY user-dirs.defaults /etc/xdg/user-dirs.defaults

COPY common-scripts/ /opt/common-scripts
COPY common-env/ /opt/common-env
RUN cat /opt/common-scripts/global_bashrc >> /etc/bash.bashrc

# ----------------------------------------------------------------------
# Common conda environments
# USER ${NB_UID}
# COPY environments/ /opt/environments/

# ----------------------------------------------------------------------
# Set up astroquery and ds9 desktop short-cut, will be further
# augmented by specific deployments
USER ${NB_UID}
COPY default-home-contents/   /etc/default-home-contents

# ----------------------------------------------------------------------
# Add jupyter-lab-extensions to base environment as well as standard packages

RUN /opt/common-scripts/install-common  base
