# Copyright (c) Association of Universities for Research in Astronomy
# Distributed under the terms of the Modified BSD License.

FROM jupyter/scipy-notebook:a238993ad594
# See https://jupyter-docker-stacks.readthedocs.io/en/latest/using/selecting.html
# for a list of what comes with the base image
# python version is: 3.6.8

LABEL maintainer="Science Platforms <cslocum@stsci.edu>"

# Environment variables
ENV MKL_THREADING_LAYER="GNU"

# CRDS environment variables
ENV CRDS_PATH=/home/jovyan/crds_cache
ENV CRDS_SERVER_URL=https://jwst-serverless.stsci.edu
ENV CRDS_S3_ENABLED=1
ENV CRDS_S3_RETURN_URI=0
ENV CRDS_MAPPING_URI=s3://dmd-test-crds/mappings/jwst
ENV CRDS_REFERENCE_URI=s3://dmd-test-crds/references/jwst
ENV CRDS_CONFIG_URI=s3://dmd-test-crds/config/jwst
ENV CRDS_USE_PICKLES=0
ENV CRDS_DOWNLOAD_MODE=plugin
ENV CRDS_DOWNLOAD_PLUGIN='crds_s3_get ${SOURCE_URL} ${OUTPUT_PATH} ${FILE_SIZE} ${FILE_SHA1SUM}'

USER root

RUN apt-get update --yes > /dev/null && \
	apt-get install --yes curl rsync dbus-x11 firefox xfce4 xfce4-panel xfce4-session xfce4-settings xorg xubuntu-icon-theme automake libtool fftw3-dev libatlas-base-dev vim emacs gfortran

RUN mkdir /opt/bin && \
    wget https://github.com/astromatic/sextractor/archive/2.25.0.tar.gz && \
    tar xf 2.25.0.tar.gz && \
    cd sextractor-2.25.0 && \
    sh autogen.sh && \
    ./configure --prefix=/opt && \
    make && \
    make install

# Add kernel runner script that ensures conda environment is activated
COPY kernel_runner.py /opt

# Install base (common) environment
COPY base-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
conda env update --name base --file /opt/base-environment.yml

# Install wfirst-sit environment
#####################################################################
COPY wfirst-sit-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
    conda env create -f /opt/wfirst-sit-environment.yml && \
    conda activate wfirst-sit && \
    pip uninstall jwst -y && \
    pip install git+https://github.com/spacetelescope/jwst.git@0.15.0 && \
    conda deactivate

RUN mkdir -p $CONDA_DIR/envs/wfirst-sit/etc/conda/activate.d
COPY wfirst-sit-activate.sh $CONDA_DIR/envs/wfirst-sit/etc/conda/activate.d/activate.sh

RUN mkdir -p /usr/local/share/jupyter/kernels/wfirst-sit
COPY wfirst-sit-kernel.json /usr/local/share/jupyter/kernels/wfirst-sit/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/wfirst-sit
COPY logo-64x64.png /usr/local/share/jupyter/kernels/wfirst-sit

#####################################################################

# Install cvt environment
#####################################################################
#COPY cvt-environment.yml /opt

RUN . $CONDA_DIR/etc/profile.d/conda.sh && \
    conda create --name cvt && \
    conda activate cvt && \
    conda config --add channels http://ssb.stsci.edu/astroconda && \
    conda install ipykernel==4.8.2 --yes && \
    conda install jwst_coronagraph_visibility==0.4.2 --yes && \
    conda install matplotlib --yes && \
    conda install pysiaf --yes && \
    conda deactivate

RUN mkdir -p /usr/local/share/jupyter/kernels/cvt
COPY cvt-kernel.json /usr/local/share/jupyter/kernels/cvt/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/cvt
COPY logo-64x64.png /usr/local/share/jupyter/kernels/cvt
#####################################################################

# Install mirage environment
#####################################################################
COPY mirage-environment.yml /opt

RUN mkdir -p $CONDA_DIR/envs/mirage/etc/conda/activate.d
COPY mirage-activate.sh $CONDA_DIR/envs/mirage/etc/conda/activate.d/activate.sh

RUN mkdir -p /usr/local/share/jupyter/kernels/mirage
COPY mirage-kernel.json /usr/local/share/jupyter/kernels/mirage/kernel.json
COPY logo-32x32.png /usr/local/share/jupyter/kernels/mirage
COPY logo-64x64.png /usr/local/share/jupyter/kernels/mirage
#####################################################################

# Clone pandeia-coronagraphy to make the example notebooks available
RUN git clone https://github.com/spacetelescope/pandeia-coronagraphy /opt/pandeia-coronagraphy
COPY update_notebook_kernel.py /opt
RUN find /opt/pandeia-coronagraphy/notebooks/ -name '*.ipynb' -exec /opt/update_notebook_kernel.py {} \
    '{"display_name": "WFIRST", "language": "python", "name": "wfirst-sit"}' \;

# Setup a notebook start hook that populates the home directory.  We do this in a roundabout
# way because the EFS mount isn't available until the server actually starts in the cluster.
RUN mkdir -p /usr/local/bin/start-notebook.d
COPY apply_home_template.sh /usr/local/bin/start-notebook.d
COPY home_template /opt/home_template

RUN jupyter labextension install jupyterlab-server-proxy

# Add content to the global bashrc
COPY global_bashrc /home/jovyan
RUN cat /home/jovyan/global_bashrc >> /etc/bash.bashrc && \
    rm /home/jovyan/global_bashrc

# Keep Xfce directories out of home and set up shortcuts for DS9 and CVT.
COPY user-dirs.defaults /etc/xdg/user-dirs.defaults

# Clean out the home directory so it mimics a fresh EFS mount (useful for developer testing)
#RUN rm -rf /home/jovyan/*
#RUN rm -r /home/jovyan/.[a-zA-Z_]*

COPY VERSION /opt

USER $NB_UID
