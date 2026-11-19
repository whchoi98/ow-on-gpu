# BFF는 EKS 파드로 실행한다(k8s/bff: Graviton NodePool, Deployment, Service, Ingress). 2026-11-15에 ECS Fargate에서 옮겼다.
# 여기에는 파드가 쓰는 IAM 역할과, AWS Load Balancer Controller가 만든 내부 ALB를 CloudFront에 연결하는 정의가 있다.
#
# 처음 만들 때의 순서
#   1. 이 파일의 IAM 역할과 Pod Identity 연결을 적용한다.
#   2. k8s/bff/install.sh apply로 파드와 Ingress를 적용한다. 컨트롤러가 내부 ALB를 만든다.
#   3. 아래의 ALB 조회와 VPC origin, CloudFront 배포판(app.tf)을 적용한다. ALB가 있어야 조회된다.

# BFF 파드의 역할. 네임스페이스 app의 ServiceAccount bff에 EKS Pod Identity로 연결한다.
# BFF가 AWS 자격 증명으로 부르는 API는 웹 검색 하나다(토큰 검증은 공개 JWKS만 읽는다).
resource "aws_iam_role" "bff_pod" {
  name               = "${local.cluster_name}-bff-pod"
  assume_role_policy = local.pod_identity_trust
}

# 모델이 web_search 도구를 부르면 BFF가 InvokeWebSearch로 검색한다(app/bff/websearch.py).
# 대상은 AWS가 소유한 도구라서 ARN의 계정 자리가 "aws"다. 정한 리전의 도구 하나만 허용한다.
# 리전을 바꾸면 k8s/bff/bff.yaml의 WEB_SEARCH_REGION도 함께 바꾼다.
resource "aws_iam_role_policy" "bff_pod_web_search" {
  count = var.web_search_region == "" ? 0 : 1
  name  = "web-search"
  role  = aws_iam_role.bff_pod.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "InvokeWebSearch"
      Effect   = "Allow"
      Action   = "bedrock-agentcore:InvokeWebSearch"
      Resource = "arn:${data.aws_partition.current.partition}:bedrock-agentcore:${var.web_search_region}:aws:tool/web-search.v1"
    }]
  })
}

resource "aws_eks_pod_identity_association" "bff" {
  cluster_name    = aws_eks_cluster.this.name
  namespace       = "app"
  service_account = "bff"
  role_arn        = aws_iam_role.bff_pod.arn
}

# Ingress(app/bff)에서 AWS Load Balancer Controller가 만든 내부 ALB. Private 서브넷에 있다. 주소와 ARN만 조회한다.
data "aws_lb" "bff_eks" {
  tags = {
    "ingress.k8s.aws/stack" = "app/bff"
    "elbv2.k8s.aws/cluster" = local.cluster_name
  }
}

resource "aws_cloudfront_vpc_origin" "bff_eks" {
  vpc_origin_endpoint_config {
    name                   = "${local.cluster_name}-bff-pods-alb"
    arn                    = data.aws_lb.bff_eks.arn
    http_port              = 80
    https_port             = 443
    origin_protocol_policy = "http-only"

    origin_ssl_protocols {
      items    = ["TLSv1.2"]
      quantity = 1
    }
  }
}

# 전환할 때는 count로 만들었다. 같은 리소스를 다시 만들지 않도록 주소만 옮긴다.
moved {
  from = aws_cloudfront_vpc_origin.bff_eks[0]
  to   = aws_cloudfront_vpc_origin.bff_eks
}
