# In the `tools` directory, there are a series of convenience scripts.

#### Dependencies

In theory they're automatically installed on all new CI-nodes, but if not you
need to install Python dependencies before executing some of these scripts.

```
pip install --cert /etc/ssl/certs/ca-bundle.crt -r requirements.txt
```

#### Image management scripts

Scripts have been added to the *tools* directory to simplify image development:

- image-build   -- build the Docker image defined by setup-env
- image-test    -- experimental,  run autmatic image tests.  requires added support in deployment
- image-push    -- push the built + tested Docker image to ECR at the configured tag
- image-sh      -- start a container running an interactive bash shell for poking around
- image-root-sh -- start a container running an interactive bash shell as root
- image-exec    -- start a container and run an arbitrary command
- image-all     -- build, test, and push the image.
- image-login   -- log in to ECR
- image-configure  -- set up for CI and/or local builds not pushed anywhere
- image-freeze  -- dump out frozen environment specs from the current image into deployments tree.
- image-update  -- as part of building, generate any required Dockerfiles, obtain current SSL certs, etc.

Sourcing *setup-env* should add these scripts to your path, they generally require no parameters.

Using the scripts is simple, basically some iterative flow of:

```
# Build the Docker image
tools/image-build

# Run any self-tests defined for this deployment under deployments/<your-deployment>/image.
# Fix problems and re-build until working
tools/image-test

# Push the completed image to ECR for use on the hub,  proceed to Helm based JupyterHub deployment
tools/image-push

# Check the ECR scan report and report status and/or vulnerabilities
tools/image-scan
```

#### Scripts to automate ECR scan results

Our ECR is currently terraform'ed to run the AWS image scanner whenever a new
image is pushed to the repo.

```
# One-stop ECR results check:  downloads results, follows up with Ubuntu, prints summary
image-scan

# Fetch results from ECR,  fetch Ubuntu CVE response status, print combined
# results as YAML
image-scan-report   <ubuntu version name sub-string>   <minimum severity level>    > report.yaml
image-scan-report   Focal   medium   >report.yaml

# Pull the most critical information from the scan report, CVE descriptions and related status
image-scan-summarize  report.yaml
```

#### Secrets convenience scripts

Once you've terraform'd your secrets repo and know your way around, these
convenience scripts may help you check out and update your secrets based on
your configured environment.

```
# Clone your code commit secrets repo.  Note that this repo should never be added directly to jupyterhub-deploy.
secrets-clone

# Edit your secrets:  decrypt, edit the secrets file,  commit any changes to the checkout.
secrets-edit

# Push your updated secrets  back to codecommit
secrets-push

# Fetch and print AWS session env variables needed to perform the codecommit
# clone and pushes.  Called automatically.
secrets-get-exports
```


#### CI Source Code Scanning Scripts

As part of CI we run source code scanners which check both our own Python code
and the Python dependencies in the mission images.  These scripts are
independent of the functional CI tests and do note require building an image
prior to running.

```
# One stop dev shopping,  run all source code scans on the current sources
sscan

# Run Python's bandit package on any discoverable Python code
sscan-bandit

# Run Python's safety package to check dependencies of the conda environments
# of the current image for vulnerabilities
sscan-safety
```


#### Image Patching

The `image-patch` script is used to create a new version of an image which
results from executing a caller-supplied script.  It basically works as
follows:

1. Unless overridden, the current image defined in setup-env is used as a
source image for the patch.  It is assumed that the source image is already
available locally.  See `docker-wipe` and `image-pull` for setting up Docker
using an existing image from ECR instead of doing a full build using
`image-build`.  Note that the tags are the same but a patch source image is in
some sense "old".  Throughout the patching process,  actions occur inside
a container started from this source image.

2. The /opt/patches/<source-image-hash> directory is used to hold history
metadata for this particular patch.  Multiple patches can be applied in
sequence and each patch will store metadata in a directory named for it's
source image.  The directory and file dates show the order of patching.
Metadata describing the source image, patch metadata and script, and patch log
are eventually stored here as part of the patched image.

3. The patch script is executed inside the container to do the real work of the
patch, leaving behind side effects in the current container's file system
layer.  These side effects need to be limited to the primary file system of the
container, i.e. no changes to extra volumes, etc. mounted inside the container.
The patch script can be anything executable, e.g. a bash script performing an
Ubuntu upgrde (`tools/apt-upgrade`), a script installing or removing a package,
etc.  The log from the patch script is captured and copied into the patch.log
file in the patch history directory inside the patch container.

4. The patch container is used to generate a new version of the image using
`docker commit`.  This image only exists locally but is ready to be pushed to
ECR using `image-push`.  Run `image-test` before pushing back to ECR,  there
is no automatic CI as part of this process.

A full patch workflow might look like:

```
# Set up environment defining tagged operational ECR image $IMAGE_ID
source setup-env

# Clear out Docker so $IMAGE_ID is unequivocally coming from ECR
docker-wipe

# Pull the operartional $IMAGE_ID image out of ECR for patching
image-pull

# Use and existing patch script (e.g. tools/apt-upgrade) or create a new one.

# Apply the patch script creating new version of $IMAGE_ID
image-patch   tools/apt-upgrade     jmiller@stsci.edu   "Apply Ubuntu security updates."

# Run CI tests on the patched image to make sure no disasters occurred
image-test

# Push the patched image back to ECR as same tag $IMAGE_ID
image-push

# Perform interactive notebook tests on the live hub
...
```

To investigate patches in an operational image something like the following
is in order:

```
# Set up environment defining tagged operational ECR image $IMAGE_ID
source setup-env

# Clear out Docker so $IMAGE_ID is unequivocally coming from ECR
docker-wipe

# Pull the operartional $IMAGE_ID image out of ECR for inspection
image-pull

# Run a shell on the image and poke around
image-root-sh
cd /opt/patches/<src-image-hash>
cat metadata.yaml
...
```

**Patching NOTES:**

- `image-patch` should be used sparingly when the risk of accidentally breaking
an operational image functionally by rebuilding normally is unacceptable.
Example uses might be application of needed security updates or small
corrections or additions to conda environments applied to formal releases.

- As-is, this workflow is essentially replacing the operational image without
doing much external record keeping.  The new operational image records where it
came from and how in the /opt/patches/... history directories *inside* the
image.  Once the new image is pushed, the source image effectively becomes
anonymous unless tagged with a scheme outside this scope prior to patching and
pushing.

- Using `docker-wipe` will destroy all existing images and containers in the
Docker environment in preparation for pulling down the operational image.
