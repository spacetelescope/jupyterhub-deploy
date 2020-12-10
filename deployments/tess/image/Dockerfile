# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

ARG USE_FROZEN=1
ENV USE_FROZEN=$USE_FROZEN

# ----------------------------------------------------------------------
# Install environments

USER ${NB_UID}

# TESS
COPY environments/tess/ /opt/environments/tess
RUN /opt/common-scripts/env-clone  base  tess
# RUN /opt/common-scripts/env-create  tess /opt/environments/tess/tess.yml
RUN /opt/common-scripts/install-common tess
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/tess.pip

# ----------------------------------------------------------------------
USER $NB_UID

RUN /opt/common-scripts/kernel-setup

# ---------------------------------------------------------------
# VARTOOLS Light Curve Analysis Program
USER root
RUN curl --silent --show-error https://www.astro.princeton.edu/~jhartman/vartools/vartools-1.38.tar.gz -o vartools-1.38.tar.gz && \
   tar zxf vartools-1.38.tar.gz &&\
   cd vartools-1.38 &&\
   mkdir -p /usr/local &&\
   ./configure --prefix=/use/local &&\
   make &&\
   make install &&\
   cd .. &&\
   rm -rf vartools-1.38 vartools-1.38.tar.gz

# ----------------------------------------------------------------------
USER root
RUN mkdir /opt/tessworkshop_tutorials
RUN chmod 777 /opt/tessworkshop_tutorials

RUN mkdir /opt/notebooks
RUN chmod 777 /opt/notebooks

USER $NB_UID
RUN git clone https://github.com/spacetelescope/tessworkshop_tutorials.git /opt/tessworkshop_tutorials
RUN git clone https://github.com/spacetelescope/notebooks.git /opt/notebooks

# ========================= ^^^^^ Custom  ^^^^^ =========================
# ========================= vvvvv Generic vvvvv  =========================

# As part of Dockerfile.trailer,  these statements are executed from the
# perspective of the deployment image directory,  not common.

USER root

# Copy everything now that build is complete and cache busting wont occur
COPY environments/    /opt/environments

# ----------------------------------------------------------------------

# remove this step once nbgitpuller enabled; these contents will be in the
#  jupyterhub-user-content repo.   Install deployment-specific $HOME files.
COPY default-home-contents/  /etc/default-home-contents

COPY global_bashrc  /home/jovyan
RUN  cat /home/jovyan/global_bashrc   >> /etc/bash.bashrc  && \
     rm /home/jovyan/global_bashrc

# Fix certs in conda for application level SSL, e.g. pass image-test running on CI-node
RUN /opt/common-scripts/fix-certs

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.
RUN cp -r /etc/default-home-contents/* /home/jovyan && \
    fix-permissions  /home/jovyan  &&\
    fix-permissions  /opt/environments

USER $NB_USER
WORKDIR /home/$NB_USER

CMD [ "start-notebook.sh" ]
