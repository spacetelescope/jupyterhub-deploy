

# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

ARG USE_FROZEN=1
ENV USE_FROZEN=$USE_FROZEN

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
# Install environments

USER ${NB_UID}

# All specs for frozen builds need to be available before their normal installs
COPY --chown=${NB_UID}:${NB_GID} environments/frozen/  /opt/environments/frozen

# Roman CAL
COPY --chown=${NB_UID}:${NB_GID} environments/roman-cal/ /opt/environments/roman-cal
# RUN /opt/common-scripts/env-clone base roman-cal   # too many conflicts
RUN /opt/common-scripts/env-create  roman-cal /opt/environments/roman-cal/roman-cal.yml
RUN /opt/common-scripts/install-common roman-cal
RUN /opt/common-scripts/env-update  roman-cal /opt/environments/roman-cal/roman-cal.pip
RUN /opt/common-scripts/env-update  roman-cal /opt/environments/roman-cal/octarine.pip

# MIRAGE
COPY --chown=${NB_UID}:${NB_GID} environments/mirage/ /opt/environments/mirage
# RUN /opt/common-scripts/env-create  mirage /opt/environments/mirage/mirage.yml
RUN /opt/common-scripts/env-clone base mirage
RUN /opt/common-scripts/env-update  mirage /opt/environments/mirage/mirage.pip
RUN /opt/common-scripts/install-common mirage

# CVT
COPY --chown=${NB_UID}:${NB_GID} environments/cvt/ /opt/environments/cvt
RUN /opt/common-scripts/env-clone  base   cvt
# RUN /opt/common-scripts/env-create  cvt /opt/environments/cvt/cvt.yml
RUN /opt/common-scripts/install-common cvt

# ----------------------------------------------------------------------
USER root

# Get webbpsf-data-0.9.0.tar.gz
RUN mkdir /data && cd /data && \
    wget --quiet https://stsci.box.com/shared/static/qcptcokkbx7fgi3c00w2732yezkxzb99.gz
RUN cd /data && tar zxf qcptcokkbx7fgi3c00w2732yezkxzb99.gz && \
    rm qcptcokkbx7fgi3c00w2732yezkxzb99.gz && chmod -R a+r /data/webbpsf-data

# Install sextractor under /usr/local
RUN cd /tmp && \
    curl -sSL https://github.com/astromatic/sextractor/archive/2.25.0.tar.gz | tar -xzf - && \
    cd sextractor-2.25.0 && \
    sh autogen.sh && \
    ./configure --prefix=/usr/local && \
    make && \
    make install

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

#  &&\
#    fix-permissions  /opt/environments     # Docker cache buster?

CMD [ "start-notebook.sh" ]
