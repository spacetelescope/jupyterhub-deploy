# ========================= vvvvv Custom  vvvvv =========================

ARG BASE_IMAGE
FROM $BASE_IMAGE AS build

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

COPY --chown=${NB_UID}:${NB_GID} env-frozen/ /opt/env-frozen/

# ----------------------------------------------------------------------
# Add jupyter-lab-extensions to base environment as well as standard packages.
# Performing common update here enables mission specific frozen spec.

RUN   /opt/common-scripts/install-common  base

# --------------------------- TESS -------------------------------------

COPY --chown=${NB_UID}:${NB_GID} environments/tess/*.yml /opt/environments/tess/
RUN /opt/common-scripts/env-conda tess

COPY --chown=${NB_UID}:${NB_GID} environments/tess/*.pip /opt/environments/tess/
RUN /opt/common-scripts/env-compile tess

RUN /opt/common-scripts/env-sync  tess

COPY --chown=${NB_UID}:${NB_GID} environments/tess/ /opt/environments/tess/

# ----------
# Due to numpy binary API incompatibilities and available compiled pip package versions
# Re-building from source ensures compatability with the installed numpy
# Install these BEFORE the packages which depend on them or you may get incompatible versions from PyPi

# batman-package
RUN  pip uninstall --yes batman-package && \
     /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/f3/33/3eda063897edb8bd267347da08a9874ddf77eea8244e91daa37411f8bc56/batman-package-2.4.8.tar.gz

# radvel
RUN pip uninstall --yes radvel  && \
    /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/d6/0c/7437ea1774f7edb78b291eac38c80361c5e5672ea8e56b28b0df416eee97/radvel-1.4.7.tar.gz

# juliet
RUN pip uninstall --yes juliet  && \
    /opt/common-scripts/env-src-install  tess  https://files.pythonhosted.org/packages/95/5c/2a97a352d0c4ba59a0decf06964f5660a13ac57004014a62fe4a9e2a891a/juliet-2.1.2.tar.gz

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
