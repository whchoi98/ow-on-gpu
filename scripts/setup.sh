#!/bin/bash
# 이 저장소에서 작업을 시작할 때 한 번 실행한다.
# 사용법: bash scripts/setup.sh
# AWS 리소스를 만들거나 바꾸지 않는다. 로컬 도구를 확인하고 훅과 화면 의존성만 준비한다.

set -e

cd "$(dirname "$0")/.."

echo "=== 작업 환경 준비 ==="

# 훅과 시험이 쓰는 도구
command -v jq >/dev/null 2>&1 || { echo "ERROR: jq가 필요합니다 (훅이 이벤트 JSON을 읽는 데 씁니다)"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3가 필요합니다 (시험이 json.tool을 씁니다)"; exit 1; }
[ "${BASH_VERSINFO[0]}" -ge 4 ] || { echo "ERROR: Bash 4 이상이 필요합니다 (지금 $BASH_VERSION)"; exit 1; }

# 배포와 측정에 쓰는 도구. 없어도 문서 작업은 할 수 있으므로 경고만 한다.
for tool in aws kubectl terraform docker node npm; do
    command -v "$tool" >/dev/null 2>&1 || echo "WARNING: $tool 이 없습니다 (docs/onboarding.md의 사전 요구 사항)"
done

chmod +x .claude/hooks/*.sh scripts/*.sh tests/run-all.sh tests/*/*.sh
echo "훅과 스크립트에 실행 권한을 줬습니다"

# git 훅(commit-msg, pre-commit)
if [ -d ".git" ]; then
    bash scripts/install-hooks.sh
else
    echo "git 저장소가 아니어서 git 훅은 설치하지 않았습니다 (git init 뒤에 bash scripts/install-hooks.sh)"
fi

# 환경마다 다른 값이 든 파일은 저장소에 없다. 예시를 복사해 두고 무엇을 채울지 알린다.
for example in k8s/base/params.yaml.example k8s/observability/prometheus.yml.example bench/coldstart/k8s/storage-s3.yaml.example \
               jobs/model-sync/params.env.example infra/terraform/terraform.tfvars.example \
               k8s/envs/tokyo/base/params.yaml.example k8s/envs/tokyo/observability/prometheus.yml.example; do
    target="${example%.example}"
    if [ ! -f "$target" ] && [ -f "$example" ]; then
        cp "$example" "$target"
        echo "예시를 복사했습니다: $target (자리 표시를 실제 값으로 바꿉니다. docs/onboarding.md)"
    fi
done

# 확인용 페이지의 의존성. 잠금 파일대로만 설치한다.
if command -v npm >/dev/null 2>&1 && [ ! -d app/web/node_modules ]; then
    npm ci --prefix app/web
fi

echo "=== 준비 완료 ==="
echo "다음 순서:"
echo "  1. AGENT.md와 CLAUDE.md, docs/onboarding.md를 읽습니다"
echo "  2. 하네스 시험: bash tests/run-all.sh"
echo "  3. 화면 시험: npm test --prefix app/web"
echo "  4. kubectl은 KUBECONFIG=infra/terraform/.kubeconfig 으로 씁니다"
