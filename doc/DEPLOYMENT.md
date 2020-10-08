# Actions to take before deployment

**SSL certificates**

Put in a support ticket to obtain SSL certificates for the desired DNS name. You should be provided with a private key and a public certificate. _Make sure to put this request in early as it may take a while for ITSD to generate and provide them._

Note: if a DNS entry associated with the certificate is not made within a week, the certificate will be revoked.

**Gather platform requirements**

Get list of desired software/files/notebooks for Docker image. This may take a while because it involves iterating with scientists and stakeholders.

**Register client with MAST**

JupyterHub will need a client secret and ID to integrate with the MAST authentication service.  You will need to contact someone on the MAST team to request these credentials - they will generate and deploy them to the OAuth service.

Hold on to the secret and ID, they will be needed later in the deployment process.

Notes: 1) there is an ongoing conversation about which authentication method is most appropriate for JupyterHub, and 2) there is currently no formalized procedure for requesting these credentials.

# CI Node Setup

This section covers the process of setting up an EC2 instance on AWS that will be used for configuration and deployment.

### Create EC2 and login using ssh

**TODO: Pull this out into it's own doc; update to use Session Manager**
**NOTE: This section is completely out of date...***

Use the AWS EC2 Console to create a CI node where you'll deploy from.  The EC2 instance will be based on an AMI that contains software, tools, and configuration required for deployment.  Things like nodejs, helm3, awsudo, sops, docket, etc. are included.

- Base your EC2 on this AMI: **ami-01956bd49feb578e2**
- Instance type: **t3.xlarge**
- EBS storage: **150 GB**
- Security group: **institute-ssh-only**
- Tags: **Name = *your-username*-ci**
- From withing the ST network, connect to your CI node using ssh.  You can find your EC2 instance in the AWS console and copy the public IPv4 address, then issue this command:
  - `ssh ec2-user@<public-IPv4-address-for-you-ci-node>`

**attach the worker sg to your CI-node to give it access to the EKS Private API endpoint needed for Terraform to complete normally.***

**_Please remember to shut down the instance when not in use._**

# Start Docker

`sudo service docker start`

(this step will not be necessary once JUSI-419 has been implemented)

# Repository Overview

Installing JupyterHub requires working through a flow of several git repositories, in series, on your CI node:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/spacetelescope/terraform-deploy) | Creates an EKS cluster and roles used by the cluster, and CodeCommit and ECR repositories |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains JupyterHub deployment configurations for Docker images and tools to deploy JupyterHub to the EKS cluster.

# Set some convenience variables

To make things more convient for the rest of this procedure, set a few evironment variables.  This will reduce the need to modify copy/paste commands.

- `export ADMIN_ARN=arn:aws:iam::<account-id>:role/jupyterhub-admin`
- `export ACCOUNT_ID=account-id`
- `export DEPLOYMENT_NAME=deployment-name`

# Terraform-deploy

This section describes how to set up an EKS cluster and supporting resources using Terraform.

Get a copy of the repository with this command:

- `git clone --recursive https://github.com/spacetelescope/terraform-deploy`

### Setup CodeCommit repository for secrets and an ECR repository for Docker images

First, we will setup KMS and CodeCommit with the *kms-codecommit* Terraform module:

- `cd terraform-deploy/kms-codecommit`
- `terraform init`
- `cp your-vars.tfvars.example $DEPLOYMENT_NAME.tfvars`
- Update *deployment-name.tfvars* based on the templated values
- `awsudo $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve`

A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops) later in this procedure.

### Provision EKS cluster

Next, we will configure and deploy an EKS cluster and supporting resources needed to run JupyterHub with the *aws* Terraform module:

- `../aws`
- `terraform init`
- `cp your-cluster.tfvars.template to $DEPLOYMENT_NAME.tfvars`
- Update *deployment-name.tfvars* based on the templated values
- `awsudo $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve` (this will take a while...)

Finally, configure the local environment for the EKS cluster:

- `awsudo $ADMIN_ARN aws eks update-kubeconfig --name $DEPLOYMENT_NAME`

# Jupyterhub-deploy

In this section, we will define a Docker image, then build and push it to ECR.  We will then deploy JupyterHub to the EKS cluster.

To get started, clone the repository:

