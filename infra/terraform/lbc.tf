resource "aws_iam_policy" "lbc" {
  name   = "${var.cluster_name}-aws-load-balancer-controller"
  policy = file("${path.module}/files/lbc-iam-policy-v${var.lbc_chart_version}.json")
}

resource "aws_iam_role" "lbc" {
  name               = "${var.cluster_name}-aws-load-balancer-controller"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_iam_role_policy_attachment" "lbc" {
  role       = aws_iam_role.lbc.name
  policy_arn = aws_iam_policy.lbc.arn
}

resource "aws_eks_pod_identity_association" "lbc" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "kube-system"
  service_account = "aws-load-balancer-controller"
  role_arn        = aws_iam_role.lbc.arn
}

resource "helm_release" "lbc" {
  name       = "aws-load-balancer-controller"
  namespace  = "kube-system"
  repository = "https://aws.github.io/eks-charts"
  chart      = "aws-load-balancer-controller"
  version    = var.lbc_chart_version

  values = [yamlencode({
    clusterName = aws_eks_cluster.this.name
    region      = var.region
    vpcId       = data.aws_vpc.this.id
    serviceAccount = {
      name = "aws-load-balancer-controller"
    }
    # 애드온 노드 그룹의 taint
    tolerations = [{ key = "CriticalAddonsOnly", operator = "Exists" }]
  })]

  depends_on = [
    aws_eks_addon.coredns,
    aws_eks_pod_identity_association.lbc,
    aws_iam_role_policy_attachment.lbc,
  ]
}
