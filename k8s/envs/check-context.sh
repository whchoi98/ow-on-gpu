#!/usr/bin/env bash
# kubectl이 향한 클러스터가 지금 고른 환경(TF_WORKSPACE, 없으면 default)의 클러스터인지 확인한다.
# 환경이 둘 이상이라 KUBECONFIG와 TF_WORKSPACE가 어긋나면 한 환경의 값을 다른 클러스터에 적용하게 된다.
set -euo pipefail
TF="$(cd "$(dirname "$0")/../../infra/terraform" && pwd)"

want=$(terraform -chdir="$TF" output -raw cluster_name)
# aws eks update-kubeconfig가 만든 kubeconfig에서 클러스터 이름은 ARN이다(...:cluster/<이름>).
have=$(kubectl config view --minify -o jsonpath='{.clusters[0].name}')
if [ "${have##*/}" != "$want" ]; then
  echo "kubectl이 향한 클러스터(${have##*/})가 환경 ${TF_WORKSPACE:-default}의 클러스터($want)와 다릅니다." >&2
  echo "KUBECONFIG와 TF_WORKSPACE를 같은 환경으로 맞춘 뒤 다시 실행하세요." >&2
  exit 1
fi
