#!/usr/bin/env bash
# 정적 페이지를 빌드한다. 결과물(dist/)은 infra/terraform/app.tf가 S3에 올린다.
#   ./build.sh && terraform -chdir=../../infra/terraform apply
set -euo pipefail
cd "$(dirname "$0")"
npm ci --no-audit --no-fund
npm test
npm run build
