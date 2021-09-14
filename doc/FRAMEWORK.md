# Framework for JupyterHub Deployments and Testing

## Configuring your environment

Copy `setup-env.template` to setup-env and set the environment variables at
the top of the file to describe your deployment and images.

## Building Images

To factor out common features, the image has been partitioned into two separate
Docker builds: (1) a common base image shared by all missions providing a more
consistent environment across missions and (2) a mission specific image which
adds the specific software and dependencies required by that mission.

### Convenience scripts

- image-build   -  Build both common and mission images

- image-test    -  Run mission image tests in container using /opt/environments/test

- image-push    -  Push images to the configured repo

- image-all     -  Build, test, and push images if build and tests succeed

### Common Base Image

The common base image defines software and setup which is required by and shared
for all missions.  The common base image includes these parts:

1. A *Dockerfile* which defines the core Linux package set and base Jupyter environment,
extending the jupyter/scipy-notebook image.

2. A *common/image/common-scripts* directory which includes scripts used to standardize
installation and testing.   These run inside the container.

3. A *common/image/common-env* directory which defines packages which are nominally
installed in all conda environments by calling /opt/common-scripts/install-common.
Calling install-common is optional for each mission but some requirements (e.g.
installing papermill in the base environment) must be met somehow.   Note that this
facility augments builds where cloning the base environment is not feasible due to
version conflicts.

4. A *Dockerfile.trailer* file which represents the final steps required to prepare
a mission image.  As implemented this is just concatenated to a mission's Dockerfile.custom
to produce the mission image Dockerfile.

### Deployment/Mission Image

The mission image for each deployment is based on the common image and adds extra
software and setup unique to the mission:

1. `Dockerfile.custom` defines the core mission specific software setup.  For
roman this primarily consists of conda environment setups which are layered in
multiple pieces to support incremental development and Docker caching.  It also
includes classic UNIX packages setups.

2. The `environments` subdirectory defines conda environments.  Each
environment is given a subdirectory.  Within each environment, a `tests`
subdirectory defines tests for that environment.

3. An executable `test` script which defines arbitrary tests for the mission
which is ultimately installed at `/opt/test`.  Generally it will include a
command to execute tests for each environment in the standard way:
`/opt/common-scripts/test-environments`.

#### Conda Environment Definitions 1

*IMPORTANT:* This section documents our original conda environment build
process but is being supplanted by a newer process defined in the next section.
The frozen "dependency solutions" produced by this process are frequently not
reproducible.

Conda environments are also installed as jupyter kernels.  Seperate conda
environments support installation of s/w with conflicting dependencies and
rapid switching within a single jupyterlab session.

An example `roman-cal` environment is built with these Docker commands:

```
RUN /opt/common-scripts/env-clone base roman-cal
# RUN /opt/common-scripts/env-create  roman-cal /opt/environments/roman-cal/roman-cal.yml
RUN /opt/common-scripts/install-common roman-cal
RUN /opt/common-scripts/env-update  roman-cal /opt/environments/roman-cal/roman-cal.pip
RUN /opt/common-scripts/env-update  roman-cal /opt/environments/roman-cal/octarine.pip
```

As currently implemented `roman-cal` is cloned from the `base` environment supplied by
scipy-notebook;  this includes many generic compute and lab packages.   An alternative
method to cloning `base` is to create a new environment using a conda env YAML spec
and `env-create`;  this can be used to resolve package conflicts but is otherwise
undesirable as it forfeits base environment features which are not explicitly added
back in.

The `install-common` script installs generic packages defined by the common image into
all environments.  This may include several groups of packages which are installed from
independent spec files using nested  `env-update`'s.  The specs are nominally found
in deployments/common/image/common-env or /opt/common-env inside the image.

The fundamental calibration software for Roman is installed into `roman-cal`
using `env-update` and the `roman-cal.pip` list of pip packages.

Additional software not directly required by calibration is added as pip
packages using `env-update` and `octarine.pip`.

There should be only one `env-clone` or `env-create` command for each environment.  If
no .yml spec is given to `env-create` an empty default python environment is created.

`env-update` can add additional packages to an existing environment.
`env-update` can be called multiple times different kinds of package specs:
using conda environment `.yml` specs, lists of conda packages specified in
`xxxx.conda` files, or lists of pip packages specified in `xxxx.pip` files.  An
`xxxx.pip` file is basically identical to a `requirements.txt` file but
identifies that pip is required to install the package list.

