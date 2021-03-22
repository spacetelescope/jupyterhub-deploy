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
# Install non-environment packages early to avoid constant trailing rebuilds
# while working conda/pip dependency issues.
# BUG: we have no standard process for adding tests for these.

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

# ----------------------------------------------------------------------
# Install environments

USER ${NB_UID}

# This is a cache buster when environment freezing creates new specs, so Docker
# build will back up to this point.  Consequently image-update/image-build reverts
# the frozen specs whenever USE_FROZEN=0.  Note that since the specs aren't
# updated until a floating build is complete,  unless USE_FROZEN=1 the specs in
# the image don't reflect the as-built environment.
COPY environments/frozen /opt/environments/frozen

# ----------------------------------------------------------------------
# BUG: ds9 is installed in the jwebbinar kernel, but it's included also include in the
#      common image in it's own kernel.  To avoid cluttering up the Launcher tab,
#      remove the ds9 environment
RUN conda env remove --name ds9

#USER root
#RUN chmod +x /opt/conda/envs/jwebbinar/bin/ds9

# ----------------------------------------------------------------------
# JWebbinar
# --- COPY environments/jwebbinar/ /opt/environments/jwebbinar
# --- RUN /opt/common-scripts/env-create jwebbinar /opt/environments/jwebbinar/jwebbinar.yml
# --- RUN /opt/common-scripts/install-common jwebbinar
# --- RUN /opt/common-scripts/env-update jwebbinar /opt/environments/jwebbinar/jwebbinar.pip

# ----------------------------------------------------------------------
# Jdaviz
COPY environments/jdaviz/jdaviz.yml /opt/environments/jdaviz/jdaviz.yml
RUN /opt/common-scripts/env-create jdaviz /opt/environments/jdaviz/jdaviz.yml

COPY environments/jdaviz/jdaviz.pip /opt/environments/jdaviz/jdaviz.pip
RUN /opt/common-scripts/env-update jdaviz /opt/environments/jdaviz/jdaviz.pip

RUN /opt/common-scripts/install-common jdaviz

COPY environments/jdaviz/ /opt/environments/jdaviz

# ----------------------------------------------------------------------
USER root

#RUN git clone https://github.com/glue-viz/bqplot-image-gl.git && \
#    cd bqplot-image-gl && \
#    pip install -e . && \
#    ${CONDA_DIR}/bin/jupyter nbextension install --py --symlink --sys-prefix bqplot_image_gl && \
#    ${CONDA_DIR}/bin/jupyter nbextension enable --py --sys-prefix bqplot_image_gl && \
#    rm -rf bqplot-image-gl

# Install additional lab and notebook extensions
USER ${NB_UID}
RUN jupyter nbextension install --py --sys-prefix widgetsnbextension && \
    jupyter nbextension enable --py --sys-prefix widgetsnbextension && \
    jupyter nbextension install --py --sys-prefix ipyevents && \
    jupyter nbextension enable --py --sys-prefix ipyevents && \
    jupyter nbextension install --py --sys-prefix ipyvuetify&& \
    jupyter nbextension enable --py --sys-prefix ipyvuetify && \
    jupyter labextension install @jupyterlab/server-proxy @jupyter-widgets/jupyterlab-manager ipyevents bqplot bqplot-image-gl jupyter-vuetify && \
    jupyter labextension update --all && \
    #jupyter lab build -y && \
    jupyter lab clean -y && \
    npm cache clean --force && \
    rm -rf "/home/${NB_USER}/.cache/yarn" && \
    rm -rf "/home/${NB_USER}/.node-gyp"

RUN gitpuller https://github.com/spacetelescope/jwebbinar_prep test-env jwebbinar_prep
RUN /opt/common-scripts/set-notebook-kernel jdaviz jdaviz jwebbinar_prep/test_environment/*.ipynb

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
RUN  cp -r /home/jovyan/.local  /etc/default-home-contents && \
     cp -r /home/jovyan/.jupyter /etc/default-home-contents
COPY global_bashrc  /home/jovyan
RUN  cat /home/jovyan/global_bashrc   >> /etc/bash.bashrc  && \
     rm /home/jovyan/global_bashrc

# Fix certs in conda for application level SSL, e.g. pass image-test running on CI-node
RUN /opt/common-scripts/fix-certs

# This top level command runs unit tests for the image,  nominally import tests
# and notebook runs but it's an arbitrary bash script.
COPY environments/test    /opt/environments/test

# Install security patches now that build is complete;  potentially this could be done sooner
RUN apt-get update && \
    apt-get dist-upgrade --yes && \
    apt-get clean

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.
RUN cp -r /etc/default-home-contents/* /home/jovyan && \
    fix-permissions  /home/jovyan

USER $NB_USER
WORKDIR /home/$NB_USER

#  &&\
#    fix-permissions  /opt/environments     # Docker cache buster?

CMD [ "start-notebook.sh" ]
