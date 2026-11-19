# 환경은 Terraform 작업 공간(workspace)으로 고른다. default가 서울이고 리전을 더할 때 작업 공간을 하나 더한다.
# 상태 파일도 작업 공간마다 따로다(default는 terraform.tfstate, 그 밖은 terraform.tfstate.d/<이름>/terraform.tfstate).
#
# 명령마다 TF_WORKSPACE=<이름>을 붙여 고른다. `terraform workspace select`로 바꿔 두면 그 뒤의 명령이 모두 그 환경을 향하므로 쓰지 않는다.
# app/bff/build.sh, app/bff/create-user.sh, k8s/bff/install.sh, k8s/gateway/install.sh도 같은 변수를 읽는다.
#
# cluster_name은 계정 전체에서 고유해야 한다. IAM 역할과 정책, Karpenter 스택의 KarpenterNodeRole-<클러스터>,
# CloudFront용 WAF와 OAC의 이름에 들어가고, 이 리소스들은 리전이 달라도 이름이 겹치면 만들어지지 않는다.
locals {
  environments = {
    default = {
      region       = "ap-northeast-2"
      cluster_name = "ow-on-gpu"
      # 컨트롤 플레인 ENI와 애드온 노드 그룹을 둘 AZ. EKS 컨트롤 플레인이 2d를 지원하는지 확인하지 못해 2d는 뺀다
      # (eks 엔드포인트 서비스는 2d 미지원). Karpenter 노드는 네 AZ를 모두 쓴다.
      control_plane_azs = ["ap-northeast-2a", "ap-northeast-2b", "ap-northeast-2c"]
    }
    tokyo = {
      region       = "ap-northeast-1"
      cluster_name = "ow-on-gpu-tokyo"
      # 도쿄에서 이 계정이 쓸 수 있는 AZ는 이 셋이다. g6e.4xlarge와 g6.xlarge는 1a와 1c에서만 제공된다(2026-11-19 확인).
      control_plane_azs = ["ap-northeast-1a", "ap-northeast-1c", "ap-northeast-1d"]
    }
  }

  env               = local.environments[terraform.workspace]
  region            = local.env.region
  cluster_name      = local.env.cluster_name
  control_plane_azs = local.env.control_plane_azs
}
