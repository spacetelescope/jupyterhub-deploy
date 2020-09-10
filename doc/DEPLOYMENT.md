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
| [hubploy](https://github.com/yuvipanda/hubploy) | A package that builds JupyterHub images, uploads them to ECR, and deploys JupyterHub to a staging or production environment. Hubploy supports iteration with the JupyterHub system and does not interact with the Kubernetes cluster. |
| [jupyterhub-deploy](https://github.com/spacetelescope/jupyterhub-deploy.git) | Contains JupyterHub deployment configurations for Docker images and and the EKS cluster.

# Terraform-deploy

This section describes how to set up an EKS cluster and resources required by the hubploy program, using Terraform.

Get a copy of the repository with this command:

- `git clone --recursive https://github.com/spacetelescope/terraform-deploy`

The terraform-deploy repository has two subdirectories with independent Terraform modules: *aws-creds* and *aws*.  *aws-codecommit-secrets* is a separate repository and will become a third subdirectory after being cloned.

### Setup IAM resources, KMS, and CodeCommit

The **_aws-creds_** subdirectory contains configuration files to set up roles and policies needed to do the overall deployment.

**Note:** AWS has a hard limit of 10 groups per user. Since terraform-deploy adds 2 groups, you can be a member of at most 8 groups before proceeding.

Complete these steps:

- `cd aws-creds`
- Customize the file called *roles.tfvars* with your deployment name
- `terraform init`
- `terraform apply -var-file=roles.tfvars`

**_aws-codecommit-secrets_** contains Terraform modules to setup a secure way to store secret YAML files for use with hubploy.  There are two subdirectories in this repository: *kms-codecommit* and *terraform_iam*.

Clone the repository:

- `cd ..`
- `git clone https://github.com/yuvipanda/aws-codecommit-secret.git`.

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

It creates the EKS cluster, ECR registry for JupyterHub images, IAM roles and policies for hubploy, the EKS autoscaler, etc.

In the *aws* directory, configure the local deployment environment for the EKS cluster:

- `awsudo arn:aws:iam::162808325377:role/<deployment-name>-hubploy-eks aws eks update-kubeconfig --name <deployment-name>`

Then run Terraform:

- `terraform init`
- Copy _your-cluster.tfvars.template_ to _deployment-name.tfvars_ and edit the contents
- `awsudo arn:aws:iam::<account-id>:role/<deployment-name>-terraform-architect terraform apply -var-file=<deployment-name>.tfvars` (this will take a while...)

Add yourself to the deployers group:

- In the AWS console, navigate to the IAM service.  Check for your user's membership in group *deployment-name-hubploy-deployers*
- Add your user to the group if necessary

Note: we should not have to add ourselves to the deployers group.  This step will go away eventually...

### Add Trust Relationships

Set up the trust relationships for role _deployment-name-hubploy-eks_ in the IAM service console:

- Open the AWS IAM service console for role _deployment-name-hubploy-eks_
- Click on the "Trust relationships" tab
- Click "Edit trust relationship"
- Replace the "Principal: block with:

```
      "Principal": {
        "AWS": [
          "arn:aws:iam::162808325377:user/<username>",
          "arn:aws:iam::162808325377:root",
          "arn:aws:iam::162808325377:role/<deployment-name>-secrets-decrypt"
        ]
      },
```

Next edit the trust relationships for _deployment-name-secrets-decrypt_:

- Open the AWS IAM service console for role _deployment-name-secrets-decrypt_
- Click on the "Trust relationships" tab
- Click "Edit trust relationship"
- Replace the "Principal" block with:

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
-  `cd hubploy`
- `pip install .`

You may remove the hubploy repository clone after installation.

# Jupyterhub-deploy

In this section, we will define a Docker image and EKS cluster configuration, as well as build and push the image to ECR.  We will then deploy JupyterHub to the cluster.

To get started, clone the repository:

- `git clone https://github.com/spacetelescope/jupyterhub-deploy.git`

### Build a Docker image with hubploy

First, identify an existing deployment in the *deployments* directory that most closely matches your desired configuration, and do a recursive copy (the copied directory name should be the new deployment name).  Modifications to the Docker image, cluster configuration, and *hubploy.yaml* file will need to be made.  Follow these instructions:

- An example of *hubploy.yaml* can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-hubploy.yaml).  Modify image_name, role_arn, project (the AWS account), and cluster.
- Go through the *image* directory, change file names and edit files that contain deployment-specific references.  Also make any changes to the Docker image files as needed (for instance, required software).
- A file named *common.yaml* file needs to be created in the *config* directory.  An example can be found [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-common.yaml).  Place a copy of this example file in *config*, and edit the contents as appropriate.
- Add, commit, and push all changes.
- From the top level of the jupyterhub-deploy repository, issue this command to build the Docker image and push it to ECR:
  - `hubploy build <deployment-name> --push --check-registry`

### Configure JupyterHub and cluster secrets

There are three categories of secrets involved in the cluster configuration:

-   **JupyterHub proxyToken** - the hub authenticates its requests to the proxy using a secret token that the both services agree upon.  Generate the token with this command:
	- `openssl rand -hex 32`
-   MAST authentication **client ID** and **client secret** - these were obtained earlier and will be used during the OAuth authentication process
-   **SSL private key and certificate** - these were obtained earlier

In the top level of the *jupyterhub-deployment* repository, create a directory structure that will contain a clone of the AWS CodeCommit repository provisioned by Terraform earlier:

- `mkdir -p secrets/deployments/<deployment-name>`
- `cd secrets/deployments/<deployment-name>`

In the AWS console, find the URL of the secrets repository by navigating to **Services → CodeCommit → Repositories** and click on the repository named *deployment-name-secrets*.  Click on the drop-down button called "Clone URL" and select "Clone HTTPS".  The copied URL should look something like https://git-codecommit.us-east-1.amazonaws.com/v1/repos/deployment-name-secrets.

Next, clone the repository:

- `git clone https://git-codecommit.us-east-1.amazonaws.com/v1/repos/<deployment-name>-secrets secrets`
- `cd secrets`

Since we use sops to encrypt and decrypt the secret files, we need to copy the *.sops.yaml* file that was created in *terraform-deploy/aws-codecommit-secret/kms-codecommit*:

- `cp terraform-deploy/aws-codecommit-secret/kms-codecommit/.sops.yaml .`
- `git add .sops.yaml`

**BUG**:  it is necessary to manually insert the ARN of the encrypt role into *.sops.yaml* (the encrypt role is able to encrypt and decrypt).  You can see an example of an updated file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-sops.yaml).

