
# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

# ----------------------------------------------------------------------

# All data is arranged  on /data opening up options for sharing a file system
ENV MIRAGE_DATA=/data/mirage \
    PYSYN_CDBS=/data/pysynphot \
    WEBBPSF_PATH=/data/webbpsf-data \
    pandeia_refdata=/data/pandeia

# ----------------------------------------------------------------------

ENV CRDS_PATH=/home/jovyan/crds_cache
ENV CRDS_SERVER_URL=https://jwst-crds.stsci.edu
ENV CRDS_VERBOSITY=20

# ----------------------------------------------------------------------
USER root

# ----------------------------------------------------------------------
# UNIX build unaffected by environments

# Get webbpsf-data-0.9.0.tar.gz
RUN mkdir /data && cd /data && \
    wget --quiet https://stsci.box.com/shared/static/qcptcokkbx7fgi3c00w2732yezkxzb99.gz
RUN cd /data && tar zxf qcptcokkbx7fgi3c00w2732yezkxzb99.gz && \
    rm qcptcokkbx7fgi3c00w2732yezkxzb99.gz && chmod -R a+r /data/webbpsf-data

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

# ------------------------------------------------------------------------------
# Install environments

# All specs for frozen builds need to be available before their normal installs
USER ${NB_UID}

COPY --chown=${NB_UID}:${NB_GID} environments/frozen/  /opt/environments/frozen

# --- # ------------------------------------------------------------------------------
# --- # MIRAGE
# --- # RUN /opt/common-scripts/env-create  mirage /opt/environments/mirage/mirage.yml
# --- RUN /opt/common-scripts/env-clone base mirage

# --- COPY --chown=${NB_UID}:${NB_GID} environments/mirage/mirage.pip /opt/environments/mirage/mirage.pip
# --- RUN /opt/common-scripts/env-update  mirage /opt/environments/mirage/mirage.pip

# --- RUN /opt/common-scripts/install-common mirage

# ------------------------------------------------------------------------------
# CVT

COPY --chown=${NB_UID}:${NB_GID} environments/cvt/*.yml  /opt/environments/cvt/
RUN /opt/common-scripts/env-conda cvt

COPY --chown=${NB_UID}:${NB_GID} environments/cvt/*.pip  /opt/environments/cvt/
COPY --chown=${NB_UID}:${NB_GID} environments/cvt/requirements.txt  /opt/environments/cvt/
RUN /opt/common-scripts/env-compile cvt

RUN /opt/common-scripts/env-sync cvt

COPY --chown=${NB_UID}:${NB_GID} environments/cvt/ /opt/environments/cvt/

# ----------------------------------------------------------------------
# Roman CAL

COPY --chown=${NB_UID}:${NB_GID} environments/roman-cal/*.yml  /opt/environments/roman-cal/
RUN /opt/common-scripts/env-conda roman-cal

COPY --chown=${NB_UID}:${NB_GID} environments/roman-cal/*.pip  /opt/environments/roman-cal/
COPY --chown=${NB_UID}:${NB_GID} environments/roman-cal/requirements.txt  /opt/environments/roman-cal/
RUN /opt/common-scripts/env-compile roman-cal

RUN /opt/common-scripts/env-sync roman-cal

COPY --chown=${NB_UID}:${NB_GID} environments/roman-cal/ /opt/environments/

# ========================= ^^^^^ Custom  ^^^^^ =========================
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

RUN chown -R ${NB_UID}:${NB_GID}  /home/${NB_USER}

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
