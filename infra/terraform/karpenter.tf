# 노드 역할(KarpenterNodeRole-<클러스터>), 컨트롤러 정책 6개, 중단 알림 큐와 EventBridge 규칙은
# Karpenter가 버전마다 배포하는 공식 CloudFormation 템플릿을 그대로 쓴다. 권한이 버전에 맞게 유지된다.
resource "aws_cloudformation_stack" "karpenter" {
  name = "Karpenter-${var.cluster_name}"
  # CloudFormation은 템플릿 끝에 줄바꿈을 하나 붙여 돌려준다. 같게 맞추지 않으면 plan마다 변경으로 잡힌다.
  template_body = "${trimspace(file("${path.module}/files/karpenter-cloudformation-v${var.karpenter_version}.yaml"))}\n"
  capabilities  = ["CAPABILITY_NAMED_IAM"]

  parameters = {
    ClusterName = var.cluster_name
  }
}

locals {
  karpenter_node_role_name = "KarpenterNodeRole-${var.cluster_name}"
  iam_arn_prefix           = "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}"

  # 템플릿의 ManagedPolicyName: KarpenterController<이름>Policy-<클러스터>
  karpenter_controller_policies = [
    "NodeLifecycle",
    "IAMIntegration",
    "EKSIntegration",
    "Interruption",
    "ResourceDiscovery",
    "ZonalShift",
  ]

  pod_identity_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

resource "aws_iam_role" "karpenter" {
  name               = "${var.cluster_name}-karpenter"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_iam_role_policy_attachment" "karpenter" {
  for_each = toset(local.karpenter_controller_policies)

  role       = aws_iam_role.karpenter.name
  policy_arn = "${local.iam_arn_prefix}:policy/KarpenterController${each.key}Policy-${var.cluster_name}"

  depends_on = [aws_cloudformation_stack.karpenter]
}

resource "aws_eks_pod_identity_association" "karpenter" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "kube-system"
  service_account = "karpenter"
  role_arn        = aws_iam_role.karpenter.arn
}

resource "aws_eks_access_entry" "karpenter_node" {
  cluster_name  = aws_eks_cluster.this.name
  principal_arn = "${local.iam_arn_prefix}:role/${local.karpenter_node_role_name}"
  type          = "EC2_LINUX"

  depends_on = [aws_cloudformation_stack.karpenter]
}

data "aws_ecrpublic_authorization_token" "this" {
  provider = aws.virginia
}

resource "helm_release" "karpenter" {
  name       = "karpenter"
  namespace  = "kube-system"
  repository = "oci://public.ecr.aws/karpenter"
  chart      = "karpenter"
  version    = var.karpenter_version

  # 로컬에 만료된 public.ecr.aws 자격 증명이 남아 있으면 익명 pull이 403으로 실패한다.
  repository_username = data.aws_ecrpublic_authorization_token.this.user_name
  repository_password = data.aws_ecrpublic_authorization_token.this.password

  values = [yamlencode({
    settings = {
      clusterName       = aws_eks_cluster.this.name
      interruptionQueue = var.cluster_name
    }
    controller = {
      resources = {
        requests = { cpu = "1", memory = "1Gi" }
        limits   = { cpu = "1", memory = "1Gi" }
      }
    }
  })]

  # 토큰은 plan마다 새로 발급되어 매번 변경으로 잡힌다. 차트를 받을 때만 필요하므로 무시한다.
  # 차트 버전을 올릴 때는 새 토큰이 들어가도록 이 블록을 잠시 뺀다.
  lifecycle {
    ignore_changes = [repository_password]
  }

  depends_on = [
    aws_eks_addon.coredns,
    aws_eks_pod_identity_association.karpenter,
    aws_eks_access_entry.karpenter_node,
    aws_iam_role_policy_attachment.karpenter,
    aws_ec2_tag.karpenter_subnet,
    aws_ec2_tag.karpenter_security_group,
  ]
}
