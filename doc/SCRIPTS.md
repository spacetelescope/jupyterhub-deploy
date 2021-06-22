# In the `tools` directory, there are a series of convenience scripts.

#### Dependencies

In theory they're automatically installed on all new CI-nodes, but if not you
need to install Python dependencies before executing some of these scripts.

```
pip install --cert /etc/ssl/certs/ca-bundle.crt -r requirements.txt
```

#### Image management scripts

Scripts have been added to the *tools* directory to simplify image development:

- image-all     -- build, test, push, scan the image.
- image-build   -- build the Docker image defined by setup-env
- image-base    -- build base images with SSL certs + jupyter docker-stack / scipy-notebook
- image-update  -- as part of building, generate any required Dockerfiles, obtain current SSL certs, etc.
- docker-history -- print out the docker history,  identify layer sizes and associated build commands.

Automated testing:

- image-test    -- run automatic image tests on build image
- image-configure  -- generate setup-env for CI based on simple inputs
- image-scan    -- after pushing,  run this to download and examine ECR scan results

Interact with ECR to push images, pull images, and delete images:

- image-push    -- push the built image to ECR at the configured tag
- image-pull    -- pull the configured image tag from ECR to the local Docker
- image-delete  -- delete the specified image tags or digests from ECR, e.g. to ditch vulnerable images
- image-login   -- log in to ECR

Run a JH image in local Docker for inspection, development, debug:

- image-sh      -- start a container running an interactive bash shell for poking around
- image-root-sh -- start a container running an interactive bash shell as root
- image-exec    -- start a container and run an arbitrary command
- image-dev     -- start a container and map in Docker sources r/w for incremental install debug
- run-lab       -- start a JH server in Docker using the current image

Capture conda environment s/w versions (automatic w/ image-build):

- image-freeze     -- dump out frozen environment specs from the current image into deployments tree.
- image-env-list   -- run the image to list the names of conda environments
- image-env-export -- run the image to export the specified conda environment s/w versions

Sourcing *setup-env* should add these scripts to your path, they generally require no parameters.

Using the scripts is simple, basically some iterative flow of:

```
# Build the Docker image
image-build

# Run any self-tests defined for this deployment under deployments/<your-deployment>/image.
# Fix problems and re-build until working
image-test

# Push the completed image to ECR for use on the hub,  proceed to Helm based JupyterHub deployment
image-push

# Check the ECR scan report and report status and/or vulnerabilities
image-scan
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

# Run Python's safety package to check dependencies specified in frozen specs
# or requirements.txt for vulnerabilities
sscan-safety
```


#### Image Patching

Two initial high level scripts support image-patching:

- patch-os    -  Runs an OS upgrade script using patch-image
- patch-ssl   -  Updates the SSL cert using patch-image.

Both `patch-os` and `patch-ssl` are wrappers around `patch-image` which
performs the lower level aspects of the patch.

- patch-image -  Executes an arbitrary patch script to generate a new image

These scripts operate solely within the confines of Docker using the configured
image tag,  nominally "latest".

The scripts DO:

- Run the local source image and apply a patch script.
- Save metadata about the patch in the container's /opt/patches directory.
- Save container changes resulting from the patch script as a new image layer.
- Re-tag the patched image with the configured tag,  hi-jacking it.

The scripts *DO NOT*:

- Fetch the operational image from the repo to local Docker.  (see `image-pull`).
- Back up the repo's operational image.
- Test the patched image.   (see `image-test`)
- Push the patched image back to the repo.   (see `image-push`)
- Tag the source or patched image other than re-using the configured tag.
- Store history of the patch in git and/or github.
- Delete old untagged vulnerable images from the repo (see `image-delete`)

The `patch-os` script applies an OS upgrade script and creates a new image
from the result,  hijacking the configured tag.

```
patch-os   admin@your-org  [<description>]    [<source-image-hash>]
```

The `patch-ssl` script updates the SSL certs of the source image creating
a new image from the result,  hijacking the configured tag.