In general the fewer packages specified in an conda .yml file the better, but
.yml files are useful for installing packages not supported by PyPi and for
performing auxilliary tasks like setting up conda channels.

##### Conda Environment Definitions 2

To address deficiencies with the original build framework (weak default
diagnostics, broken frozen builds), a second environment definition workflow
has been developed using pip-tools:

```
/opt/common-scripts/env-conda   <env>    # Create minimal conda environment.
/opt/common-scripts/env-compile <env>    # Resolve loose pip constraints to requirements.txt
/opt/common-scripts/env-sync    <env>    # Download and install requirements.txt
/opt/common-scripts/env-src-install  ... # Build packages with missing binaries from source.
...
```

These commands produce improved diagnostics relative to pip defaults and also
do a better job with frozen builds.  They compile loosely constrained conda or
pip requirements into fully pinned requirements.yml and requirements.txt.
Ultimately the complete environment is built with respect to those fully pinned
specs rather than on-th-fly dependency resolution.  The commands use the
existing environments .yml and .pip loosely constrainted pacakge spec files as
the seed for the full dependency solution.

#### Resolving Dependency Conflicts

Fundamentally, resolving dependency conflicts entails changing loose
requirements definitions as needed and recompiling the package version
solutions.   It's both a mathematically precise specification process,
and at the same time more of an art than a science.

##### Wrong Version of Python Supported

One particularly confusing dependency resolution problem occurs when a
particular x.y.z version of some package does exist, but not for the desired
Python version.  In this case pip can make it sound like version x.y.z doesn't
exist at all, but a quick visit to PyPi immediately contradicts pip: look,
x.y.z is right there!  Digging deeper by looking at file downloads on PyPi, one
may find that no distribution exists for the exact version of Python in the
target environment.  This problem can be resolved using `env-src-install` and
compiling a version for the target environment from source.

##### Incompatible Numpy ABI Used

A pernicious conflict occurs when an environment has pinned numpy for some
reason while numpy is in the process of undergoing an ABI change (Application
Binary Interface).  In this case, a package compiled for one version of numpy
won't work for versions of numpy with a different ABI.  Worse, this is only
detected on package import because PyPi has no mechanism to communicate which
ABI is being supported and can only distribute a package compiled for a single
ABI version.  Generally newly compiled pacakges on PyPi will track the new
numpy ABI version, while a back-pinned numpy uses the old ABI version by
definition.  Here again the solution is to re-compile new package sources
against the older installed numpy using `env-src-install`.

##### Dependency Maze

A network of dependency constraints on 5-6 interrelated packages can be
difficult to follow.  Fortunately, this is a common problem so tools have been
developed that can help out, particularly `pipdeptree`.  In cooperation with
`Graphviz`, `pipdeptree` can produce graphs of dependency relationships as .png
files which are annotated with version constraints.  This makes it easier to
see which constraints must be mutually satisfied.

The script `image-graph-env` is used to run `pipdeptree` as a container job
conveniently.  This is only useful for environments which build successfully
but fail to run correctly, and it further helps if packages in conflict can be
named precisely.  For environments which fail to build, output from
`env-compile` can often show the dependency conflicts causing the failure
instead but can be more difficult to understand.

#### Test Definitions

Standard test setup for each environment/<kernel>/tests can include:

1. An `imports` file which lists packages for which Python-importability should be
verified one per line.

2. A `notebooks` file which lists paths to test notebooks which should execute without
errors when run headless.

3. Individual .ipynb notebook files which should execute without errors when
run headless.

Additional files or subdirectories which will be installed along with the rest of the
environment/`kernel` files under `/opt/environments/<kernel>`.

By convention `imports` tests are defined statically as part of defining
required packages for each environment.  Failing imports imply the environment
is broken.

In contrast, the `notebooks` file is currently defined on the fly by the
`post-start-hook` script where the appropriate notebook kernel for each
notebook is also defined by running `set-notebook-kernels`.  Partly this is
because notebooks are defined independently of JupyterHub and are not intrinsic
to the kernel definitions,  partly it is because actual notebooks are not
available until `git-sync` is run to clone them by the `post-start-hook`.

