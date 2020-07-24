
[Add a bit of background]

# Prerequisites

[What are we putting here?]

# Actions to take before deployment

**SSL certificates**

Put in a support ticket to obtain SSL certificates for the desired DNS name. You should be provided with a private key and a public certificate. _Make sure to put this request in early as it make take a while for ITSD to generate and provide them._

**Gather Platform Requirements**

Get list of desired software/files/notebooks for Docker image. This make take a while because it involves iterating with scientists and stakeholders.

# CI Node Setup

This section documents setting up an EC2 instance on AWS from which to execute subsequent sections of these instructions and JupyterHub deployments.

### Create EC2 and login using ssh

Use the AWS EC2 Console to create a CI node where you'll deploy from.  The EC2 instance will be based on an AMI that contains software, tools, and configuration required for deployment.  Things like nodejs, helm3, awsudo, sops, docket, etc. are included.

- Base your EC2 on this AMI: **ami-01956bd49feb578e2**
- Instance type: **t3.xlarge**
- EBS storage: **150 GB**
- Security group: **institute-ssh-only**
- Tags: **Name = <your-username>-ci**
- On your laptop or desktop pc, connect to your EC2 / CI node using ssh
- You must be on VPN to get through the security group restrictions

Select your EC2 instance on the AWS console and copy the public IPv4 address.

`ssh ec2-user@<public-IPv4-address-for-you-ci-node>`

_Please remember to shut down the instance when not in use._

## Configure AWS

You will need security credentials, they can be found in the AWS console under IAM→Users→ yourUsername → Security Credentials → Access Keys

Then on your CI node:
`aws configure`

- Access Key ID: **<your key id>**
- Secrete Access Key: **<your secret key>**
- Region: **us-east-1**
- Default output format: **json**

## Start Docker

`sudo service docker start`

