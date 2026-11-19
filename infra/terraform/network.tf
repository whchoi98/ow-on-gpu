data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_vpc" "this" {
  filter {
    name   = "tag:Name"
    values = [var.vpc_name]
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.this.id]
  }
  filter {
    name   = "tag:kubernetes.io/role/internal-elb"
    values = ["1"]
  }
}

data "aws_subnet" "private" {
  for_each = toset(data.aws_subnets.private.ids)
  id       = each.value
}

locals {
  control_plane_subnet_ids = sort([
    for s in data.aws_subnet.private : s.id if contains(local.control_plane_azs, s.availability_zone)
  ])
}

# Karpenter가 이 클러스터의 서브넷과 보안 그룹만 고르도록 붙이는 태그.
# kubernetes.io/role/internal-elb 태그는 같은 계정의 다른 VPC에도 있어서 선택 기준으로 쓸 수 없다.
resource "aws_ec2_tag" "karpenter_subnet" {
  for_each    = toset(data.aws_subnets.private.ids)
  resource_id = each.value
  key         = "karpenter.sh/discovery"
  value       = local.cluster_name
}

resource "aws_ec2_tag" "karpenter_security_group" {
  resource_id = aws_eks_cluster.this.vpc_config[0].cluster_security_group_id
  key         = "karpenter.sh/discovery"
  value       = local.cluster_name
}
