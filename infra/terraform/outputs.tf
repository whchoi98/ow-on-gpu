output "cluster_name" {
  value = aws_eks_cluster.this.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.this.endpoint
}

output "update_kubeconfig" {
  value = "aws eks update-kubeconfig --region ${var.region} --name ${aws_eks_cluster.this.name}"
}

output "model_bucket" {
  value = aws_s3_bucket.models.bucket
}

output "karpenter_node_role_name" {
  value = local.karpenter_node_role_name
}

output "vpc_id" {
  value = data.aws_vpc.this.id
}

output "bff_repository_url" {
  value = aws_ecr_repository.bff.repository_url
}

output "app_url" {
  value = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "bff_alb_dns" {
  value = data.aws_lb.bff_eks.dns_name
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.app.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "amp_workspace_id" {
  value = aws_prometheus_workspace.this.id
}

output "amp_endpoint" {
  value = aws_prometheus_workspace.this.prometheus_endpoint
}

output "alb_log_bucket" {
  value = aws_s3_bucket.alb_logs.bucket
}
