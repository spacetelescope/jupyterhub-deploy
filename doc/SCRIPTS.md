In the `tools` directory, there are a series of convenience scripts.


#### Image management scripts

Scripts have been added to the *tools* directory to simplify image development:

- image-build   -- build the Docker image defined by setup-env
- image-test    -- experimental,  run autmatic image tests.  requires added support in deployment
- image-push    -- push the built + tested Docker image to ECR at the configured tag
- image-sh      -- start a container running an interactive bash shell for poking around
- image-exec    -- start a container and run an arbitrary command
- image-all     -- build, test, and push the image.

**TODO**: update this list of scripts^^

Sourcing *setup-env* should add these scripts to your path, they require no parameters.

Using the scripts is simple, basically some iterative flow of:

```
# Update deployment Dockerfile in deployments/<your-deployment>/image.

# Build the Docker image
tools/image-build

# Run any self-tests defined for this deployment under deployments/<your-deployment>/image.
# Fix problems and re-build until working
tools/image-test

# Push the completed image to ECR for use on the hub,  proceed to Helm based JupyterHub deployment
tools/image-push
```

#### Scripts to automate ECR scan results

```
# Fetch results from ECR,  fetch Ubuntu CVE response status, print combined
# results as YAML
image-scan-report   <ubuntu version name sub-string>   <minimum severity level>    > report.yaml
image-scan-report   Focal   medium   >report.yaml

# Pull the most critical information from the scan report, CVE descriptions and related status
image-scan-summarize  report.yaml
```

You may need to install Python dependency before executing the *image-scan-xxx* scripts:
```
pip install --cert /etc/ssl/certs/ca-bundle.crt -r requirements.txt
```

#### Secrets convenience scripts

Once you've terraform'd your secrets repo and know your way around, these convenience scripts may help you check out and update your secrets based on your configured environment.

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
