#!/usr/bin/env bash
# Strands Decider를 배포한다(Deployment, Service, HTTPRoute).
# 이미지는 strands-labs/strands-decider 저장소의 deploy/sagemaker/Dockerfile로 빌드해 ECR에 올린 것을 쓴다.
# 이미지 주소에 계정 ID가 들어가므로 매니페스트의 ${DECIDER_IMAGE} 자리를 Terraform 출력으로 채운다.
#
#   ./install.sh build    저장소의 v$VERSION 태그를 받아 linux/amd64 이미지를 빌드하고 ECR에 올린다
#   ./install.sh render   채운 매니페스트를 표준 출력으로 낸다
#   ./install.sh diff     클러스터와의 차이를 본다 (kubectl diff)
#   ./install.sh apply    적용한다. 파드가 다시 뜨는 동안 BFF는 Decider 응답이 없는 경우의 기본 처리를 쓴다
#
# 먼저 ECR 저장소가 있어야 한다: terraform -chdir=infra/terraform apply -target=aws_ecr_repository.decider
# GPU 노드는 amd64다. arm64 장비에서 build를 하려면 amd64 에뮬레이션(binfmt)이 등록되어 있어야 한다.
set -euo pipefail
cd "$(dirname "$0")"
TF=../../infra/terraform
REGION=ap-northeast-2
# v2 체크포인트(decision_config.json)는 strands-decider 0.4.0 이상에서만 읽힌다.
VERSION=0.4.0

repository() { terraform -chdir="$TF" output -raw decider_repository_url; }

build() {
  local repo source
  repo=$(repository)
  if aws ecr describe-images --region "$REGION" --repository-name "${repo#*/}" \
    --image-ids "imageTag=$VERSION" >/dev/null 2>&1; then
    echo "$repo:$VERSION 이미지가 이미 있습니다."
    return
  fi
  source=$(mktemp -d)
  # 트랩은 함수가 끝난 뒤에 실행되어 local 변수를 보지 못한다. 경로를 지금 넣어 둔다.
  trap "rm -rf '$source'" EXIT
  git clone --quiet --depth 1 --branch "v$VERSION" https://github.com/strands-labs/strands-decider.git "$source"
  aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${repo%%/*}"
  # 저장소 안에 .git을 넣지 않고 빌드하므로 패키지 버전을 인자로 준다(Dockerfile의 PACKAGE_VERSION).
  docker buildx build --platform linux/amd64 --provenance=false \
    --build-arg "PACKAGE_VERSION=$VERSION" \
    -f "$source/deploy/sagemaker/Dockerfile" -t "$repo:$VERSION" --push "$source"
  echo "pushed $repo:$VERSION"
}

render() {
  DECIDER_IMAGE="$(repository):$VERSION" envsubst '$DECIDER_IMAGE' < <(kubectl kustomize .)
}

case "${1:-}" in
  build) build ;;
  render) render ;;
  diff) render | kubectl diff -f - ;;
  apply) render | kubectl apply -f - ;;
  *)
    echo "사용법: $0 build|render|diff|apply" >&2
    exit 2
    ;;
esac
