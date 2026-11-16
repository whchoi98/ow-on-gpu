#!/usr/bin/env bash
# 게이트웨이 계층을 설치한다. 버전은 docs/00-versions.md의 "버전 조합" 표와 맞춘다.
#
#   ./install.sh render   Helm 차트를 렌더링해 표준 출력으로 낸다(kubectl diff -f - 로 미리 볼 때 쓴다)
#   ./install.sh apply    CRD, agentgateway, 모델별 EPP와 InferencePool, Gateway를 순서대로 적용한다
set -euo pipefail
cd "$(dirname "$0")/.."

AGENTGATEWAY_VERSION=v1.7.0
ROUTER_CHART_VERSION=v1.0.0
NAMESPACE=inference

charts() {
  # $1: template 또는 "upgrade --install"
  helm $1 agentgateway oci://cr.agentgateway.dev/charts/agentgateway \
    --version "$AGENTGATEWAY_VERSION" --namespace agentgateway-system \
    -f gateway/agentgateway-values.yaml ${2:-}
  for model in gemma qwen; do
    helm $1 "$model" oci://ghcr.io/llm-d/charts/llm-d-router-gateway \
      --version "$ROUTER_CHART_VERSION" --namespace "$NAMESPACE" \
      -f "$model/epp-values.yaml" ${2:-}
  done
}

case "${1:-}" in
  render)
    charts template
    ;;
  apply)
    kubectl apply --server-side -k gateway/crds
    helm upgrade --install agentgateway-crds oci://cr.agentgateway.dev/charts/agentgateway-crds \
      --version "$AGENTGATEWAY_VERSION" --namespace agentgateway-system --create-namespace
    charts "upgrade --install" --wait
    kubectl apply -k gateway
    kubectl apply -k gemma
    kubectl apply -k qwen
    ;;
  *)
    echo "사용법: $0 render|apply" >&2
    exit 2
    ;;
esac