- `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

### Configure, build, and push a Docker image to ECR

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy using `cp -r <existing-dir> <new-dir>` (the destination directory name should be the new deployment name).  Modifications to the Docker image and cluster configuration will need to be made.  Follow these instructions:

- Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).
- A file named *common.yaml* file needs to be created in the *config* directory.  An example can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-common.yaml).  Place a copy of this example file in *config*, and edit the contents as appropriate.
- Git add, commit, and push all changes.

Now, we'll build and push the Docker image:

- From the top level of the jupyterhub-deploy clone, `cd deployments/$DEPLOYMENT_NAME/image`
- `docker build --tag $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$DEPLOYMENT_NAME-user-image .`
- `DOCKER_LOGIN_CMD=$(awsudo $ADMIN_ARN aws ecr get-login --region us-east-1 --no-include-email)`
- `eval $DOCKER_LOGIN_CMD`
- `docker push $ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/$DEPLOYMENT_NAME-user-image:latest`

### Configure JupyterHub and cluster secrets

There are three categories of secrets involved in the cluster configuration:

-   **JupyterHub proxyToken** - the hub authenticates its requests to the proxy using a secret token that the both services agree upon.  Generate the token with this command:
	- `openssl rand -hex 32`
-   MAST authentication **client ID** and **client secret** - these were obtained earlier and will be used during the OAuth authentication process (Note that this authentication method is likely to change in the future)
-   **SSL private key and certificate** - these were obtained earlier

In the top level of the *jupyterhub-deployment* repository, create a directory structure that will contain a clone of the CodeCommit repository provisioned by Terraform earlier:

- `mkdir -p secrets/deployments/$DEPLOYMENT_NAME`
- `cd secrets/deployments/$DEPLOYMENT_NAME`

In the AWS console, find the URL of the secrets repository by navigating to **Services → CodeCommit → Repositories** and click on the repository named *<deployment-name>-secrets*.  Click on the drop-down button called "Clone URL" and select "Clone HTTPS".  The copied URL should look something like https://git-codecommit.us-east-1.amazonaws.com/v1/repos/deployment-name-secrets.

Next, assume the deployment-admin role and clone the repository:

- `aws sts assume-role $ADMIN_ARN --role-session-name clone`
- export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN with the values returned from the previous command
- `git config --global credential.helper '!aws codecommit credential-helper $@'`
- `git config --global credential.UseHttpPath true`
- `git clone https://git-codecommit.us-east-1.amazonaws.com/v1/repos/$DEPLOYMENT_NAME-secrets secrets`
- `unset AWS_ACCESS_KEY_ID; unset AWS_SECRET_ACCESS_KEY; unset AWS_SESSION_TOKEN`
- `cd secrets`

Since we use sops to encrypt and decrypt the secret files, we need to fetch the *.sops.yaml* file from S3 (this was created in *terraform-deploy/kms-codecommit*):

- `awsudo $ADMIN_ARN aws s3 cp s3://$DEPLOYMENT_NAME-sops-config/.sops.yaml .sops.yaml`

**BUG**:  it is necessary to manually insert the ARN of the encrypt role into *.sops.yaml* (the encrypt role is able to encrypt and decrypt).  You can see an example of an updated file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-sops.yaml).

**SECURITY ISSUE**: having the encrypt role in *.sops.yaml* will give helm more than the minimally required permissions since deployment only needs to decrypt.

Now we need to create a *staging.yaml* file.  During JupyterHub deployment, helm will merge this file with the *common.yaml* file with the other YAML files created earlier to generate a master configuration file for JupyterHub.  Follow these instructions:

- `awsudo $ADMIN_ARN sops staging.yaml` - this will open up your editor...
- Populate the file with the contents of https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-decrypted.yaml
- Fill in the areas that say "[REDACTED]" with the appropriate values, then save and exit the editor
- `git add staging.yaml .sops.yaml`

**BUG**: After *staging.yaml* has been created and configured, sops adds a section to the end of the file that defines the KMS key ARN and other values necessary for decryption.  Due to a hiccup documented in [JUSI-412](https://jira.stsci.edu/browse/JUSI-412), it is necessary to manually insert the ARN of the jupyterhub-admin role into the file so that sops can decrypt the file during deployment without specifying the role.  Edit the file (**do not use sops**) and add the role ARN.  You can see an example at the end of the an updated, encrypted file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-encrypted.yaml).

Finally, commit and push the changes to the repository:

- `git commit -m "adding secrets"`
- `awsudo $ADMIN_ARN git push`

### Deploying JupyterHub to the EKS cluster via helm

- `aws eks update-kubeconfig --name $DEPLOYMENT_NAME --region us-east-1 --role-arn $ADMIN_ARN`
- Change directories to the top level of the jupyterhub-deploy clone
- `./tools/deploy $DEPLOYMENT_NAME $ACCOUNT_ID <secrets-yaml> <environment>`
  - environment - staging or prod
  - secrets-yaml - *secrets/deployments/<deployment-name>/secrets/<environment>.yaml*
- `kubectl -n $DEPLOYMENT_NAME-staging get svc proxy-public`

The second command will output the hub's ingress, indicated by "EXTERNAL-IP".

##  Set up DNS with Route-53

**WARNING: This is a danger zone.  Mistakes here can take down live servers at the institute.

Now we need to make an entry in AWS **Route53**.  To start, navigate to https://st.awsapps.com/start in your browser.  Use your AD credentials to login.  You will be prompted for a DUO code.  Either enter "push" or a code.

Click on "AWS Account", then select the "aws-stctnetwork".  The menu will expand and show a link for "Management console" for "Route53-User-science.stsci.edu".  Click on that link and go to the "Route 53" service.

Click on "Hosted zones", then "science.stsci.edu".  You will see a list of all records under the "science.stsci.edu" zone.

Click on the "Create Record Set" button.  Enter the following information in the pane on the right:

- Name: **deployment-name.science.stsci.edu**
- Type: **A - IPv4 address**
- Alias: **Yes**
- Alias Target: **<hub's ingress>**
- Routing Policy: **Simple**