Where defined, `notebooks-failing`, `long-notebooks`, and
`long-notebooks-failing` define notebook lists which are not executed by
default by CI (`image-test`).  These define notebooks with excessive runtime
and notebooks or persistent failures which haven't been addressed.  Like
`notebooks` all are created by the `post-start-hook` script.

### Running Tests

You can run tests locally using the script `image-test`.  The `image-test`
script launches a container from the local Docker build and then executes the
`/opt/environments/test` entry point.

There are additional common entry points which can be executed independently
for focusing on specific problems:

- `/opt/common-scripts/test-environments`

- `/opt/common-scripts/env-test <kernel>`

- `/opt/common-scripts/test-notebooks   <kernel>   <notebook .ipynb files...>`

- `/opt/common-scripts/test-imports  <kernel>  <pkgs to test imports for...>`

### Using image-dev to Debug

If you find yourself hating life because you're waiting an hour for a Docker
build after changing two lines of source, over-and-over, give image-dev a try.

The image-dev script runs an interactive bash shell inside a JH container to
let you debug environments, scripts, and tests.  The key behavior is that
image-dev mounts:

   common/image/common-scripts -->  /opt/common-scripts

   common/image/common-env     -->  /opt/common-env

   <mission>/image/environments --> /opt/environments

all as r/w inside the container.  This lets you edit files inside or outside
the container and immediately see the results in both contexts.  It enables you
make source changes and evaluate the effects in a high fidelity environment
without doing full Docker builds.

Because the sources are mounted r/w, when you are done editing and testing and
exit the container, changes are waiting for you ready to add and commit.

Note that if you modify test definitions by editing
/opt/environments/post-start-hook, you need to re-run it to regenerated
`notebooks` files.  Similarly, changing package definitions you need to
re-install those package lists prior to seeing the effects.

### Defining and Updating Frozen Images

Reproducing Docker images in a repeatable way requires freezing the versions of
important packages.  One method of reproducing a conda environment uses the
output from the `conda env export` command.  The output .yml defines conda
channels, conda package versions, and pip package versions.  In principle that
single environment file specifies everything needed to recreate a frozen
environment.  In practice, conda env exports may require manual version
tweaking before they can be used.

This framework introduces an approach for updating conda environments primarily
driven by the `USE_FROZEN` env var in setup-env:

1. Defining environment varaiable `USE_FROZEN=0` tells the environment setup
scripts to use floating dependency specs.  Frozen specs are ignored.  If the
build is successful,  and <env>-frozen.yml spec is automatically generated.

2. Defining environment variable `USE_FROZEN=1` tells environment setup scripts
to use <env>-frozen.yml to install a complete frozen conda environment.
Floating dependency specs are ignored in this mode.

`USE_FROZEN` is defined in `setup-env.template` as 1 forcing the use of a fully
pinned environment unless the developer chooses otherwise.

#### Kinds of environment spec files

Environments in this framework are specified using several kinds of files:

- <env>.yml    - is a conda environment spec which will define base packages for <env>.
  ideally this should be kept small.  this file should be used with `env-create` to initialize
  the environment, channels,  and critical conda packages.   (floating)

- *.yml        - additional conda env specs which should be added using `env-update` to modify
  the base environmment.  these can e.g. add additional channels  (floating)

- *.conda      - simple lists of conda packages, one per line, to add using `conda install`.  (floating)

- *.pip        - simple lists of pip packages,  one per line, to add using `pip install`. (floating)

- <env>-frozen.yml   - defines explicit versions for most/all of environment created using floating dependencies.   (frozen)

The environment is partitioned into multiple files because they may come from
different sources with a desire to be used as-is.  Additionally, it's good to
work on smaller groups of related packages if only to exploit Docker caching
and incremental install steps.

## Working with Secrets

Convenience scripts have been defined which automate various aspects of working
with the secrets repo.  There's no requirement to use them, but they document a
typical workflow with parameter free commands based on `setup-env`.

1. secrets-clone   - Makes an appropriate clone of the deployment's secrets repository,  first performing required authorization.  does not perform initial setup of secrets file or .sops.yaml.
2. secrets-edit    - Automates updating secrets once the clone has been properly initialized. Runs sops,  then automatically does `git add` and `git commit` if contents change.
3. secrets-push    - Pushes local secrets back up to the deployment repo.


## Deploying a Hub
