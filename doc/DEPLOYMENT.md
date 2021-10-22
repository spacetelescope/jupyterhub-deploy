# Actions to take before deployment

**SSL certificates**

Put in a support ticket requesting SSL certificates for the desired DNS name.  A private key and a public certificate will be provided.

**Gather platform requirements**

Get list of desired software/files/notebooks for Docker image. This may take a while because it involves iterating with scientists and stakeholders.

**Register client with MAST**

JupyterHub will need a client secret and ID to integrate with the MAST authentication service.  You will need to contact someone on the MAST team to request these credentials - they will generate and deploy them to the OAuth service.

Hold on to the secret and ID, they will be needed later in the deployment process.

Note: There is currently no formalized procedure for requesting these credentials.  Currently, Ben Falk is a good contact.

**TODO**: is this section out of date?

# AWS Control Tower accounts

Login to the AWS Control Tower Console.  See ITSD for more details.

# CI Node Setup

This section covers the process of setting up an EC2 instance on AWS that will be used for configuration and deployment.

### Create EC2 instance for deployment

**TODO: update this section; use launch template**

Use the AWS EC2 Console to create a CI node where you'll deploy from.  The EC2 instance will be based on an AMI that contains software, tools, and configuration required for deployment.  Things like nodejs, helm3, awsudo, sops, docker, etc. are included.

- Base your EC2 instance on this AMI (on the dev acount): **ami-02e15130ac90d12fc**
- Instance type: **t3.xlarge**
- Network: ***ENV-MISSION*-SG**
- Subnet: ***ENV-MISSION*-SG-Private-*X***
- Role: **ci-node-instance**
- EBS storage: **150 GB**
- Tags: **Name = *your-username*-ci**
- Security group: **jupyterhub-worker-sg**
- Choose no key pair before launching

**_Please remember to shut down the instance when not in use._**

### Login to your EC2 instance

Use AWS Session Manager to login to your instance.

- Open up a terminal session.
- From the start page of the AWS accounts, click on the account you are working in to to expand the list of roles.  Next to the developer role, click on "Command line or programmatic access".  Hover over the code block under "Option 1: Set AWS environment variables" and click on "Click to copy these commands".
- In your terminal session, paste the commands.
- Identify your instance ID in the EC2 section of the Management console.
- `aws ssm start-session --target <instance-id> --region us-east-1`
- `sudo -u ec2-user -i`

# Repository Overview

The complete deployment process involves two git repositories:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/spacetelescope/terraform-deploy) | Creates an EKS cluster and the roles used by the cluster, CodeCommit, and ECR repositories |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains configurations for Docker images and JupyterHub deployments, as well as tools to accomplish deployment |

# Define Account ID, the Admin ARN, and the Deployment Name

- `export ACCOUNT_ID=<account-id>`
- `export ADMIN_ARN=<admin-arn>`
- `export DEPLOYMENT_NAME=<deployment-name>`
- `export ENVIRONMENT=<sandbox | dev | test | ops>`

# Terraform-deploy

This section describes how to set up an EKS cluster and supporting resources using Terraform.

Get a copy of the repository with this command:

- `git clone --recursive https://github.com/spacetelescope/terraform-deploy`

### Setup CodeCommit repository for secrets, an ECR repository for Docker images, and the User Data EFS volume

First, we will setup KMS and CodeCommit with the *one-time-setup* Terraform module:

- `cd terraform-deploy/one-time-setup/`
- `cp backend.conf.template backend.conf`
- Update *backend.conf* based on the templated values
- `awsudo -d 3600 $ADMIN_ARN terraform init -backend-config=./backend.conf`
- `cp your-vars.tfvars.template $DEPLOYMENT_NAME.tfvars`
- Update *deployment-name.tfvars* based on the templated values.
- `awsudo -d 3600 $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve`

A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops) later in this procedure.

### Provision EKS cluster

Next, we will configure and deploy an EKS cluster and supporting resources needed to run JupyterHub with the *ephemeral-setup* Terraform module:

- `../ephemeral-setup`
- `cp backend.conf.template backend.conf`
- Update *backend.conf* based on the templated values
- `awsudo -d 3600 $ADMIN_ARN terraform init -backend-config=./backend.conf`
- `cp your-vars.tfvars.template $DEPLOYMENT_NAME.tfvars`
- Update *deployment-name.tfvars* based on the templated values.
- `awsudo -d 3600 $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve`

# Jupyterhub-deploy

In this section, we will define a Docker image, then build and push it to ECR.  We will then deploy JupyterHub to the EKS cluster.

