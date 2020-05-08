#!/bin/bash

sudo -u jovyan rsync -url /opt/home_template/ /home/jovyan/
sudo -u jovyan mkdir -p /home/jovyan/example_notebooks
sudo -u jovyan rsync -url /opt/pandeia-coronagraphy/notebooks/ /home/jovyan/example_notebooks/