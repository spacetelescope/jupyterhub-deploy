
## STScI JupyterHub Science Platforms

### Overview
The Space Telescope Science Institute ([STScI](https://www.stsci.edu/)) provides JupyterHub-based science platforms for community use.  These web-based platforms offer software and tools to perform analysis and processing of astronomical data, as well as easy access to multi-mission data archives.

The code in this repository does not include an installable package, but rather a collection of tools, Docker image configurations, Helm charts, and tests.

Much of the content here is derived from the [Zero-to-JupyterHub](https://zero-to-jupyterhub.readthedocs.io/en/latest) project.  The JupyterHub software is installed in a Kubernetes cluster on Amazon Web Services (AWS).  Terraform is used for cluster deployments - configurations can be found [here](https://github.com/spacetelescope/terraform-deploy).

### Usage

While this project is open source, many of the details of the underlying infrastructure are not available.  Sanitized deployment instructions [are available](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/DEPLOYMENT.md).

### License
...

### TODO
Disclaimers, credits, contact info
