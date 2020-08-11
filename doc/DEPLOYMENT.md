# Actions to take before deployment

**SSL certificates**

Put in a support ticket to obtain SSL certificates for the desired DNS name. You should be provided with a private key and a public certificate. _Make sure to put this request in early as it may take a while for ITSD to generate and provide them._

**Gather platform requirements**

Get list of desired software/files/notebooks for Docker image. This make take a while because it involves iterating with scientists and stakeholders.

**Register client with MAST**

JupyterHub will need and client secret and ID to integrate with MAST authentication.  Follow these [instructions](https://innerspace.stsci.edu/display/DMD/Register+a+new+OAuth+application) to generate and register the secret and ID.  This process includes making a pull request.  Contact someone on the MAST team to test the new PR and update the production MAST service.

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

# Configure AWS

You will need security credentials.  Under **IAM → Users→ yourUsername → Security Credentials → Access Keys** in the AWS console, create a new set.  Save these credentials, as you will not be able to access your secret key again.

On your CI node, execute `aws configure`.  You will be prompted for the following information:

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
| [hubploy](https://github.com/yuvipanda/hubploy) | A package that builds JupyterHub images, uploads them to ECR, and deploys JupyterHub to a staging or production environment. Hubploy supports iteration with the JupyterHub system and does not interact with the Kubernetes cluster. |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains JupyterHub deployment configurations for Docker images and and the EKS cluster.

# Terraform-deploy

This section describes how to set up an EKS cluster and resources required by the hubploy program, using Terraform.

Get a copy of the repository with this command: `git clone --recursive https://github.com/spacetelescope/terraform-deploy` (Note: eventually, this will be will be merged back into the parent repository).

The terraform-deploy repository has two subdirectories with independent Terraform modules: *aws-creds* and *aws*.  *aws-codecommit-secrets* is a separate repository and will become a third subdirectory after being cloned.

### Setup IAM resources, KMS, and CodeCommit

The **_aws-creds_** subdirectory contains configuration files to set up roles and policies needed to do the overall deployment.

**NOTE:** AWS has a hard limit of 10 groups per user.   Since terraform-deploy adds 2 groups,  you can be a member of at
most 8 groups prior to executing these instructions.

Complete these steps:

- Customize the file called *roles.tfvars* with your cluster name.
- `terraform init`
- `terraform apply -var-file=roles.tfvars`
- After Terraform constructs group `<deployment-name>-terraform-architects`,  add your user to it using the AWS IAM console.
- WHAT ELSE???


**_aws-codecommit-secrets_** contains Terraform code to set up a secure way to store secret YAML files for use with hubploy.

`aws-codecommit-secrets` directory should have been created by the recursive clone of `terraform-deploy` above, but if not,
run:  `git clone https://github.com/yuvipanda/aws-codecommit-secret.git` from the terraform-deploy root directory.

There are two subdirectories in `aws-codecommit-secrets`: *kms-codecommit* and *terraform_iam*.

First, setup an IAM role using *terraform-iam* with just enough permissions to run the Terraform module in *kms-codecommit*:

- `cd terraform-iam`
- `cp your-vars.tfvars.example roles.tfvars`
- Edit *roles.tfvars*:
	- Update "repo_name" to be "deployment-name-secrets"
	- Update the user ARN to reflect your user
- `terraform init`
- `awsudo arn:aws:iam::162808325377:role/deployment-name-secrets-setup terraform apply -var-file=roles.tfvars`

Next, we will setup KMS and CodeCommit with the *kms-codecommit* Terraform module:

- `cd ../kms-codecommit`
- `cp your-vars.tfvars.example codecommit.tfvars`
- Edit *codecommit.tfvars*:
	- Update "repo_name" to be "deployment-name-secrets"
	- Update the user ARNs to reflect your user
- `terraform init`
- `awsudo arn:aws:iam::162808325377:role/<deployment-name->secrets-setup terraform apply -var-file=code.tfvars`
- A file named **_.sops.yaml_** will have been produced, and this will be used in the new CodeCommit repository for appropriate encryption with [sops](https://github.com/mozilla/sops)

### Provision EKS cluster

The **_aws_** subdirectory contains configuration files that create the EKS cluster resources needed to run JupyterHub.

It creates the EKS cluster, ECR registry for JupyterHub images, IAM roles and policies for hubploy, the EKS autoscaler, etc.

In the *aws* directory, configure the local deployment environment for the EKS cluster:
- `awsudo arn:aws:iam::162808325377:role/<deployment-name>-hubploy-eks aws eks update-kubeconfig --name <deploymentName>`

Then run Terraform:
- `terraform init`
- Copy _your-cluster.tfvars.template_ to _deploymentName.tfvars_ and edit the contents
- `terraform apply -var-file=deploymentName.tfvars` (this will take a while.)

Add yourself to the deployers group:
- Check for your user's membership in group `<deployment-name>`-hubploy-deployers.
- Use the IAM console to add it to your user as necessary.

### Add Trust Relationships

Set up the trust relationships for role `<deployment-name>-hubploy-eks` using the IAM console:

- Open the AWS IAM console for role `<deployment-name>-hubploy-eks`
- Click on the `Trust relationships` tab.
- Click `Edit trust relationship`.
- Replace the `Principal` block with:

```
      "Principal": {
        "AWS": [
          "arn:aws:iam::162808325377:user/<username>",
          "arn:aws:iam::162808325377:root",
          "arn:aws:iam::162808325377:role/<deployment-name>-secrets-decrypt"
        ]
      },
```

Next edit the trust relationships for `<deployment-name>-secrets-decrypt`:

- Open the AWS IAM console for role `<deployment-name>-secrets-decrypt`
- Click on the `Trust relationships` tab.
- Click `Edit trust relationship`.
- Replace the `Principal` block with:

```
      "Principal": {
        "AWS": [
          "arn:aws:iam::162808325377:role/<deployment-name>-hubploy-eks",
          "arn:aws:iam::162808325377:user/<username>",
          "arn:aws:iam::162808325377:role/kops_svc"
        ]
      },
```

# Hubploy

To clone and install hubploy:

- `git clone https://github.com/yuvipanda/hubploy`
- `cd hubploy`
- `pip install .`

You may remove the hubploy repository clone after installation.

# Jupyterhub-deploy

In this section, we will define a Docker image and EKS cluster configuration, as well as build and push the image to ECR.  We will then deploy JupyterHub to the cluster.

To get started, clone the repository: `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

## Build a Docker Image with Hubploy

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy (the copied directory name should be the new deployment name).  Modifications to the Docker image, cluster configuration, and *hubploy.yaml* file will need to be made.

1. An example of *hubploy.yaml* can be found [here](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-hubploy.yaml).  Modify image_name, role_arn, project (the AWS account), and cluster.

2. Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).

3. A file named *common.yaml* file needs to be created in the *config* directory.  An example can be found [here](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-common.yaml).  Place a copy of this example file in *config*, and edit the contents as appropriate.

4. Add, commit, and push all changes.

5. Once the configuration changes have been made, change directories to the top level of the jupyterhub-deploy repository.

6. If needed, log into AWS ECR using this or something like it:

- `aws ecr get-login | sed -e 's/-e none//g' | bash`


7. Then issue this command to build the Docker image and push it to ECR:

- `hubploy build <deployment-name> --push --check-registry`


## Configure JupyterHub and Cluster Secrets

There are three categories of secrets involved in the cluster configuration:

-   **JupyterHub proxyToken** - the hub authenticates its requests to the proxy using a secret token that the both services agree upon
	- Generate the token with this command: `openssl rand -hex 32`
-   MAST authentication **client ID** and **client secret** - these were generated earlier and will be used during the OAuth authentication process
-   **SSL private key and certificate** - these were obtained earlier

In the top level of the *jupyterhub-deployment* repository, create a directory structure that will contain a clone of the AWS CodeCommit repository provisioned by Terraform earlier.

- `mkdir -p secrets/deployments/deployment-name`
- `cd secrets/deployments/deployment-name`

In the AWS console, find the URL of the secrets repository by navigating to **Services → CodeCommit → Repositories** and click on the repository named *deployment-name-secrets*.  Click on the drop-down button called "Clone URL" and select "Clone HTTPS".  The copied URL should look something like https://git-codecommit.us-east-1.amazonaws.com/v1/repos/deployment-name-secrets.

Next, clone the repository:

- `git clone https://git-codecommit.us-east-1.amazonaws.com/v1/repos/deployment-name-secrets secrets`
- `cd secrets`

Since we use sops to encrypt and decrypt the secret files, we need to copy the *.sops.yaml* file that was created *terraform-deploy/aws-codecommit-secret/kms-codecommit*:

- `cp terraform-deploy/aws-codecommit-secret/kms-codecommit/.sops.yaml .`
- `git add .sops.yaml`

Examining `.sops.yaml`,  it should look something like this:

```
creation_rules:
  - path_regex: .*
    kms: "arn:aws:kms:us-east-1:162808325377:key/<your kms key uuid>"
    role: "arn:aws:iam::162808325377:role/<deployment-name>-secrets-decrypt"
```

If it does not, ask around and/or update it accordingly.

Now we need to create a *staging.yaml* file.  During JupyterHub deployment, helm, via hubploy, will merge this file with the the *common.yaml* file created earlier in the deployment configuration process to generate a master configuration file for JupyterHub.  Download the [example file](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-staging.yaml) and fill in the redacted sections (pay attention to indentation - only use spaces):

- `wget https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-staging.yaml` (**This URL will changed after merging in the master branch**)
- `git add staging.yaml`
- `sops staging.yaml`
- Fill in the areas that say "[REDACTED]" and change the "client_id" value

Do to a hiccup documented in [JUSI-412](https://jira.stsci.edu/browse/JUSI-412), it is necessary to insert the ARN of the decrypt role, so that sops can decrypt *staging.yaml* during deployment without specifying the role.  Once *staging.yaml* has been created and configured, edit the file (do not use sops) and add the role ARN.  You can see an example of the bottom of the an updated, encrypted file [here](https://github.com/cslocum/jupyterhub-deploy/blob/roman/doc/example-staging-with-inserted-role.yaml).

Finally, commit and push the changes to the repository.

## Deploying JupyterHub to the EKS Cluster with Hubploy

- `hubploy deploy <deployment-name> hub staging`
- `kubectl -n <deployment-name>-staging get svc proxy-public`

The second command will output the hub's ingress, indicated by "EXTERNAL-IP".

## Set up DNS with Route-53

Now we need to make an entry in AWS **Route53**.  To start, navigate to https://st.awsapps.com/start in your browser.  Use your AD credentials to login.  You will be prompted for a DUO code.  Either enter "push" or a code.

Click on "AWS Account", then select the "aws-stctnetwork".  The menu will expand and show a link for "Management console" for "Route53-User-science.stsci.edu".  Click on that link.  Go to the "Route 53" service.

Click on "Hosted zones", then "science.stsci.edu".  You will see a list of all records under the "science.stsci.edu" zone.

Click on the "Create Record Set" button.  Enter the following information in the pane on the right:

- Name: **deployment-name.science.stsci.edu**
- Type: **A - IPv4 address**
- Alias: **Yes**
- Alias Target: **<hub's ingress>**
- Routing Policy: **Simple**
