variable "region" {
  type    = string
  default = "ap-northeast-2"
}

variable "cluster_name" {
  type    = string
  default = "ow-on-gpu"
}

variable "vpc_name" {
  description = "CDK 스택 EksVpcStack(infra/cdk-vpc)이 만든 VPC의 Name 태그"
  type        = string
  default     = "eks-vpc"
}

# 버전은 docs/00-versions.md의 "버전 조합" 표와 맞춘다.
variable "kubernetes_version" {
  type    = string
  default = "1.37"
}

variable "addon_versions" {
  type = map(string)
  default = {
    "vpc-cni"                = "v1.23.3-eksbuild.1"
    "kube-proxy"             = "v1.37.0-eksbuild.39"
    "eks-pod-identity-agent" = "v1.4.1-eksbuild.3"
    "coredns"                = "v1.14.7-eksbuild.35"
    # 8단계의 콜드 스타트 기준 구성에서만 쓴다(observability.tf)
    "aws-mountpoint-s3-csi-driver" = "v2.9.2-eksbuild.1"
  }
}

variable "karpenter_version" {
  description = "files/karpenter-cloudformation-v<버전>.yaml도 같은 버전이어야 한다"
  type        = string
  default     = "1.15.2"
}

variable "lbc_chart_version" {
  description = "files/lbc-iam-policy-v<버전>.json도 같은 버전이어야 한다"
  type        = string
  default     = "3.6.3"
}

variable "control_plane_azs" {
  description = "컨트롤 플레인 ENI와 애드온 노드 그룹을 둘 AZ. EKS 컨트롤 플레인이 2d를 지원하는지 확인하지 못해 2d는 뺀다(eks 엔드포인트 서비스는 2d 미지원). Karpenter 노드는 네 AZ를 모두 쓴다"
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2b", "ap-northeast-2c"]
}

variable "api_public_access_cidrs" {
  description = "EKS API 퍼블릭 엔드포인트에 접근을 허용할 CIDR. 작업 장비의 외부 IP만 넣는다"
  type        = list(string)
}

variable "addons_node_instance_type" {
  description = "Karpenter, CoreDNS, LBC가 올라가는 관리형 노드 그룹의 인스턴스 유형. 노드 그룹의 AMI가 arm64이므로 Graviton 유형만 쓴다"
  type        = string
  default     = "m7g.large"
}

variable "bff_image_tag" {
  description = "ECR에 올린 BFF 이미지 태그. app/bff/build.sh가 bff.auto.tfvars에 적고 k8s/bff/install.sh가 읽어 파드의 이미지로 쓴다"
  type        = string
  default     = "unset"
}

variable "waf_rate_limit" {
  description = "IP 하나가 5분 동안 보낼 수 있는 요청 수. 넘으면 WAF가 차단한다"
  type        = number
  default     = 300
}

variable "web_search_region" {
  description = "BFF가 Amazon Bedrock AgentCore Web Search(InvokeWebSearch)를 부를 리전. 서울 리전에는 이 API가 없다. 빈 문자열이면 웹 검색을 쓰지 않는다"
  type        = string
  default     = "us-east-1"
}
