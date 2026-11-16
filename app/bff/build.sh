#!/usr/bin/env bash
# BFF 이미지를 빌드해 ECR에 올리고, 태그를 infra/terraform/bff.auto.tfvars에 적는다.
# 그 태그로 파드를 바꾸려면 이어서 k8s/bff/install.sh diff, apply를 실행한다(BFF는 EKS 파드다).
# ECR 저장소가 먼저 있어야 한다: terraform -chdir=infra/terraform apply -target=aws_ecr_repository.bff
# 작업 장비가 arm64이므로 이미지도 arm64다. 파드는 Graviton NodePool(app)에서 실행한다.
set -euo pipefail
cd "$(dirname "$0")"

REGION=ap-northeast-2
REPOSITORY=$(terraform -chdir=../../infra/terraform output -raw bff_repository_url)
TAG=$(date -u +%Y%m%d-%H%M%S)

docker build -t "$REPOSITORY:$TAG" .
docker run --rm "$REPOSITORY:$TAG" python -m unittest test_bff
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "${REPOSITORY%%/*}"
docker push "$REPOSITORY:$TAG"

echo "bff_image_tag = \"$TAG\"" > ../../infra/terraform/bff.auto.tfvars
echo "pushed $REPOSITORY:$TAG"
