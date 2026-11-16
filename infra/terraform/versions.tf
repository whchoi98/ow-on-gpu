terraform {
  required_version = ">= 1.14.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.73"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.3"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project = "ow-on-gpu"
    }
  }
}

# public.ecr.aws 인증 토큰은 us-east-1에서만 발급된다. Karpenter 차트를 받을 때 쓴다.
provider "aws" {
  alias  = "virginia"
  region = "us-east-1"
}

provider "helm" {
  kubernetes = {
    host                   = aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(aws_eks_cluster.this.certificate_authority[0].data)
    exec = {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", aws_eks_cluster.this.name, "--region", var.region]
    }
  }
}
