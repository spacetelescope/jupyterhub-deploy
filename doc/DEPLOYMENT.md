# Actions to take before deployment

**SSL certificates**

Put in a support ticket to obtain SSL certificates for the desired DNS name. You should be provided with a private key and a public certificate. _Make sure to put this request in early as it make take a while for ITSD to generate and provide them._

**Gather platform requirements**

Get list of desired software/files/notebooks for Docker image. This make take a while because it involves iterating with scientists and stakeholders.

**Register client with MAST**

Jupyterhub will need and client secret and ID to integrate with MAST authentication.  Follow these [instructions](https://innerspace.stsci.edu/display/DMD/Register+a+new+OAuth+application) to generate and register the secret and ID.  This process includes making a pull request.  Contact someone on the MAST team to test the new PR and update the production MAST service.

Hold on to the secret and ID, they will be needed later in the deployment process.

# CI Node Setup

This section documents setting up an EC2 instance on AWS from which to execute subsequent sections of these instructions and JupyterHub deployments.

### Create EC2 and login using ssh

Use the AWS EC2 Console to create a CI node where you'll deploy from.  The EC2 instance will be based on an AMI that contains software, tools, and configuration required for deployment.  Things like nodejs, helm3, awsudo, sops, docket, etc. are included.

- Base your EC2 on this AMI: **ami-01956bd49feb578e2**
- Instance type: **t3.xlarge**
- EBS storage: **150 GB**
- Security group: **institute-ssh-only**
- Tags: **Name = *your-username*-ci**
- From withing the ST network, connect to your CI node using ssh
	- Find your EC2 instance on the AWS console and copy the public IPv4 address, then issue this command: `ssh ec2-user@<public-IPv4-address-for-you-ci-node>`

Note: some of this may change when we move to the sandbox account.

**_Please remember to shut down the instance when not in use._**

## Configure AWS

You will need security credentials.  Under **IAM → Users→ yourUsername → Security Credentials → Access Keys** in the AWS console, create a new set.  Save these credentials, as you will not be able to access your secret key again.

On your CI node, execute `aws configure`.  You will be prompted for the following information:

- Access Key ID: **your-key-id**
- Secret Access Key: **your-access-key**
- Region: **us-east-1**
- Default output format: **json**

# Start Docker

`sudo service docker start`

(this step will not be necessary once ![](https://innerspace.stsci.edu/plugins/servlet/confluence/placeholder/macro?definition=e2ppcmE6a2V5PUpVU0ktNDE5fQ==&locale=en_US) has been implemented)

# Repository Overview

Installing JupyterHub requires working through a flow of several git repositories, in series, on your CI node:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/TheRealZoidberg/terraform-deploy) | Creates an EKS cluster, security roles, ECR registry, secrets, etc. needed to host a JupyterHub platform. |
| [hubploy](https://github.com/yuvipanda/hubploy) | A package that builds JupyterHub images, uploads them to ECR, and deploys JupyterHub to a staging or production environment. Hubploy supports iteration with the JupyterHub system and does not interact with the Kubernetes cluster. |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains JupyterHub deployment configurations for Docker images and and the EKS cluster.

# Terraform-deploy

This section describes how to set up an EKS cluster and resources required by the hubploy program, using Terraform.

Get a copy of the repository with this command: `git clone --recursive https://github.com/TheRealZoidberg/terraform-deploy` (Note: eventually, this will be will be merged back into the parent repository).

The terraform-deploy repository has three subdirectories with independent Terraform configurations: *aws-creds*, *aws*, and *aws-codecommit-secrets*.

### Setup IAM resources and assume architect role

The **_aws-creds_** subdirectory contains configuration files to set up roles and policies needed to do the overall deployment.

 - In the _aws-creds_ directory, create a new file called *roles.tfvars* [**DO WE COPY AN EXAMPLE FILE FROM SOMEWHERE???**]
 - Edit and add the following:
	 - region = **us-east-1**
	 - iam_prefix = **prefix** (where *prefix* is the deployment name)
 - `terraform init`
 - `terraform apply -var-file=roles.tfvars` (this creates a group that can assume the architect role)
 - Add user to group *prefix*-terraform-architect [**SHOULD THIS BE NECESSARY???**]
 - Assume the role:
	 - `aws sts assume-role --role-arn arn:aws:iam::162808325377:role/gough-terraform-architect --role-session-name gough`
		 - The output of this command should be similar to [this](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/assume-role-output.txt)
	 - Export variables *AWS_SECRET_ACCESS_KEY*, *AWS_SESSION_TOKEN*, and *AWS_ACCESS_KEY_ID* based on the output

The assumed architect role will allow you to proceed with the rest of the deployment.

### Provision EKS cluster

The **_aws_** subdirectory contains configuration files that create the EKS cluster resources needed to run JupyterHub.

It creates the EKS cluster, ECR registry for JupyterHub images, IAM roles and policies for hubploy, the EKS autoscaler, etc.

In the *aws* directory, configure the local deployment environment for the EKS cluster:
- `aws eks update-kubeconfig --name <deploymentName>`
- `aws sts get-caller-identity`

Then run Terraform:
- `terraform init`
- Copy _your-cluster.tfvars.template_ to _deploymentName.tfvars_ and edit the contents
- `terraform apply -var-file=deploymentName.tfvars` (this will take a while...)

### Setup roles for accessing the secrets repository

The _**aws-codecommit-secrets**_ subdirectory contains configuration files that setup roles for accessing for a private AWS CodeCommit repository.  This repository will contain secrets for the EKS cluster, JupyterHub proxy, and MAST authentication.

[**TODO: INCLUDE TERRAFORM INSTRUCTIONS**]

Instructions for populating this repository will be provided later.

# Hubploy

To clone and install hubploy:

- `git clone https://github.com/yuvipanda/hubploy`
-  `cd hubploy`
- `git checkout support_roles` [**This step will go away once the branch is merged**]
- `pip install .`

You may remove the hubploy repository clone after installation.

# Jupyterhub-deploy

In this section, we will define a Docker image and EKS cluster configuration, as well as build and push the image to ECR.  We will then deploy JupyterHub to the cluster.

To get started, clone the repository: `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

### Build a Docker image with Hubploy

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy (the copied directory name should be the new deployment name).  Modifications to the Docker image, cluster configuration, and *hubploy.yaml* file will need to be made.

An example of *hubploy.yaml* can be found [here](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-hubploy.yaml).  Modify image_name, role_arn, project (the AWS account), and cluster.

Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).

Once the configuration changes have been made, change directories to the top level of the jupyterhub-deploy repository.  Then issue this command to build the Docker image and push it to ECR: `hubploy build <deployment-name> --push --check-registry`.

### Configure Jupyterhub and Cluster Secrets

There are three categories of secrets involved in the cluster configuration:

-   **Jupyterhub proxyToken** - this will be used by the Jupyterhub hub pod (**or proxy? check on this; is this what it's actually used for?**)
-   MAST authentication **client ID** and **client secret** - these with be used during the OAuth2 authentication process
-   **SSL private key and certificate** - these were obtained earlier

Steps to obtain and configure secrets:


2.  Clone CodeCommit repository in <top-level jupyterhub-deploy>/secrets/deployments/<deployment>/**secrets**
    1.  Using sops, create a file called staging.yaml that looks like this: [https://gist.github.com/cslocum/1ac64ff17eb7ffd574ea95b4b661d921](https://gist.github.com/cslocum/1ac64ff17eb7ffd574ea95b4b661d921) [Move somewhere from gist]
    2.  common.yaml in <top-level jupyterhub-deploy>/deployments/<deployment>/config should look like this: [https://gist.github.com/cslocum/48f7151fb5c713b6d4e5f5eee1a09f6b](https://gist.github.com/cslocum/48f7151fb5c713b6d4e5f5eee1a09f6b) [Move somewhere from gist]






### Deploying Jupyterhub to the EKS Cluster with Hubploy

1.  hubploy deploy <hub-name> hub staging
2.  kubectl -n <hub-name>-staging get svc proxy-public
    1.  Will return public IP address of hub.
        
        kubectl -n roman-sit-staging get svc proxy-public
        NAME           TYPE           CLUSTER-IP     EXTERNAL-IP                                                               PORT(S)                      AGE
        proxy-public   LoadBalancer   10.100.89.44   adf8eaeb22ac649819fa9475a65c1dbd-1141269795.us-east-1.elb.amazonaws.com   443:32457/TCP,80:30976/TCP   7d3h
        
          
        
    2.  Connecting to external ingress will bring you to hub login page. Log in with AD credentials.![](https://innerspace.stsci.edu/download/attachments/212113480/image2020-7-13_15-21-28.png?version=1&modificationDate=1594668088952&api=v2 "Data Management Division > EKS Jupyterhub Setup > image2020-7-13_15-21-28.png")
    3.  Using Route 53, add an entry associating the DNS name to the ingress [ADD MORE INFO]


----------

# Misc. Notes

  

We use [KMS Secret Encryption](https://innerspace.stsci.edu/display/DMD/KMS+Secret+Encryption) to store secrets. The encrypted secrets are stored in a CodeCommit repository.

  

Earlier notes, procedures, etc. that were on this page have been moved [here](https://innerspace.stsci.edu/display/DMD/AMI%3A+misc) for posterity.

  

Yuvi's provided this diagram documenting some of the repository relationships a while ago:  
  
![](https://innerspace.stsci.edu/rest/documentConversion/latest/conversion/thumbnail/214342897/3?attachmentId=214342897&version=3&mimeType=application%2Fpdf&height=250&thumbnailStatus=200)
  

