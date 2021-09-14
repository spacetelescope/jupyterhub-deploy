
## STScI JupyterHub Science Platforms

### Overview
The Space Telescope Science Institute ([STScI](https://www.stsci.edu/)) provides JupyterHub-based science platforms for community use.  These web-based platforms offer software and tools to perform analysis and processing of astronomical data, as well as easy access to multi-mission data archives.

The code in this repository does not include an installable package, but rather a collection of tools, Docker image configurations, Helm charts, and tests.

Much of the content here is derived from the [Zero-to-JupyterHub](https://zero-to-jupyterhub.readthedocs.io/en/latest) project.  The JupyterHub software is installed in a Kubernetes cluster on Amazon Web Services (AWS).  Terraform is used for cluster deployments - configurations can be found [here](https://github.com/spacetelescope/terraform-deploy).

### Usage

While this project is open source, many of the details of the underlying infrastructure are not available.  Sanitized deployment instructions [are available](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/DEPLOYMENT.md).

### License

BSD 3-Clause License

Copyright (c) 2021, Association of Universities for Research in Astronomy. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

- Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
- Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
- Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
