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

# AWS Control Tower accounts

TODO:
- https://st.awsapps.com/start
- session manager basics, prereqs

# CI Node Setup

This section covers the process of setting up an EC2 instance on AWS that will be used for configuration and deployment.

### Create EC2 instance for deployment

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

- Open up a terminal session
- From the start page of the AWS accounts, click on the account you are working in to to expand the list of roles.  Next to the developer role, click on "Command line or programmatic access".  Hover over the code block under "Option 1: Set AWS environment variables" and click on "Click to copy these commands".
- In your terminal session, paste the commands
- Identify your instance ID in the EC2 section of the Management console
- `aws ssm start-session --target <instance-id> --region us-east-1`
- `sudo -u ec2-user -i`

# Repository Overview

The complete deployment process involves two git repositories:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/spacetelescope/terraform-deploy) | Creates an EKS cluster and the roles used by the cluster, CodeCommit, and ECR repositories |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains configurations for Docker images and JupyterHub deployments, as well as tools to accomplish deployment |

# Set some convenience variables

To make things more convient for the rest of this procedure, set a few evironment variables.  This will reduce the need to modify copy/paste commands.

- `export ACCOUNT_ID=<account-id>`
- `export ADMIN_ARN=arn:aws:iam::${ACCOUN_ID}:role/jupyterhub-admin`
- `export DEPLOYMENT_NAME=<deployment-name>`

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
- `awsudo -d 3600 $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve`
  - When prompted the enter a value for the "Owner" tag, enter the name of the mission (Roman, JWST, etc.)
  - BUG: you will likely need to run this twice until we add a "depends_on"

A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops) later in this procedure.

### Provision EKS cluster

Next, we will configure and deploy an EKS cluster and supporting resources needed to run JupyterHub with the *aws* Terraform module:

- `../aws`
- `terraform init`
- `cp your-cluster.tfvars.template $DEPLOYMENT_NAME.tfvars`
- Update *deployment-name.tfvars* based on the templated values
- `awsudo $ADMIN_ARN ./mktags` (Need to edit this first; maybe be Terraformed in the future)
- `awsudo -d 3600 $ADMIN_ARN terraform apply -var-file=$DEPLOYMENT_NAME.tfvars -auto-approve` (this will take a while...)

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

- `aws sts assume-role --role-arn $ADMIN_ARN --role-session-name clone`
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

- `awsudo $ADMIN_ARN aws eks update-kubeconfig --name $DEPLOYMENT_NAME --region us-east-1 --role-arn $ADMIN_ARN`
- Change directories to the top level of the jupyterhub-deploy clone
- `./tools/deploy $DEPLOYMENT_NAME $ACCOUNT_ID <secrets-yaml> <environment>`
  - environment - staging or prod
  - secrets-yaml - *secrets/deployments/<deployment-name>/secrets/<environment>.yaml*
- `kubectl get svc proxy-public`

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
