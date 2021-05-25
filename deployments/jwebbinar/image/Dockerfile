# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

ARG USE_FROZEN=1
ENV USE_FROZEN=$USE_FROZEN

# ----------------------------------------------------------------------

# All data is arranged on /data opening up options for sharing a file system
ENV MIRAGE_DATA=/data/mirage \
    PYSYN_CDBS=/data/pysynphot \
    WEBBPSF_PATH=/data/webbpsf-data \
    pandeia_refdata=/data/pandeia

# ----------------------------------------------------------------------

ENV CRDS_PATH=/home/jovyan/crds_cache
ENV CRDS_SERVER_URL=https://jwst-crds.stsci.edu
# ENV CRDS_VERBOSITY=20    # 0 or missing for normal output,  -1 for no INFO,  50 for default DEBUG

# ----------------------------------------------------------------------
# Install non-environment packages early to avoid constant trailing rebuilds
# while working conda/pip dependency issues.
# BUG: we have no standard process for adding tests for these.

USER root

# Get webbpsf-data-0.9.0.tar.gz
RUN mkdir /data && cd /data && \
    wget --quiet https://stsci.box.com/shared/static/qcptcokkbx7fgi3c00w2732yezkxzb99.gz && \
    tar zxf qcptcokkbx7fgi3c00w2732yezkxzb99.gz && \
    rm qcptcokkbx7fgi3c00w2732yezkxzb99.gz && \
    chmod -R a+r /data/webbpsf-data

# Install sextractor under /usr/local
# NOTE: using master because this fix is required:
#       https://github.com/astromatic/sextractor/commit/46dd48faff6a7b59939096ba55e83e02e865ddfc
RUN cd /tmp && \
    wget https://github.com/astromatic/sextractor/archive/master.zip && \
    unzip master.zip && \
    cd sextractor-master && \
    sh autogen.sh && \
    ./configure --prefix=/usr/local && \
    make && \
    make install

# ----------------------------------------------------------------------
# Install environments

USER ${NB_UID}

# This is a cache buster when environment freezing creates new specs, so Docker
# build will back up to this point.  Consequently, image build uses git to
# clear the new specs, they should be committed to git prior to attempting a
# new frozen build.
COPY --chown=${NB_UID}:${NB_GID} environments/frozen /opt/environments/frozen

# ----------------------------------------------------------------------
# JWebbinar
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/ /opt/environments/jwebbinar
RUN /opt/common-scripts/env-create jwebbinar /opt/environments/jwebbinar/jwebbinar.yml
RUN /opt/common-scripts/install-common jwebbinar
RUN /opt/common-scripts/env-update jwebbinar /opt/environments/jwebbinar/jwebbinar.pip

RUN /opt/common-scripts/install-common jwebbinar

COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/ /opt/environments/jwebbinar

# ----------------------------------------------------------------------
# Jdaviz
COPY environments/jdaviz/jdaviz.yml /opt/environments/jdaviz/jdaviz.yml
RUN /opt/common-scripts/env-create jdaviz /opt/environments/jdaviz/jdaviz.yml
COPY environments/jdaviz/jdaviz.pip /opt/environments/jdaviz/jdaviz.pip
RUN /opt/common-scripts/env-update jdaviz /opt/environments/jdaviz/jdaviz.pip

RUN /opt/common-scripts/install-common jdaviz

COPY --chown=${NB_UID}:${NB_GID} environments/jdaviz/ /opt/environments/jdaviz

# ----------------------------------------------------------------------
USER root

# Install additional lab and notebook extensions
USER ${NB_UID}

COPY  --chown=${NB_UID}:${NB_GID} environments/setup-notebooks  /opt/environments
RUN  /opt/environments/setup-notebooks

# Fix JS encoding issue that prevents widgets from displaying properly in notebook mode
# See https://github.com/jupyter/notebook/issues/6033 for details
RUN sed -i 's/data-base-url="{{base_url | urlencode}}"/data-base-url="{{base_url}}"/g' ${CONDA_DIR}/lib/python3.8/site-packages/notebook/templates/notebook.html


# ========================= ^^^^^ Custom  ^^^^^ =========================
# ========================= vvvvv Generic vvvvv  =========================

# ----------------------------------------------------------------------
USER $NB_UID
RUN /opt/common-scripts/kernel-setup   # set up Ipython / JupyterLab kernels

# As part of Dockerfile.trailer,  these statements are executed from the
# perspective of the deployment image directory,  not common.

USER root

# ----------------------------------------------------------------------

# remove this step once nbgitpuller enabled; these contents will be in the
#  jupyterhub-user-content repo.   Install deployment-specific $HOME files.
COPY default-home-contents/  /etc/default-home-contents
RUN  cp -r /home/jovyan/.local /etc/default-home-contents && \
     cp -r /home/jovyan/.jupyter /etc/default-home-contents
COPY global_bashrc  /home/jovyan
RUN  cat /home/jovyan/global_bashrc >> /etc/bash.bashrc  && \
     rm /home/jovyan/global_bashrc

# Fix certs in conda for application level SSL, e.g. pass image-test running on CI-node
RUN /opt/common-scripts/fix-certs

# This top level command runs unit tests for the image,  nominally import tests
# and notebook runs but it's an arbitrary bash script.
COPY --chown=${NB_UID}:${NB_GID} environments/test    /opt/environments/test

# Install security patches now that build is complete;  potentially this could be done sooner
# -- RUN apt-get update && \
# --     apt-get dist-upgrade --yes && \
# --     apt-get clean && \
# --     rm -rf /var/lib/apt/lists/*

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.

RUN cp -r /etc/default-home-contents/* /home/jovyan && \
    fix-permissions  /home/jovyan

USER $NB_USER
WORKDIR /home/$NB_USER

CMD [ "start-notebook.sh" ]
