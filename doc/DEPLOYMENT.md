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

# Configure AWS

You will need security credentials.  Under **IAM → Users→ yourUsername → Security Credentials → Access Keys** in the AWS console, create a new set.  Save these credentials, as you will not be able to access your secret key again.

On your CI node, execute:

- `aws configure`

You will be prompted for the following information:

- Access Key ID: **your-key-id**
- Secret Access Key: **your-access-key**
- Region: **us-east-1**
- Default output format: **json**

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

This section describes how to set up an EKS cluster and resources using Terraform.

Get a copy of the repository with this command:

- `git clone --recursive https://github.com/spacetelescope/terraform-deploy`

The terraform-deploy repository has two subdirectories with independent Terraform modules: *aws-creds* and *aws*.  *aws-codecommit-secrets* is a separate repository and will become a third subdirectory after being cloned.

### Setup IAM resources, KMS, and CodeCommit

The **_aws-creds_** subdirectory contains configuration files to set up roles and policies needed to do the overall deployment.

**Note:** AWS has a hard limit of 10 groups per user. Since terraform-deploy adds 2 groups, you can be a member of at most 8 groups before proceeding.

Complete these steps:

- `cd aws-creds`
- `cp roles.tfvars.template roles.tfvars`
- Customize *roles.tfvars* with your deployment name
- `terraform init`
- `terraform apply -var-file=roles.tfvars`

**_aws-codecommit-secrets_** contains Terraform modules to setup a secure way to store secret YAML files for use with helm.  There are two subdirectories in this repository: *kms-codecommit* and *terraform_iam*.

Clone the repository:

- `cd ..`
- `git clone https://github.com/spacetelescope/aws-codecommit-secret.git`.

Now, setup an IAM role using the *terraform-iam* module with just enough permissions to run the *kms-codecommit* module:

- `cd terraform-iam`
- `cp your-vars.tfvars.example roles.tfvars`
- Edit *roles.tfvars*:
	- Update "repo_name" to be "deployment-name-secrets"
	- Update the user ARN to reflect your user
- `terraform init`
- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-terraform-architect terraform apply -var-file=roles.tfvars`

Next, we will setup KMS and CodeCommit with the *kms-codecommit* Terraform module:

- `cd ../kms-codecommit`
- `cp your-vars.tfvars.example codecommit-kms.tfvars`
- Edit *codecommit.tfvars*:
	- Update "repo_name" to be "deployment-name-secrets"
	- Update the user ARNs to reflect your user
- `terraform init`
- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-secrets-repo-setup terraform apply -var-file=codecommit-kms.tfvars`
- A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops)

### Provision EKS cluster

The **_aws_** subdirectory contains configuration files that create the EKS cluster resources needed to run JupyterHub.

It creates the EKS cluster, ECR registry for JupyterHub images, IAM roles and policies for helm, the EKS autoscaler, etc.

Navigate to the *aws* directory.

Then run Terraform:

- `terraform init`
- Copy _your-cluster.tfvars.template_ to _deployment-name.tfvars_ and edit the contents
- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-terraform-architect terraform apply -var-file=<deployment-name>.tfvars` (this will take a while...)

Finally, configure the local deployment environment for the EKS cluster:

- `aws eks update-kubeconfig --name <deployment-name>`

# Jupyterhub-deploy

In this section, we will define a Docker image and EKS cluster configuration, as well as build and push the image to ECR.  We will then deploy JupyterHub to the cluster.

To get started, clone the repository:

- `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

### Configure, build, and push a Docker image to ECR

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy (the copied directory name should be the new deployment name).  Modifications to the Docker image and cluster configuration will need to be made.  Follow these instructions:

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
- `sops --decrypt staging.yaml > staging.yaml.decrypted`
- change directories to the top level of jupyterhub-deploy
- `./tools/deploy <deployment-name> <image-tag> <account-id> <secrets-yaml> <environment>`
  - environment - staging or prod
  - image-tag - TODO: describe how to find this...
  - secrets-yaml - *secrets/deployments/<deployment-name>/secrets/<environment>.yaml.decrypted*
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
