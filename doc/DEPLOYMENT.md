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

Note: some of this may change when we move to the sandbox account.

**_Please remember to shut down the instance when not in use._**

# Start Docker

`sudo service docker start`

(this step will not be necessary once JUSI-419 has been implemented)

# Repository Overview

Installing JupyterHub requires working through a flow of several git repositories, in series, on your CI node:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/spacetelescope/terraform-deploy) | Creates an EKS cluster, security roles, ECR registry, secrets, etc. needed to host a JupyterHub platform. |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains JupyterHub deployment configurations for Docker images and and the EKS cluster.

# Terraform-deploy

This section describes how to set up an EKS cluster and supporting resources using Terraform.

Get a copy of the repository with this command:

- `git clone --recursive https://github.com/spacetelescope/terraform-deploy`

To make things more convient for the rest of this procedure, set an evironment variable with the ARN of the jupyterhub-admin role, which can be found in the IAM section of the AWS console.

- export ADMIN_ARN=arn:aws:iam::<account-id>:role/jupyterhub-admin

### Setup CodeCommit and an ECR repository for secrets

Next, we will setup KMS and CodeCommit with the *kms-codecommit* Terraform module:

- `cd terraform-deploy/kms-codecommit`
- `terraform init`
- `cp your-vars.tfvars.example <deployment-name>.tfvars`
- Update *deployment-name.tfvars* based on the templated values
- `awsudo $ADMIN_ARN terraform apply -var-file=deployment-name.tfvars -auto-approve`

A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops) later in this procedure.

### Provision EKS cluster

The **_aws_** subdirectory contains configuration files that are used to create the EKS cluster and supporting resources needed to run JupyterHub.

Configure the module and run Terraform:

- `../aws`
- `terraform init`
- `cp your-cluster.tfvars.template to <deployment-name>.tfvars`
- Update *deployment-name.tfvars* based on the templated values
- `awsudo $ADMIN_ARN -var-file=<deployment-name>.tfvars -auto-approve` (this will take a while...)

Finally, configure the local deployment environment for the EKS cluster:

- `aws eks update-kubeconfig --name <deployment-name>`

# Jupyterhub-deploy

In this section, we will define a Docker image and EKS cluster configuration, as well as build and push the image to ECR.  We will then deploy JupyterHub to the cluster.

To get started, clone the repository:

- `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

### Configure, build, and push a Docker image to ECR

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy using `cp -r` (the copied directory name should be the new deployment name).  Modifications to the Docker image and cluster configuration will need to be made.  Follow these instructions:

- Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).
- A file named *common.yaml* file needs to be created in the *config* directory.  An example can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-common.yaml).  Place a copy of this example file in *config*, and edit the contents as appropriate.
- Add, commit, and push all changes.

Now, we'll build and push the Docker image:

- `cd deployments/<deployment-name>/image`
- `docker build --tag <account-id>.dkr.ecr.us-east-1.amazonaws.com/<deployment-name>-user-image .`
- `DOCKER_LOGIN_CMD=$(awsudo arn:aws:iam::<account-id>:role/<deployment-name>-hubploy-ecr aws ecr get-login --region us-east-1 --no-include-email)`
- `eval $DOCKER_LOGIN_CMD`
- `docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/<deployment-name>-user-image:latest`

### Configure JupyterHub and cluster secrets

There are three categories of secrets involved in the cluster configuration:

-   **JupyterHub proxyToken** - the hub authenticates its requests to the proxy using a secret token that the both services agree upon.  Generate the token with this command:
	- `openssl rand -hex 32`
-   MAST authentication **client ID** and **client secret** - these were obtained earlier and will be used during the OAuth authentication process
-   **SSL private key and certificate** - these were obtained earlier

In the top level of the *jupyterhub-deployment* repository, create a directory structure that will contain a clone of the AWS CodeCommit repository provisioned by Terraform earlier:

- `mkdir -p secrets/deployments/<deployment-name>`
- `cd secrets/deployments/<deployment-name>`

In the AWS console, find the URL of the secrets repository by navigating to **Services → CodeCommit → Repositories** and click on the repository named *<deployment-name>-secrets*.  Click on the drop-down button called "Clone URL" and select "Clone HTTPS".  The copied URL should look something like https://git-codecommit.us-east-1.amazonaws.com/v1/repos/deployment-name-secrets.

Next, assume the secrets-repo-setup role and clone the repository:

- `aws sts assume-role --role-arn arn:aws:iam::<account-id>:role/<deployment-name>-secrets-repo-setup --role-session-name clone`
- export AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN with the values returned from the previous command
- `git config --global credential.helper '!aws codecommit credential-helper $@'`
- `git config --global credential.UseHttpPath true`
- `git clone https://git-codecommit.us-east-1.amazonaws.com/v1/repos/<deployment-name>-secrets secrets`
- `unset AWS_ACCESS_KEY_ID; unset AWS_SECRET_ACCESS_KEY; unset AWS_SESSION_TOKEN`
- `cd secrets`

