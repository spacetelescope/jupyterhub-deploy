#! /usr/bin/env python

import os
import subprocess


deployment_name = 'roman-sit'
image_tag = 'ee7c41f'
account_id = '328656936502'
secrets_yaml = 'secrets/deployments/roman-sit/secrets/staging.yaml.decrypted'
environment = 'staging'

if not os.path.exists(secrets_yaml):
    raise Exception(f'secrets file {secrets_yaml} does not exist')

helm_cmd = f'"helm upgrade", "--wait", "--install", "--namespace", "{deployment_name}-{environment}", "{deployment_name}-{environment}", "hub", "-f", "deployments/{deployment_name}/config/common.yaml", "-f deployments/{deployment_name}/config/{environment}.yaml", "-f", "secrets/deployments/{deployment_name}/secrets/{environment}.yaml.decrypted", "--set-string jupyterhub.singleuser.image.tag={image_tag}", "--set-string jupyterhub.singleuser.image.name={account_id}.dkr.ecr.us-east-1.amazonaws.com/{deployment_name}-user-image"'

print(helm_cmd)


proc = subprocess.Popen(
    helm_cmd,
    stdout = subprocess.PIPE, 
    stderr = subprocess.PIPE
)
stdout, stderr = process.communicate()
print(stdout, stderr)

