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

# This is a cache buster when environment freezing creates new specs, so Docker
# build will back up to this point.  Consequently, image build uses git to
# clear the new specs, they should be committed to git prior to attempting a
# new frozen build.
COPY --chown=${NB_UID}:${NB_GID} environments/frozen /opt/environments/frozen

# --------------------------- Jwebbinar -------------------------------------

# BASE
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/*.yml /opt/environments/jwebbinar/
RUN /opt/common-scripts/env-conda jwebbinar

# COMPILE ALL
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/*.pip /opt/environments/jwebbinar/
COPY --chown=${NB_UID}:${NB_GID} environments/jwebbinar/requirements.txt /opt/environments/jwebbinar/
RUN /opt/common-scripts/env-compile jwebbinar

# SYNC ALL
RUN /opt/common-scripts/env-sync  jwebbinar

# --------------------------- Jdaviz -------------------------------------

# BASE
COPY --chown=${NB_UID}:${NB_GID} environments/jdaviz/*.yml /opt/environments/jdaviz/
RUN /opt/common-scripts/env-conda jdaviz

# COMPILE ALL
COPY --chown=${NB_UID}:${NB_GID} environments/jdaviz/*.pip /opt/environments/jdaviz/
COPY --chown=${NB_UID}:${NB_GID} environments/jdaviz/requirements.txt /opt/environments/jdaviz/
RUN /opt/common-scripts/env-compile jdaviz

# SYNC ALL
RUN /opt/common-scripts/env-sync  jdaviz
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

# ------------------------------------------------------------------------------
# Handle copying all of environments to /opt/environments,  particularly root level
# files like *test* and *post-startup-hook*.   Preserve any requirements files generated
# by conda and pip-tools.

# First save any /opt/environments files which have been updated,  particularly requirements
RUN  cd /opt/environments && tar cf /opt/env-requirements.tar .

# Copy any remaining environments files not caught by more precise as-needed build copies
# which avoid cache busting.  If ANYTHING in environments changes Docker will roll back
# at least this far.  Hence this COPY is not done earlier and just handles cleanup.
COPY --chown=${NB_UID}:${NB_GID} environments/    /opt/environments/

# Restore files which the build generated or modified,  wiped out by the COPY above.
RUN  cd /opt/environments && tar xf /opt/env-requirements.tar  &&  rm /opt/env-requirements.tar

# -----------------------------------------------------------------------------

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.   post-start-hook may not include everything required
# for running on AWS,  just common functions needed for both AWS and standalone/CI.

USER $NB_USER
WORKDIR /home/$NB_USER

RUN /opt/environments/post-start-hook

CMD [ "start-notebook.sh" ]
