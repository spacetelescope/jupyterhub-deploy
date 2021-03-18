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

# JWebbinar
COPY environments/jwebbinar/ /opt/environments/jwebbinar
RUN /opt/common-scripts/env-create jwebbinar /opt/environments/jwebbinar/jwebbinar.yml
RUN /opt/common-scripts/install-common jwebbinar
RUN /opt/common-scripts/env-update jwebbinar /opt/environments/jwebbinar/jwebbinar.pip

# ----------------------------------------------------------------------
# BUG: ds9 is installed in the jwebbinar kernel, but it's included also include in the
#      common image in it's own kernel.  To avoid cluttering up the Launcher tab,
#      remove the ds9 environment
RUN conda env remove --name ds9

#USER root
#RUN chmod +x /opt/conda/envs/jwebbinar/bin/ds9

# ----------------------------------------------------------------------
USER root

#RUN git clone https://github.com/glue-viz/bqplot-image-gl.git && \
#    cd bqplot-image-gl && \
#    pip install -e . && \
#    ${CONDA_DIR}/bin/jupyter nbextension install --py --symlink --sys-prefix bqplot_image_gl && \
#    ${CONDA_DIR}/bin/jupyter nbextension enable --py --sys-prefix bqplot_image_gl && \
#    rm -rf bqplot-image-gl

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

# Install additional lab and notebook extensions
USER ${NB_UID}
RUN jupyter nbextension install --py --sys-prefix widgetsnbextension && \
    jupyter nbextension enable --py --sys-prefix widgetsnbextension && \
    jupyter nbextension install --py --sys-prefix ipyevents && \
    jupyter nbextension enable --py --sys-prefix ipyevents && \
    jupyter nbextension install --py --sys-prefix ipyvuetify&& \
    jupyter nbextension enable --py --sys-prefix ipyvuetify && \
    jupyter labextension install @jupyterlab/server-proxy @jupyter-widgets/jupyterlab-manager@2 ipyevents bqplot bqplot-image-gl jupyter-vuetify && \
    jupyter lab build -y && \
    jupyter lab clean -y && \
    npm cache clean --force && \
    rm -rf "/home/${NB_USER}/.cache/yarn" && \
    rm -rf "/home/${NB_USER}/.node-gyp"

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

# For standalone operation outside JupyterHub,  note that  /etc also includes
# common home directory files.
RUN cp -r /etc/default-home-contents/* /home/jovyan && \
    fix-permissions  /home/jovyan  &&\
    fix-permissions  /opt/environments

# This top level command runs unit tests for the image,  nominally import tests
# and notebook runs but it's an arbitrary bash script.
COPY environments/test    /opt/environments/test

# Install security patches now that build is complete;  potentially this could be done sooner
RUN apt-get update && \
    apt-get dist-upgrade --yes && \
    apt-get clean

USER $NB_USER
WORKDIR /home/$NB_USER

CMD [ "start-notebook.sh" ]
