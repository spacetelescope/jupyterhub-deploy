# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

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

# ----------------------------------------------------------------------
# Add jupyter-lab-extensions to base environment as well as standard packages.
# Performing common update here enables mission specific frozen spec.

COPY --chown=${NB_UID}:${NB_GID} env-frozen/base/  /opt/env-frozen/base/
RUN   /opt/common-scripts/install-common  base

# --------------------------- Jwebbinar -------------------------------------

# BASE
COPY --chown=${NB_UID}:${NB_GID} env-frozen/jwebbinar/ /opt/env-frozen/jwebbinar/
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/*.yml /opt/environments/jwebbinar/
RUN /opt/common-scripts/env-conda jwebbinar

# COMPILE ALL
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/*.pip /opt/environments/jwebbinar/
RUN /opt/common-scripts/env-compile jwebbinar

# SYNC ALL
RUN /opt/common-scripts/env-sync  jwebbinar

# REMAINING ENV
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/ /opt/environments/jwebbinar/

# --------------------------- Jdaviz -------------------------------------

# Needed for cleaning up existing/obsolete kernel
COPY --chown=${NB_UID}:${NB_GID} environments/remove-jdaviz-kernel /opt/environments/

# --------------------------- Mirisim -------------------------------------

# BASE
COPY --chown=${NB_UID}:${NB_GID} env-frozen/mirisim/ /opt/env-frozen/mirisim/
COPY --chown=${NB_UID}:${NB_GID} environments/mirisim/*.yml /opt/environments/mirisim/
RUN /opt/common-scripts/env-conda mirisim

# COMPILE ALL
COPY --chown=${NB_UID}:${NB_GID} environments/mirisim/*.pip /opt/environments/mirisim/

# Mirisim pinned requirements conflict with /opt/common-env/jupyter.pip... so omit it
# and install everything else explicitly.
RUN /opt/common-scripts/env-compile mirisim  \
   /opt/common-env/common.pip \
   /opt/common-env/testing.pip \
   /opt/common-env/docs.pip

# SYNC ALL
RUN /opt/common-scripts/env-sync  mirisim

# Install from Mirisim conda server, strictly speaking, not frozen, always
# executes.  env-update would've been nicer/simpler but the package references
# in miricle-linux don't freeze.  Hence they need to be tacked onto the frozen
# build afterwards and env-update does nothing when USE_FROZEN=1.

RUN cd /opt/environments/mirisim && \
    wget https://jenkins.miricle.org/mirisim/stable/16/miricle-linux-py37.0.txt && \
    chmod +x miricle-linux-py37.0.txt && \
    /opt/common-scripts/env-run mirisim /opt/environments/mirisim/miricle-linux-py37.0.txt  &&\
    /opt/common-scripts/env-clean


# REMAINING ENV
COPY --chown=${NB_UID}:${NB_GID} environments/mirisim/ /opt/environments/mirisim/
# ========================= vvvvv Generic vvvvv  =========================

# Fix JS encoding issue that prevents widgets from displaying properly in notebook mode
# See https://github.com/jupyter/notebook/issues/6033 for details
RUN sed -i 's/data-base-url="{{base_url | urlencode}}"/data-base-url="{{base_url}}"/g' `ls -1 ${CONDA_DIR}/lib/python*/site-packages/notebook/templates/notebook.html`

# ----------------------------------------------------------------------

USER $NB_UID
RUN /opt/common-scripts/kernel-setup   # set up Ipython / JupyterLab kernels

# ----------------------------------------------------------------------
# As part of Dockerfile.trailer,  these statements are executed from the
# perspective of the deployment image directory,  not common.

USER root

RUN find /home/${NB_USER} ! -uid ${NB_UID} | xargs chown ${NB_UID}:${NB_GID}

# remove this step once nbgitpuller enabled; these contents will be in the
#  jupyterhub-user-content repo.   Install deployment-specific $HOME files.
COPY default-home-contents/ /etc/default-home-contents
RUN  cp -r /home/jovyan/.local /etc/default-home-contents && \
     cp -r /home/jovyan/.jupyter /etc/default-home-contents
COPY global_bashrc /home/jovyan
RUN  cat /home/jovyan/global_bashrc >> /etc/bash.bashrc  && \
     rm /home/jovyan/global_bashrc

# Fix certs in conda for application level SSL, e.g. pass image-test running on CI-node
RUN /opt/common-scripts/fix-certs

# Copy any remaining environments files not caught by more precise as-needed build copies
COPY --chown=${NB_UID}:${NB_GID} environments/    /opt/environments/

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.   post-start-hook may not include everything required
# for running on AWS,  just common functions needed for both AWS and standalone/CI.

USER $NB_USER
WORKDIR /home/$NB_USER

RUN /opt/environments/post-start-hook

CMD [ "start-notebook.sh" ]