To get started, clone the repository:

- `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

#### Environment setup

- `cd jupyterhub-deploy`
- `cp setup-env.template setup-env`
- Update the environment variables in *setup-env*.
- `source setup-env`

## Configure, build, and push a Docker image to ECR

#### Configure Docker image

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy using `cp -r <existing-dir> <new-dir>` (the destination directory name should be the new deployment name).  Modifications to the Docker image and cluster configuration will need to be made.

- Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).
- A file named *common.yaml* file needs to be created in the *config* directory.  An example can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/example-common.yaml).  Edit the contents as appropriate.
- A file named *$ENVIRONMENT.yaml* also needs to be created in the *config* directory.  An example can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/example-env.yaml).  Edit the contents as appropriate.
- Git add, commit, and push all changes.

**NOTE:** This document covers configuring JupyterHub and deploying a fully specified image.  A secondary document describes the strategy/process used to define, update, and test a deployment's Docker image: [FRAMEWORK.md](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/FRAMEWORK.md).  There is a set of convenience scripts for image-related tasks described [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/SCRIPTS.md#image-management-scripts).

#### Scan-On-Push Docker Vulnerability Scanning

Our terraform'd ECR repositories have scan-on-push vulnerability scanning turned on.  After pushing, visit the ECR repository for your deployment, and when ready, review the scan results.  Address vulnerabilities as needed before proceeding with the deployment.  Scripts to automate the ECR scan results can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/SCRIPTS.md#scripts-to-automate-ecr-scan-results).

### Configure JupyterHub and cluster secrets

**Note**: There is a set of convenience scripts for managing secrets described [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/SCRIPTS.md#secrets-convenience-scripts).

There are three categories of secrets involved in the cluster configuration:

- **JupyterHub proxyToken** - the hub authenticates its requests to the proxy using a secret token that the both services agree upon.  Generate the token with this command:
    - `openssl rand -hex 32`
- MAST authentication **client ID** and **client secret** - these were obtained earlier and will be used during the OAuth authentication process.
- **SSL private key and certificate** - these were obtained earlier.

Start by cloning the repository:

- `secrets-clone`
- `cd deployments/$DEPLOYMENT_NAME/secrets`
- `cp ~/terraform-deploy/one-time-setup/.sops.yaml .sops.yaml`

**SECURITY ISSUE**: having the encrypt role in *.sops.yaml* will give helm more than the minimally required permissions since the deployment process only requires decrypt.

Now we need to create a *environment.yaml* file.  During JupyterHub deployment, helm will merge this file with the *common.yaml* file with the other YAML files created earlier to generate a master configuration file for JupyterHub.

- `awsudo $ADMIN_ARN sops $ENVIRONMENT.yaml` - this will open up your editor...
- Populate the file with the contents of https://github.com/spacetelescope/jupyterhub-deploy/blob/main/doc/example-secrets-env-decrypted.yaml.
- Fill in the areas that say "[REDACTED]" with the appropriate values, then save and exit the editor.
- `git add $ENVIRONMENT.yaml .sops.yaml`

To support pushing secrets back to codecommit you need to set up a credentials helper with:

``` 
git config --global credential.helper '!aws codecommit credential-helper $@' 
git config --global credential.UseHttpPath true
```

Finally, commit and push the changes to the repository:

- `git commit -m "adding secrets"`
- `awsudo $ADMIN_ARN git push`

### Deploying JupyterHub to the EKS cluster via helm

From the top directory of jupyterhub-deploy clone, run `deploy-jupyterhub`. The final output of this command will be the hub's ingress, indicated by "EXTERNAL-IP".

##  Set up DNS with Route-53

**WARNING: This is a danger zone.  Mistakes here can take down live servers at the institute.

Now we need to make an entry in AWS **Route53**.  To start, navigate to the AWS Control Tower Console in your browser.  Use your AD credentials to login.  You will be prompted for a DUO code.  Either enter "push" or a code.

Click on "AWS Account", then select the AWS account name hosting the Route53 entry.  The menu will expand and show a link for "Management console" for "Route53-User-science.stsci.edu".  Click on that link and go to the "Route 53" service.

Click on "Hosted zones", then "science.stsci.edu".  You will see a list of all records under the "science.stsci.edu" zone.

Click on the "Create Record" button and choose "Simple Routing".  Click on "Define simple record" and enter the following information in the pane on the right:

- Name: **deployment-name.science.stsci.edu**
- Type: **CNAME**
- Alias: **No**
- Alias Target: **<hub's ingress>**
- TTL: **300**
