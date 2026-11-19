#!/usr/bin/env bash
# BFF를 EKS 파드로 배포한다(Graviton NodePool, Deployment, Service, Ingress).
# 매니페스트의 ${...} 자리는 Terraform 출력에서 읽은 값으로 채운다. 계정 ID가 든 값을 저장소 파일에 적지 않기 위해서다.
#
#   ./install.sh render   채운 매니페스트를 표준 출력으로 낸다
#   ./install.sh diff     클러스터와의 차이를 본다 (kubectl diff)
#   ./install.sh apply    적용한다. Graviton 노드가 뜨고 AWS Load Balancer Controller가 내부 ALB를 만든다
#
# 환경은 TF_WORKSPACE로 고른다(infra/terraform/environments.tf). 없으면 서울(default)이다.
# diff와 apply는 kubectl이 향한 클러스터가 그 환경의 클러스터인지 먼저 확인한다.
#
# 먼저 infra/terraform을 적용해 Pod Identity 연결(네임스페이스 app, ServiceAccount bff)이 있어야 한다.
# 파드가 만들어질 때 연결이 없으면 자격 증명이 주입되지 않아 웹 검색이 실패한다.
set -euo pipefail
cd "$(dirname "$0")"
TF=../../infra/terraform
# 이미지 태그 파일은 환경마다 따로다. app/bff/build.sh가 같은 규칙으로 적는다.
ENV=${TF_WORKSPACE:-default}
TAG_FILE="$TF/bff.auto.tfvars"
[ "$ENV" = default ] || TAG_FILE="$TF/bff.$ENV.tfvars"

render() {
  local tag pool
  tag=$(sed -n 's/^bff_image_tag *= *"\(.*\)"$/\1/p' "$TAG_FILE")
  [ -n "$tag" ] || { echo "$TAG_FILE에 이미지 태그가 없습니다. app/bff/build.sh를 먼저 실행하세요." >&2; exit 1; }
  pool=$(terraform -chdir="$TF" output -raw cognito_user_pool_id)
  # 사용자 풀 ID는 <리전>_<값> 꼴이다. 발급자 주소의 리전을 여기서 얻는다.
  CLUSTER_NAME="$(terraform -chdir="$TF" output -raw cluster_name)" \
  BFF_IMAGE="$(terraform -chdir="$TF" output -raw bff_repository_url):$tag" \
  COGNITO_ISSUER="https://cognito-idp.${pool%%_*}.amazonaws.com/$pool" \
  COGNITO_CLIENT_ID="$(terraform -chdir="$TF" output -raw cognito_client_id)" \
  ALB_LOG_BUCKET="$(terraform -chdir="$TF" output -raw alb_log_bucket)" \
    envsubst '$CLUSTER_NAME $BFF_IMAGE $COGNITO_ISSUER $COGNITO_CLIENT_ID $ALB_LOG_BUCKET' < <(kubectl kustomize .)
}

case "${1:-}" in
  render) render ;;
  diff) ../envs/check-context.sh && render | kubectl diff -f - ;;
  apply) ../envs/check-context.sh && render | kubectl apply -f - ;;
  *)
    echo "사용법: $0 render|diff|apply" >&2
    exit 2
    ;;
esac
