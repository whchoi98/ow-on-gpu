#!/usr/bin/env bash
# BFF 이미지를 빌드해 ECR에 올리고, 태그를 infra/terraform/bff.auto.tfvars에 적는다.
# 그 태그로 파드를 바꾸려면 이어서 k8s/bff/install.sh diff, apply를 실행한다(BFF는 EKS 파드다).
# ECR 저장소가 먼저 있어야 한다: terraform -chdir=infra/terraform apply -target=aws_ecr_repository.bff
# 작업 장비가 arm64이므로 이미지도 arm64다. 파드는 Graviton NodePool(app)에서 실행한다.
# 환경은 TF_WORKSPACE로 고른다(infra/terraform/environments.tf). 저장소와 태그 파일이 환경마다 따로다.
set -euo pipefail
cd "$(dirname "$0")"

TF=../../infra/terraform
ENV=${TF_WORKSPACE:-default}
TAG_FILE="$TF/bff.auto.tfvars"
[ "$ENV" = default ] || TAG_FILE="$TF/bff.$ENV.tfvars"

REPOSITORY=$(terraform -chdir="$TF" output -raw bff_repository_url)
# 저장소 주소는 <계정>.dkr.ecr.<리전>.amazonaws.com/<이름> 꼴이다. 로그인할 리전을 여기서 얻는다.
REGION=$(cut -d. -f4 <<<"$REPOSITORY")
TAG=$(date -u +%Y%m%d-%H%M%S)

docker build -t "$REPOSITORY:$TAG" .
docker run --rm "$REPOSITORY:$TAG" python -m unittest test_bff
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPOSITORY%%/*}"
docker push "$REPOSITORY:$TAG"

echo "bff_image_tag = \"$TAG\"" > "$TAG_FILE"
echo "pushed $REPOSITORY:$TAG"
