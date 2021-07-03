# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

ARG USE_FROZEN=1
ENV USE_FROZEN=$USE_FROZEN

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
# Install environments

USER ${NB_UID}

# This enables installation of ALL frozen environments and needs to be at the top
COPY --chown=${NB_UID}:${NB_GID}  environments/frozen/  /opt/environments/frozen

# --------------------------- TESS -------------------------------------
# ---- RUN /opt/common-scripts/env-clone  base  tess &&\
# ----     /opt/common-scripts/env-update tess /opt/environments/tess/tess.yml  &&\

COPY --chown=${NB_UID}:${NB_GID} environments/tess/tess.yml /opt/environments/tess/tess.yml
RUN /opt/common-scripts/env-create  tess /opt/environments/tess/tess.yml

RUN /opt/common-scripts/install-common tess

# ---------- supplies key build tools (cython, etc) which should potentially be common
COPY --chown=${NB_UID}:${NB_GID} environments/tess/basic.pip  /opt/environments/tess/basic.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/basic.pip

# ----------
# Due to numpy binary API incompatibilities and available compiled pip package versions
# Re-building from source ensures compatability with the installed numpy
# Install these BEFORE the packages which depend on them or you may get incompatible versions from PyPi

# batman-package
RUN  /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/f3/33/3eda063897edb8bd267347da08a9874ddf77eea8244e91daa37411f8bc56/batman-package-2.4.8.tar.gz

# radvel
RUN  /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/ae/df/956dfd5f990869818dc98e7077e570e977380ee2e5e54dbf6ec456dfb6d0/radvel-1.4.6.tar.gz

# juliet
RUN  /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/95/5c/2a97a352d0c4ba59a0decf06964f5660a13ac57004014a62fe4a9e2a891a/juliet-2.1.2.tar.gz

# transitleastsquares
# RUN  /opt/common-scripts/env-src-install  tess https://files.pythonhosted.org/packages/76/e6/371cff7a236330c5893486ac7a208e55c52ba1463bfb9ecc96676b03b36f/transitleastsquares-1.0.28.tar.gz

# ----------

COPY --chown=${NB_UID}:${NB_GID} environments/tess/tess.pip  /opt/environments/tess/tess.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/tess.pip

COPY --chown=${NB_UID}:${NB_GID} environments/tess/ml.pip  /opt/environments/tess/ml.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/ml.pip

COPY --chown=${NB_UID}:${NB_GID} environments/tess/exoplanet.pip  /opt/environments/tess/exoplanet.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/exoplanet.pip

# ----------------------------------------------------------------------
COPY --chown=${NB_UID}:${NB_GID} environments/ /opt/environments

# ----------------------------------------------------------------------
# Run the hook script for updates which are common to both the standalone
# image and to hub cloud operation.
#
USER root
RUN chown -R ${NB_UID}:${NB_GID}  /home/${NB_USER}

# ========================= ^^^^^ Custom  ^^^^^ =========================
# ========================= vvvvv Generic vvvvv  =========================

# Fix JS encoding issue that prevents widgets from displaying properly in notebook mode
# See https://github.com/jupyter/notebook/issues/6033 for details
RUN sed -i 's/data-base-url="{{base_url | urlencode}}"/data-base-url="{{base_url}}"/g' `ls -1 ${CONDA_DIR}/lib/python*/site-packages/notebook/templates/notebook.html`

# ----------------------------------------------------------------------

USER $NB_UID
RUN /opt/common-scripts/kernel-setup   # set up Ipython / JupyterLab kernels

# As part of Dockerfile.trailer,  these statements are executed from the
# perspective of the deployment image directory,  not common.

USER root

# ----------------------------------------------------------------------

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

# This top level command runs unit tests for the image,  nominally import tests
# and notebook runs but it's an arbitrary bash script.
COPY --chown=${NB_UID}:${NB_GID} environments/test    /opt/environments/test

# Install security patches now that build is complete;  potentially this could be done sooner
# -- RUN apt-get update && \
# --     apt-get dist-upgrade --yes && \
# --     apt-get clean && \
# --     rm -rf /var/lib/apt/lists/*

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.   post-start-hook may not include everything required
# for running on AWS,  just common functions needed for both AWS and standalone/CI.

USER $NB_USER
WORKDIR /home/$NB_USER

RUN /opt/environments/post-start-hook

CMD [ "start-notebook.sh" ]
