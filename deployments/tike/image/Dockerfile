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

COPY --chown=${NB_UID}:${NB_GID} environments/tess/basic.pip  /opt/environments/tess/basic.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/basic.pip

COPY --chown=${NB_UID}:${NB_GID} environments/tess/tess.pip  /opt/environments/tess/tess.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/tess.pip

# ----------
# juliet equires batman-package and radvel but as supplied by PyPi they are currently built with
# a version of numpy which is too agressive for the current exoplanet overall dependency solution.
# eventually these source installs should be reverted to standard pip installs as part of the juliet.pip
# package bundle.

RUN  /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/f3/33/3eda063897edb8bd267347da08a9874ddf77eea8244e91daa37411f8bc56/batman-package-2.4.8.tar.gz

RUN  /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/ae/df/956dfd5f990869818dc98e7077e570e977380ee2e5e54dbf6ec456dfb6d0/radvel-1.4.6.tar.gz

COPY --chown=${NB_UID}:${NB_GID} environments/tess/juliet.pip  /opt/environments/tess/juliet.pip
RUN /opt/common-scripts/env-update  tess /opt/environments/tess/juliet.pip

# COPY --chown=${NB_UID}:${NB_GID} environments/tess/ml.pip  /opt/environments/tess/ml.pip
# RUN /opt/common-scripts/env-update  tess /opt/environments/tess/ml.pip

# --------------------------- EXOPLANET -------------------------------------

COPY --chown=${NB_UID}:${NB_GID} environments/exoplanet/exoplanet.yml /opt/environments/exoplanet/exoplanet.yml
RUN /opt/common-scripts/env-create  exoplanet /opt/environments/exoplanet/exoplanet.yml

RUN /opt/common-scripts/install-common exoplanet

COPY --chown=${NB_UID}:${NB_GID} environments/exoplanet/basic.pip  /opt/environments/exoplanet/basic.pip
RUN /opt/common-scripts/env-update  exoplanet /opt/environments/exoplanet/basic.pip

COPY --chown=${NB_UID}:${NB_GID} environments/exoplanet/exoplanet.pip  /opt/environments/exoplanet/exoplanet.pip
RUN /opt/common-scripts/env-update  exoplanet /opt/environments/exoplanet/exoplanet.pip

COPY --chown=${NB_UID}:${NB_GID} environments/exoplanet/ml.pip  /opt/environments/exoplanet/ml.pip
RUN /opt/common-scripts/env-update  exoplanet /opt/environments/exoplanet/ml.pip

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
# common home directory files.   post-start-hook may not include everything required
# for running on AWS,  just common functions needed for both AWS and standalone/CI.

USER $NB_USER
WORKDIR /home/$NB_USER

RUN /opt/environments/post-start-hook

CMD [ "start-notebook.sh" ]