Since we use sops to encrypt and decrypt the secret files, we need to fetch the *.sops.yaml* file from S3 (this was created in *terraform-deploy/aws-codecommit-secret/kms-codecommit*):

- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-secrets-repo-setup aws s3 cp s3://<deployment-name>-sops-config/.sops.yaml .sops.yaml`
- `git add .sops.yaml`

**BUG**:  it is necessary to manually insert the ARN of the encrypt role into *.sops.yaml* (the encrypt role is able to encrypt and decrypt).  You can see an example of an updated file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-sops.yaml).

**SECURITY ISSUE**: having the encrypt role in *.sops.yaml* will give helm more than the minimally required permissions since deployment only needs to decrypt.

Now we need to create a *staging.yaml* file.  During JupyterHub deployment, helm will merge this file with the *common.yaml* file with the other YAML files created earlier to generate a master configuration file for JupyterHub.  Follow these instructions:

- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-secrets-encrypt sops staging.yaml` - this will open up your editor...
- Populate the file with the contents of https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-decrypted.yaml
- Fill in the areas that say "[REDACTED]" with the appropriate values
- `git add staging.yaml`

**BUG**: After *staging.yaml* has been created and configured, sops adds a section to the end of the file that defines the KMS key ARN and other values necessary for decryption.  Due to a hiccup documented in [JUSI-412](https://jira.stsci.edu/browse/JUSI-412), it is necessary to manually insert the ARN of the decrypt role into the file so that sops can decrypt the file during deployment without specifying the role.  Edit the file (**do not use sops**) and add the role ARN.  You can see an example at the end of the an updated, encrypted file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-encrypted.yaml).

Finally, commit and push the changes to the repository:

- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-secrets-repo-setup git push`

### Deploying JupyterHub to the EKS cluster with helm

- `aws eks update-kubeconfig --name <deployment-name> --region us-east-1 --role-arn arn:aws:iam::<account-id>:role/<deployment-name>-hubploy-eks`
- change directories to the top level of jupyterhub-deploy
- `./tools/deploy <deployment-name> <account-id> <secrets-yaml> <environment>`
  - environment - staging or prod
  - secrets-yaml - *secrets/deployments/<deployment-name>/secrets/<environment>.yaml*
- `kubectl -n <deployment-name>-staging get svc proxy-public`

The second command will output the hub's ingress, indicated by "EXTERNAL-IP".

##  Set up DNS with Route-53

Now we need to make an entry in AWS **Route53**.  To start, navigate to https://st.awsapps.com/start in your browser.  Use your AD credentials to login.  You will be prompted for a DUO code.  Either enter "push" or a code.

Click on "AWS Account", then select the "aws-stctnetwork".  The menu will expand and show a link for "Management console" for "Route53-User-science.stsci.edu".  Click on that link and go to the "Route 53" service.

Click on "Hosted zones", then "science.stsci.edu".  You will see a list of all records under the "science.stsci.edu" zone.

Click on the "Create Record Set" button.  Enter the following information in the pane on the right:

- Name: **deployment-name.science.stsci.edu**
- Type: **A - IPv4 address**
- Alias: **Yes**
- Alias Target: **<hub's ingress>**
- Routing Policy: **Simple**
