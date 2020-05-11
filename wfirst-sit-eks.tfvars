region = "us-east-1"

# See https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html for
# more information
map_users = [{
    userarn  = "arn:aws:iam::162808325377:role/JupyterhubOperator"
    username = "JupyterhubOperator"
    groups   = ["system:masters"]
}]

# Name of your cluster
cluster_name = "wfirst-sit-eks"

vpc_name = "wfirst-sit-eks-vpc"
