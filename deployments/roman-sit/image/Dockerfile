# Use latest ubuntu LTS from community maintained buildpack-deps
# https://hub.docker.com/_/buildpack-deps/
FROM buildpack-deps:focal-scm

LABEL maintainer="Science Platforms <cslocum@stsci.edu>"

USER root
COPY ssl.pem /etc/ssl/certs/ssl.pem
RUN chmod 644 /etc/ssl/certs/ssl.pem
RUN update-ca-certificates

# We assume only one user per container, so make it unique
# UID matches GID
ARG NB_USER="jovyan"
ARG NB_UID="1000"

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# ENV vars set in individual activate scripts previously
ENV MIRAGE_DATA=/data/mirage \
    PYSYN_CDBS=/data/pysynphot \
    WEBBPSF_PATH=/data/webbpsf \
    pandeia_refdata=/data/pandeia

# conda related env vars
ENV CONDA_DIR=/opt/conda
ENV SHELL=/bin/bash
ENV PATH=${CONDA_DIR}/bin:${PATH}


USER root

# Create user & group jovyan
RUN groupadd --gid ${NB_UID} ${NB_USER}
RUN useradd \
    --comment 'Jupyter container user' \
    --create-home \
    --no-log-init \
    --shell /bin/bash \
    --gid ${NB_UID} \
    --uid ${NB_UID} \
    ${NB_USER}

# Make /opt writeable by ${NB_USER}
RUN mkdir -p $(dirname ${CONDA_DIR}) && chown ${NB_USER}:${NB_USER} $(dirname ${CONDA_DIR})

# Install apt packages, without any questions asked
RUN apt-get update --yes > /dev/null && \
    DEBIAN_FRONTEND=noninteractive \
    apt-get install --yes \
        curl rsync locales \
        dbus-x11 firefox xfce4 xfce4-panel xfce4-session xfce4-settings xorg xubuntu-icon-theme \
        automake libtool fftw3-dev libatlas-base-dev build-essential make vim emacs gfortran > /dev/null && \
    rm -rf /var/lib/apt/lists/*

# Set up locales, and default to UTF-8
RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

ENV LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

# Install sextractor under /usr/local
RUN cd /tmp && \
    curl -sSL --cacert /etc/ssl/certs/ssl.pem https://github.com/astromatic/sextractor/archive/2.25.0.tar.gz | tar -xzf - && \
    cd sextractor-2.25.0 && \
    sh autogen.sh && \
    ./configure --prefix=/usr/local && \
    make && \
    make install

USER ${NB_USER}

RUN curl -sSL --cacert /etc/ssl/certs/ssl.pem https://github.com/conda-forge/miniforge/releases/download/4.8.3-2/Miniforge3-4.8.3-2-Linux-x86_64.sh > /tmp/miniforge-installer.sh && \
    bash /tmp/miniforge-installer.sh  -b -p ${CONDA_DIR} && \
    conda clean -tipsy

RUN conda config --set ssl_verify /etc/ssl/certs/ssl.pem


USER root
# Load conda profile scripts by default
RUN ln -s ${CONDA_DIR}/etc/profile.d/conda.sh /etc/profile.d/conda.sh

USER ${NB_USER}

# Install environments one at a time!
# Base environment has JupyterLab & related packages
COPY environments/base.yml /tmp/base.yml
RUN conda env update --name base -f /tmp/base.yml && \
    conda clean -tipsy

RUN ./${CONDA_DIR}/bin/activate base && \
    pip install --cert /etc/ssl/certs/ssl.pem nbgitpuller && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/yuvipanda/jupyter-desktop-server@daecbdbbf89003a1d71fa03f362682a886bb3ad7 && \
    pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/yuvipanda/jupyter-desktop-server && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/yuvipanda/jupyter-server-proxy && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/yuvipanda/jupyter-rsession-proxy && \
    ./${CONDA_DIR}/bin/deactivate


# BUG: cannot install this...

#RUN ${CONDA_DIR}/bin/jupyter labextension install @jupyterlab/server-proxy
#RUN ${CONDA_DIR}/bin/jupyter labextension install jupyterlab-server-proxy

#RUN git config --global http.sslVerify false
#RUN npm config set strict-ssl false

#RUN cd /tmp/ && \
    #git clone --depth 1 https://github.com/jupyterhub/jupyter-server-proxy && \
#    git clone https://github.com/jupyterhub/jupyter-server-proxy && \
#    cd jupyter-server-proxy/jupyterlab-server-proxy && \
#    npm install && npm run build && jupyter labextension link . && \
#    npm run build && jupyter lab build


COPY environments/roman-sit.yml /tmp/roman-sit.yml
RUN conda env create -f /tmp/roman-sit.yml && \
    conda clean -tipsy


#RUN ./${CONDA_DIR}/bin/activate roman-sit && \
    #pip install --cert /etc/ssl/certs/ssl.pem setuptools==42 && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/spacetelescope/jwst.git && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/spacetelescope/crds.git@7.4.1.2#egg=crds[aws] && \
    #pip install --cert /etc/ssl/certs/ssl.pem astroquery && \
    #pip install --cert /etc/ssl/certs/ssl.pem jwst-backgrounds==1.1.1 && \
    #pip install --cert /etc/ssl/certs/ssl.pem pandeia-engine==1.5 && \
    #pip install --cert /etc/ssl/certs/ssl.pem git+https://github.com/spacetelescope/pandeia-coronagraphy.git@1d5ad4c &&\
    #./${CONDA_DIR}/bin/deactivate



#COPY environments/cvt.yml /tmp/cvt.yml
#RUN conda env create -f /tmp/cvt.yml && \
#    conda clean -tipsy

#COPY environments/mirage.yml /tmp/mirage.yml
#RUN conda env create -f /tmp/mirage.yml && \
#    conda clean -tipsy



# remove this step once nbgitpuller enabled; these contents will be in the jupyterhub-user-content repo
COPY default-home-contents/ /etc/default-home-contents/

# Keep Xfce directories out of home and set up shortcuts for DS9 and CVT.
COPY user-dirs.defaults /etc/xdg/user-dirs.defaults

WORKDIR /home/jovyan
