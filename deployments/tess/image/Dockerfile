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
RUN /opt/common-scripts/env-create  tess /opt/environments/tess/tess.yml
RUN /opt/common-scripts/install-common tess
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/tess.pip

# ----------------------------------------------------------------------
USER $NB_UID

RUN /opt/common-scripts/kernel-setup

# Drop kernels not explicitly defined by us,  those preceded with conda-
RUN jupyter kernelspec list | grep conda\- | awk '{print $1;}' | xargs jupyter kernelspec remove -f

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

USER root

COPY test /opt/test

# ----------------------------------------------------------------------

RUN cat /opt/common-scripts/global_bashrc >> /etc/bash.bashrc

# RUN chown -R ${NB_UID}.${NB_UID} /opt/environments
RUN  fix-permissions  /opt/environments

USER $NB_USER
WORKDIR /home/$NB_USER

# remove this step once nbgitpuller enabled; these contents will be in the jupyterhub-user-content repo
COPY default-home-contents/ /etc/default-home-contents/

COPY default-home-contents/ /home/jovyan

# FROM scratch
# COPY --from=build /  /



CMD [ "start-notebook.sh" ]
