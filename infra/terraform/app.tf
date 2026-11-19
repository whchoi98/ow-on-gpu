# 앱 계층: CloudFront + WAF -> 내부 ALB -> BFF 파드(EKS) -> 게이트웨이, 깨우기 API
# BFF 파드와 내부 ALB는 k8s/bff가 만든다(ALB는 AWS Load Balancer Controller). 여기에는 그 둘이 쓰는 AWS 리소스가 있다.

# 게이트웨이 NLB는 AWS Load Balancer Controller가 만든다(k8s/gateway). 주소만 조회한다.
data "aws_lb" "gateway" {
  tags = {
    "service.k8s.aws/stack" = "inference/inference-gateway"
    "elbv2.k8s.aws/cluster" = local.cluster_name
  }
}

# ---------------------------------------------------------------- 보안 그룹

# 배치 작업은 BFF를 거치지 않고 게이트웨이 NLB를 직접 부른다. 배치 클라이언트에 이 보안 그룹을 붙인다.
resource "aws_security_group" "batch_client" {
  name        = "${local.cluster_name}-batch-client"
  tags        = { Name = "${local.cluster_name}-batch-client" }
  description = "Batch clients that call the gateway NLB directly"
  vpc_id      = data.aws_vpc.this.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 게이트웨이 NLB의 프런트엔드 보안 그룹. k8s/gateway/gateway.yaml이 이 이름을 어노테이션으로 지정한다.
# AWS Load Balancer Controller는 어노테이션의 이름을 보안 그룹 이름이 아닌 Name 태그에서 찾는다.
# BFF는 클러스터 안에서 게이트웨이의 Service를 직접 부르므로 NLB는 배치 클라이언트만 받는다.
# description은 바꾸면 보안 그룹이 다시 만들어지므로 그대로 둔다.
resource "aws_security_group" "gateway_nlb" {
  name        = "${local.cluster_name}-gateway-nlb"
  tags        = { Name = "${local.cluster_name}-gateway-nlb" }
  description = "Gateway NLB: only the BFF and batch clients"
  vpc_id      = data.aws_vpc.this.id

  ingress {
    from_port       = 80
    to_port         = 80
    protocol        = "tcp"
    security_groups = [aws_security_group.batch_client.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 내부 ALB의 프런트엔드 보안 그룹. k8s/bff의 Ingress가 이 이름을 어노테이션으로 지정한다.
# 들어오는 쪽은 CloudFront VPC origin만, 나가는 쪽은 BFF 파드가 쓰는 노드의 보안 그룹 8080만 연다.
resource "aws_security_group" "alb" {
  name        = "${local.cluster_name}-bff-alb"
  tags        = { Name = "${local.cluster_name}-bff-alb" }
  description = "Internal ALB: only the CloudFront VPC origin"
  vpc_id      = data.aws_vpc.this.id

  egress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_eks_cluster.this.vpc_config[0].cluster_security_group_id]
  }
}

# CloudFront는 VPC origin을 만들 때 이 이름의 보안 그룹을 VPC에 스스로 만든다.
data "aws_security_group" "cloudfront_vpc_origin" {
  name   = "CloudFront-VPCOrigins-Service-SG"
  vpc_id = data.aws_vpc.this.id

  depends_on = [aws_cloudfront_vpc_origin.bff_eks]
}

resource "aws_vpc_security_group_ingress_rule" "alb_from_cloudfront" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = data.aws_security_group.cloudfront_vpc_origin.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}

# ---------------------------------------------------------------- 로그인 (Cognito)

# CloudFront 주소는 공개되어 있다. /v1/* 요청은 이 사용자 풀이 발급한 액세스 토큰이 있어야 BFF를 통과한다.
# 사용자는 app/bff/create-user.sh로 만든다. 비밀번호를 Terraform 코드와 state에 남기지 않기 위해서다.
resource "aws_cognito_user_pool" "app" {
  name                = local.cluster_name
  user_pool_tier      = "LITE"
  username_attributes = ["email"]
  deletion_protection = "INACTIVE"

  # 가입을 막는다. 앱 클라이언트 ID는 정적 페이지에 드러나므로, 열어 두면 누구나 계정을 만들 수 있다.
  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }
}

# 브라우저가 쓰는 공개 클라이언트라서 시크릿을 두지 않는다.
resource "aws_cognito_user_pool_client" "web" {
  name                          = "${local.cluster_name}-web"
  user_pool_id                  = aws_cognito_user_pool.app.id
  generate_secret               = false
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 1

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

locals {
  cognito_issuer = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.app.id}"
}

# ---------------------------------------------------------------- BFF 이미지

# 이미지는 app/bff/build.sh가 올리고 k8s/bff/install.sh가 파드에 쓴다. 파드의 역할과 Pod Identity 연결은 bff_eks.tf에 있다.
resource "aws_ecr_repository" "bff" {
  name         = "${local.cluster_name}/bff"
  force_delete = true
}

# ---------------------------------------------------------------- 정적 페이지 (S3)

