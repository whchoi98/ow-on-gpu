# 모델 가중치(models/)와 compile 캐시(vllm-cache/)를 담는 버킷. 이름은 고유 접미사로 만든다.
resource "aws_s3_bucket" "models" {
  bucket_prefix = "${var.cluster_name}-"
}

resource "aws_s3_bucket_public_access_block" "models" {
  bucket                  = aws_s3_bucket.models.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

locals {
  model_object_arns = [
    "${aws_s3_bucket.models.arn}/models/*",
    "${aws_s3_bucket.models.arn}/vllm-cache/*",
  ]

  # k8s/base/namespaces.yaml, 이후 단계의 ServiceAccount 이름과 맞춘다.
  model_reader_service_accounts = ["gemma", "qwen", "decider"]
  model_writer_service_accounts = ["model-sync", "cache-publish"]
}

# 서빙 파드: 읽기 전용
resource "aws_iam_role" "model_reader" {
  name               = "${var.cluster_name}-model-reader"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_iam_role_policy" "model_reader" {
  name = "s3-read"
  role = aws_iam_role.model_reader.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = local.model_object_arns
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation"]
        Resource = aws_s3_bucket.models.arn
      },
    ]
  })
}

resource "aws_eks_pod_identity_association" "model_reader" {
  for_each = toset(local.model_reader_service_accounts)

  cluster_name    = aws_eks_cluster.this.name
  namespace       = "inference"
  service_account = each.key
  role_arn        = aws_iam_role.model_reader.arn
}

# 적재 Job과 캐시 게시 Job: 쓰기
resource "aws_iam_role" "model_writer" {
  name               = "${var.cluster_name}-model-writer"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_iam_role_policy" "model_writer" {
  name = "s3-write"
  role = aws_iam_role.model_writer.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"]
        Resource = local.model_object_arns
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket", "s3:GetBucketLocation", "s3:ListBucketMultipartUploads"]
        Resource = aws_s3_bucket.models.arn
      },
    ]
  })
}

resource "aws_eks_pod_identity_association" "model_writer" {
  for_each = toset(local.model_writer_service_accounts)

  cluster_name    = aws_eks_cluster.this.name
  namespace       = "model-jobs"
  service_account = each.key
  role_arn        = aws_iam_role.model_writer.arn
}