**SECURITY ISSUE**: having the encrypt role in *.sops.yaml* will give hubploy/helm more than the minimally required permissions since deployment only needs to decrypt.

Now we need to create a *staging.yaml* file.  During JupyterHub deployment, helm, via hubploy, will merge this file with the *common.yaml* file created earlier to generate a master configuration file for JupyterHub.  Follow these instructions:

- `awsudo arn:aws:iam::162808325377:role/<deployment-name>-secrets-encrypt sops staging.yaml` - this will open up your editor...
- Populate the file with the contents of https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-decrypted.yaml
- Fill in the areas that say "[REDACTED]" with the appropriate values
- `git add staging.yaml`

**BUG**: After *staging.yaml* has been created and configured, sops adds a section to the end of the file that defines the KMS key ARN and other values necessary for decryption.  Due to a hiccup documented in [JUSI-412](https://jira.stsci.edu/browse/JUSI-412), it is necessary to manually insert the ARN of the decrypt role into the file so that sops can decrypt the file during deployment without specifying the role.  Edit the file (**do not use sops**) and add the role ARN.  You can see an example at the end of the an updated, encrypted file [here](https://github.com/spacetelescope/jupyterhub-deploy/blob/staging/doc/example-staging-encrypted.yaml).

Finally, commit and push the changes to the repository.

### Deploying JupyterHub to the EKS cluster with hubploy

- `hubploy deploy <deployment-name> hub staging`
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