resource "aws_s3_bucket" "static" {
  bucket_prefix = "${local.cluster_name}-static-"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "static" {
  bucket                  = aws_s3_bucket.static.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 정적 페이지는 app/web(React, Vite)의 빌드 결과물이다. 먼저 app/web/build.sh를 실행한다.
locals {
  web_dist = "${path.module}/../../app/web/dist"
  web_content_types = {
    html  = "text/html; charset=utf-8"
    js    = "text/javascript; charset=utf-8"
    css   = "text/css; charset=utf-8"
    json  = "application/json"
    svg   = "image/svg+xml"
    png   = "image/png"
    ico   = "image/x-icon"
    woff2 = "font/woff2"
    txt   = "text/plain; charset=utf-8"
  }
}

# 빌드하지 않은 상태에서 적용하면 fileset이 비어 페이지가 지워진다. 그 전에 멈춘다.
resource "terraform_data" "web_build_guard" {
  lifecycle {
    precondition {
      condition     = fileexists("${local.web_dist}/index.html")
      error_message = "app/web/dist/index.html이 없습니다. app/web/build.sh를 먼저 실행하세요."
    }
  }
}

resource "aws_s3_object" "web" {
  for_each = fileset(local.web_dist, "**")

  bucket       = aws_s3_bucket.static.id
  key          = each.value
  source       = "${local.web_dist}/${each.value}"
  etag         = filemd5("${local.web_dist}/${each.value}")
  content_type = lookup(local.web_content_types, reverse(split(".", each.value))[0], "application/octet-stream")
  # assets/ 아래 파일은 이름에 해시가 들어 있어 오래 캐시한다. index.html은 매번 확인하게 해서
  # 다시 배포했을 때 CloudFront 캐시를 따로 지우지 않아도 되게 한다.
  cache_control = startswith(each.value, "assets/") ? "public, max-age=31536000, immutable" : "no-cache"

  depends_on = [terraform_data.web_build_guard]
}

moved {
  from = aws_s3_object.index
  to   = aws_s3_object.web["index.html"]
}

# 정적 페이지가 로그인할 때 읽는 설정. 둘 다 비밀이 아니다.
resource "aws_s3_object" "config" {
  bucket        = aws_s3_bucket.static.id
  key           = "config.json"
  content       = jsonencode({ region = local.region, userPoolClientId = aws_cognito_user_pool_client.web.id })
  content_type  = "application/json"
  cache_control = "no-cache"
}

resource "aws_cloudfront_origin_access_control" "static" {
  name                              = "${local.cluster_name}-static"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_s3_bucket_policy" "static" {
  bucket = aws_s3_bucket.static.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.static.arn}/*"
      Condition = { StringEquals = { "AWS:SourceArn" = aws_cloudfront_distribution.app.arn } }
    }]
  })
}

# ---------------------------------------------------------------- CloudFront와 WAF

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# CloudFront용 WAF는 us-east-1에만 만들 수 있다.
resource "aws_wafv2_web_acl" "app" {
  provider = aws.virginia
  name     = "${local.cluster_name}-app"
  scope    = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "rate-limit-per-ip"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.waf_rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${local.cluster_name}-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.cluster_name}-app"
    sampled_requests_enabled   = true
  }
}

resource "aws_cloudfront_distribution" "app" {
  enabled             = true
  comment             = "${local.cluster_name} app"
  default_root_object = "index.html"
  web_acl_id          = aws_wafv2_web_acl.app.arn
  price_class         = "PriceClass_200"

  origin {
    origin_id                = "static"
    domain_name              = aws_s3_bucket.static.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.static.id
  }

  # AWS Load Balancer Controller가 Ingress(app/bff)에서 만든 내부 ALB로 보낸다(bff_eks.tf).
  origin {
    origin_id   = "bff"
    domain_name = data.aws_lb.bff_eks.dns_name

    vpc_origin_config {
      vpc_origin_id = aws_cloudfront_vpc_origin.bff_eks.id
      # 오리진이 첫 바이트를 줄 때까지, 그리고 패킷 사이에 기다리는 시간. 기본값 30초는
      # Qwen 깨우기(약 5초)와 Decider 판단(최대 2초)이 겹치는 첫 요청에 여유가 적다.
      # 할당량을 올리지 않고 쓸 수 있는 최댓값 60초로 둔다. 배치는 이 경로를 쓰지 않는다.
      origin_read_timeout      = 60
      origin_keepalive_timeout = 60
    }
  }

  default_cache_behavior {
    target_origin_id       = "static"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
    compress               = true
  }

  ordered_cache_behavior {
    path_pattern               = "/v1/*"
    target_origin_id           = "bff"
    viewer_protocol_policy     = "redirect-to-https"
    allowed_methods            = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods             = ["GET", "HEAD"]
    cache_policy_id            = data.aws_cloudfront_cache_policy.disabled.id
    origin_request_policy_id   = data.aws_cloudfront_origin_request_policy.all_viewer_except_host.id
    response_headers_policy_id = aws_cloudfront_response_headers_policy.server_timing.id
    # 압축하면 CloudFront가 응답을 모았다가 내보내 스트리밍이 깨진다.
    compress = false
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}