```
patch-ssl  admin@your-org  [<description>]    [<source-image-hash]
```

*NOTE:* Running `patch-os` may break the SSL certs installed by our build
process if e.g. Ubuntu updated certs.  In this case, or in the event of new
certs, `patch-ssl` is used to do the fix.

The `patch-image` script is used to create a new version of an image which
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
Ubuntu upgrde (`tools/apt-upgrade` used by `patch-os`), a script installing or
removing a package, etc.  The log from the patch script is captured and copied
into the patch.log file in the patch history directory inside the patch
container.

4. The patch container is used to generate a new version of the image using
`docker commit`.  This image only exists locally but is ready to be pushed to
ECR using `image-push`.  Run `image-test` before pushing back to ECR,  there
is no automatic CI as part of this process.

A full patch workflow might look like:

```
# Set up environment defining tagged operational ECR image $IMAGE_ID
source setup-env

# Clear out Docker so $IMAGE_ID is unequivocally coming from ECR
docker system prune -a

# Pull the operartional $IMAGE_ID image out of ECR for patching
image-pull

# Use and existing patch script (e.g. tools/apt-upgrade) or create a new one.

# Apply the patch script creating new version of $IMAGE_ID
patch-image   tools/apt-upgrade     admin@your-org   "Apply Ubuntu security updates."

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
docker system prune -a

# Pull the operartional $IMAGE_ID image out of ECR for inspection
image-pull

# Run a shell on the image and poke around
image-root-sh
cd /opt/patches/<src-image-hash>
cat metadata.yaml
...
```

**Patching NOTES:**

- `patch-image` should be used sparingly when the risk of accidentally breaking
an operational image functionally by rebuilding normally is unacceptable.
Example uses might be application of needed security updates or small
corrections or additions to conda environments applied to formal releases.

- As-is, this workflow is essentially replacing the operational image without
doing much external record keeping.  The new operational image records where it
came from and how in the /opt/patches/... history directories *inside* the
image.  Once the new image is pushed, the source image effectively becomes
anonymous unless tagged with a scheme outside this scope prior to patching and
pushing.

- Using `docker system prune -a` clears out Docker completely,  removing all images,
containers, and the build cache.

#### Prototype Image Squashing

There is a family of related scripts which implement a "lossless" compression
strategy by eliminating duplicate copies of files and other similar issues:

- squash              master script which will complete the entire process
                        relative to the current mission image.
- squash-crosslink    runs /opt/common/crosslink as a patch inside a container.
- squash-export       exports the patched multilayer docker image to an external archive file.
- squash-build-cmd    creates a docker import command which restores critical image
                        metadata obtained by running docker inspect on the original image.
- squash-import       runs the docker import command creating a new single layer image
                        based on the file system export archive and inspected metadata.

It works by:

1. Detecting duplicate files via sha1sum using /opt/common-scripts/crosslink on /opt/conda.

2. Replacing duplicate files with hard links to a master copy using /opt/common-scripts/crosslink.

3. The combined multilayer image file system is exported to an archive file using `docker export.`

4. Metadata from the original image is captured using `docker inspect.`

5. The `docker import` command is built referring to the export file and defining metadata.

6. The `docker import` command is run creating a new single layer image with restored metadata.

The script `/opt/common-scripts/crosslink` runs inside a container as a
patch script.  Paradoxically,  the new layer which hard links redundant files
can only add to the overall image size.

Once the image is crosslinked/patched, squashing all image layers into a single
layer eliminates buried redundancies,  deleted files, etc. finally reducing
overall size.

*Performance*

Crosslinking is surprisingly fast,  just a few minutes.

Running everything on the Tike DEV CI-node reduced the 21.1G image down to
15.8G in 15-20 min with the bulk of the time consumed by exporting and
re-importing.  An existing PyPi project I tried required 2 hours.

Extra disk space for the archive file is required, further limiting squash
for CI on GitHub.

