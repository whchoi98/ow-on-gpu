# 8단계: 관측(Amazon Managed Service for Prometheus)과 측정에 필요한 리소스

# ---------------------------------------------------------------- 지표 수집

resource "aws_prometheus_workspace" "this" {
  alias = var.cluster_name
}

# k8s/observability의 수집기(Prometheus agent)가 이 역할로 remote write를 서명한다.
resource "aws_iam_role" "metrics_collector" {
  name               = "${var.cluster_name}-metrics-collector"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_iam_role_policy" "metrics_collector" {
  name = "amp-remote-write"
  role = aws_iam_role.metrics_collector.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["aps:RemoteWrite"]
      Resource = aws_prometheus_workspace.this.arn
    }]
  })
}

resource "aws_eks_pod_identity_association" "metrics_collector" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "monitoring"
  service_account = "metrics-collector"
  role_arn        = aws_iam_role.metrics_collector.arn
}

# ---------------------------------------------------------------- 콜드 스타트 기준 구성

# 1부의 기준 구성은 Mountpoint for Amazon S3(FUSE)로 모델 버킷을 마운트하고 vLLM 기본 로더로 읽는다.
# 같은 조건으로 재려고 CSI 드라이버를 설치한다. 평소의 서빙 경로(runai_streamer)는 이 드라이버를 쓰지 않는다.
# 드라이버는 서빙 파드와 같은 읽기 전용 역할로 버킷을 읽는다.
resource "aws_eks_addon" "s3_csi" {
  cluster_name  = aws_eks_cluster.this.name
  addon_name    = "aws-mountpoint-s3-csi-driver"
  addon_version = var.addon_versions["aws-mountpoint-s3-csi-driver"]

  pod_identity_association {
    role_arn        = aws_iam_role.model_reader.arn
    service_account = "s3-csi-driver-sa"
  }

  depends_on = [aws_eks_addon.before_nodes, aws_eks_node_group.addons]
}

# ---------------------------------------------------------------- 구간별 TTFT 측정

# ALB 접근 로그. 요청마다 ALB가 쓴 시간(request_processing_time, target_processing_time)이 남는다.
# BFF 로그와는 X-Amzn-Trace-Id로 잇는다(bench/ttft).
data "aws_elb_service_account" "this" {}

resource "aws_s3_bucket" "alb_logs" {
  bucket_prefix = "${var.cluster_name}-alb-logs-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket                  = aws_s3_bucket.alb_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "expire"
    status = "Enabled"
    filter {}
    expiration {
      days = 14
    }
  }
}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    # 서울 리전의 문서상 주체는 ELB 계정이지만 그것만으로는 "Access Denied for bucket"으로 거절됐다(2026-11-14).
    # 로그 전달 서비스 주체를 함께 허용한다.
    Statement = [
      {
        Effect    = "Allow"
        Principal = { AWS = data.aws_elb_service_account.this.arn }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.alb_logs.arn}/bff/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
      },
      {
        Effect    = "Allow"
        Principal = { Service = "logdelivery.elasticloadbalancing.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.alb_logs.arn}/bff/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
      },
    ]
  })
}

# CloudFront가 응답에 Server-Timing 헤더를 붙인다. cdn-upstream-fbl(오리진의 첫 바이트까지)과
# cdn-downstream-fbl(엣지가 첫 바이트를 내보내기까지)로 CloudFront 구간을 요청마다 알 수 있다.
resource "aws_cloudfront_response_headers_policy" "server_timing" {
  name = "${var.cluster_name}-server-timing"

  server_timing_headers_config {
    enabled       = true
    sampling_rate = 100
  }
}
