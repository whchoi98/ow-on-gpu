resource "aws_iam_role" "cluster" {
  name = "${var.cluster_name}-cluster"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "eks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "cluster" {
  role       = aws_iam_role.cluster.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonEKSClusterPolicy"
}

resource "aws_eks_cluster" "this" {
  name     = var.cluster_name
  version  = var.kubernetes_version
  role_arn = aws_iam_role.cluster.arn

  # vpc-cni, kube-proxy, coredns를 EKS 애드온으로만 관리한다.
  bootstrap_self_managed_addons = false

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  vpc_config {
    subnet_ids              = local.control_plane_subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = var.api_public_access_cidrs
  }

  lifecycle {
    precondition {
      condition     = length(local.control_plane_subnet_ids) == length(var.control_plane_azs)
      error_message = "control_plane_azs마다 Private 서브넷이 하나씩 있어야 합니다."
    }
  }

  depends_on = [aws_iam_role_policy_attachment.cluster]
}

# 노드가 뜨기 전에 있어야 하는 애드온
resource "aws_eks_addon" "before_nodes" {
  for_each = toset(["vpc-cni", "kube-proxy", "eks-pod-identity-agent"])

  cluster_name  = aws_eks_cluster.this.name
  addon_name    = each.key
  addon_version = var.addon_versions[each.key]

  # NetworkPolicy는 VPC CNI에서 기본으로 꺼져 있다. 켜지 않으면 k8s/sleep-controller의 정책이 적용되지 않는다.
  configuration_values = each.key == "vpc-cni" ? jsonencode({ enableNetworkPolicy = "true" }) : null
}

# CoreDNS는 올라갈 노드가 있어야 ACTIVE가 된다.
resource "aws_eks_addon" "coredns" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "coredns"
  addon_version = var.addon_versions["coredns"]

  depends_on = [aws_eks_node_group.addons]
}

resource "aws_iam_role" "addons_node" {
  name = "${var.cluster_name}-addons-node"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "addons_node" {
  for_each = toset([
    "AmazonEKSWorkerNodePolicy",
    "AmazonEKS_CNI_Policy",
    "AmazonEC2ContainerRegistryPullOnly",
    "AmazonSSMManagedInstanceCore",
  ])

  role       = aws_iam_role.addons_node.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.key}"
}

# Karpenter는 자신이 만든 노드에서 실행할 수 없으므로 Karpenter, CoreDNS, LBC용 노드를 따로 둔다.
# 게이트웨이와 EPP는 여기가 아닌 Karpenter의 system NodePool에 올린다.
resource "aws_eks_node_group" "addons" {
  cluster_name    = aws_eks_cluster.this.name
  node_group_name = "addons"
  node_role_arn   = aws_iam_role.addons_node.arn
  subnet_ids      = local.control_plane_subnet_ids

  ami_type       = "AL2023_ARM_64_STANDARD"
  instance_types = [var.addons_node_instance_type]
  capacity_type  = "ON_DEMAND"

  scaling_config {
    desired_size = 2
    min_size     = 2
    max_size     = 3
  }

  update_config {
    max_unavailable = 1
  }

  taint {
    key    = "CriticalAddonsOnly"
    value  = "true"
    effect = "NO_SCHEDULE"
  }

  depends_on = [
    aws_iam_role_policy_attachment.addons_node,
    aws_eks_addon.before_nodes,
  ]
}