(this step will not be necessary once ![](https://innerspace.stsci.edu/plugins/servlet/confluence/placeholder/macro?definition=e2ppcmE6a2V5PUpVU0ktNDE5fQ==&locale=en_US) has been implemented)

# Repository Overview

Once your CI node is set up, installing JupyterHub requires working through a flow of several git repositories in series on your CI node:

| Repository | Description |
|--|--|
| [terraform-deploy](https://github.com/TheRealZoidberg/terraform-deploy) | Creates an EKS cluster, security roles, ECR registry, secrets, etc. needed to host a JupyterHub system. |
| [hubploy](https://github.com/yuvipanda/hubploy) | Program which builds JupyterHub images, interacts with ECR, and (re)deploys JupyterHub to a staging or production environment. Supports iterating with the JupyterHub system and notebook image vs. the basic cluster infrastructure. |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Various configurations of JupyterHub images (including notebook config) which are deployed by hubploy and run on the EKS cluster built by terraform-deploy. |
| [hubploy-template](https://github.com/yuvipanda/hubploy-template) (optional) | spacetelescope/jupyterhub-deploy is an instantiation of this template. Template is used by organizations to set up their own custom JupyterHub images. |

# Terraform-deploy repository

This section describe setting up basic EKS cluster infrastructure and resources required by the hubploy program using the Terraform system.

The terraform-delpoy repo has three subdirectories with independent Terraform installs: aws-creds, aws, and aws-codecommit-secrets.

### Subdirectory aws-creds

The _**aws-creds**_ subdirectory uses Terraform to set up roles and policies needed to do the overall deployment.

 1.  `git clone --recursive https://github.com/super-cob/terraform-deploy` (This is Jacob's repo, note that [https://github.com/TheRealZoidberg/terraform-deploy](https://github.com/TheRealZoidberg/terraform-deploy) contains the secrets code as well)
	 - Create new file *roles.tfvars*
	 - Edit and add the following:
		 - region = "us-east-1"  
		 - iam_prefix = "prefix" (Where *prefix* can be a username or hubploy deployment name)
	 - `terraform init`
	 - `terraform apply -var-file=roles.tfvars` (this creates a group, group can assume role, role is architect)
	 - Add user to group - *prefix*-terraform-architect
	 - Assume the role:
		 - `aws sts assume-role --role-arn arn:aws:iam::162808325377:role/gough-terraform-architect --role-session-name gough`;  output of this command should produce output similar to this

    
 3.    
    
     {
        "AssumedRoleUser": {
            "AssumedRoleId": "AROASL2BB4UAZ23PIH7PC:cob7",
            "Arn": "arn:aws:sts::162808325377:assumed-role/gough-terraform-architect/cob7"
        },
        "Credentials": {
        "SecretAccessKey": "<SomeSecret>”,
        "SessionToken": "<SomeToken>",
        "Expiration": "2020-05-19T20:53:15Z",
        "AccessKeyId": "<SomeID>"
    }
    
      
    
    1.  Export variables:
        
        export AWS_SECRET_ACCESS_KEY=<someSecret>
        export AWS_SESSION_TOKEN=<someToken>
        export AWS_ACCESS_KEY_ID=<someID>
        
          
        

## Subdirectory aws

The _**aws**_ subdirectory is responsible for creating the core EKS cluster resources needed to run a JupyterHub.

It creates the EKS cluster, ECR registry for JupyterHub images, IAM roles and policies for HubPloy, the EKS autoscaler, etc.

1.  1.  Set eks config by the following:
        1.  aws eks update-kubeconfig --name <deploymentName>
        2.  aws sts get-caller-identity  
            cd ../aws
            1.  terraform init
                1.  Copy your-cluster.tfvars.template to <deploymentName>.tfvars - and edit contents.
            2.  terraform apply -var-file=<deploymentName>.tfvars
            3.  This will start a long build process...
            4.  Process will generate 'hubploy.yaml'
            5.  Edit hubploy.yaml to match the following:
                1.  images:  
                    image_name:  [162808325377.dkr.ecr.us-east-1.amazonaws.com/<deploymentName>-user-image](http://162808325377.dkr.ecr.us-east-1.amazonaws.com/wfirst-sit-user-image)  
                    provider: aws  
                    aws:  
                    zone: us-east-1  
                    role_arn: arn:aws:iam::162808325377:role/<deploymentName>-hubploy-ecr  
                    project: 162808325377  
                    cluster: <cluster-name>  
                    provider: aws  
                    aws:  
                    zone: us-east-1  
                    role_arn: arn:aws:iam::162808325377:role/<deploymentName>-hubploy-eks  
                    cluster: wfirst-sit  
                    project: 162808325377
                2.  Copy hubply.yaml to jupyterhub-deploy/deplyments/yourdeployment

## Subdirectory aws-codecommit-secrets

The _**aws-codecommit-secrets**_ subdirectory is used to set up roles and and ECR registry used to manage JupyterHub secrets in a private repo.

1.  Follow the instructions here for secrets setup:
    1.  [KMS Secret Encryption](https://innerspace.stsci.edu/display/DMD/KMS+Secret+Encryption)

  

----------

# Hubploy repository

This section documents installing the hubploy program which automates deploying a new JupyterHub image to the Terraformed EKS cluster.

1.  Checkout hubploy:
    1.  git clone [https://github.com/yuvipanda/hubploy](https://github.com/yuvipanda/hubploy)
    2.  cd hubploy
2.  Checkout 'support_roles'
    1.  git checkout support_roles
    2.  pip install .

  

----------

# Jupyterhub-deploy repository

This section documents [TODO]

1.  Clone jupyterhub-deploy.
    1.  git clone [https://github.com/spacetelescope/jupyterhub-deploy.git](https://github.com/spacetelescope/jupyterhub-deploy.git)

# Build Docker Image with Hubploy

1.  Configure image
2.  cd ~/jupyterhub-deploy
3.  hubploy build <hub-name> --push --check-registry

# Configure Jupyterhub and Cluster Secrets

There are three categories of secrets involved in the cluster configuration:

-   **Jupyterhub proxyToken** - this will be used by the Jupyterhub hub pod (or proxy? check on this; is this what it's actually used for?)
-   MAST authentication **client ID** and **client secret** - these with be used during the OAuth2 authentication process
-   **SSL private key and certificate** - these were obtained earlier

Steps to obtain and configure secrets:

1.  Generate and register client secret and ID, and register with MAST authentication site
    1.  [Register a new OAuth application](https://innerspace.stsci.edu/display/DMD/Register+a+new+OAuth+application)
    2.  Need to contact someone on MAST team to merge PR and re-deploy [THIS CAN TAKE A WHILE]
2.  Clone CodeCommit repository in <top-level jupyterhub-deploy>/secrets/deployments/<deployment>/**secrets**
    1.  Using sops, create a file called staging.yaml that looks like this: [https://gist.github.com/cslocum/1ac64ff17eb7ffd574ea95b4b661d921](https://gist.github.com/cslocum/1ac64ff17eb7ffd574ea95b4b661d921) [Move somewhere from gist]
    2.  common.yaml in <top-level jupyterhub-deploy>/deployments/<deployment>/config should look like this: [https://gist.github.com/cslocum/48f7151fb5c713b6d4e5f5eee1a09f6b](https://gist.github.com/cslocum/48f7151fb5c713b6d4e5f5eee1a09f6b) [Move somewhere from gist]

# Deploying Jupyterhub to the EKS Cluster with Hubploy

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
