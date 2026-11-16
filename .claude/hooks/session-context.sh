#!/bin/bash
# 세션을 시작할 때 프로젝트 맥락을 알려 준다.
# SessionStart의 stdout은 Claude의 맥락에 들어가므로 짧고 사실만 적는다.
# AWS나 클러스터를 부르지 않는다(느리고 자격 증명이 필요하다). 로컬 파일에서 알 수 있는 것만 낸다.

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || exit 0

echo "=== 프로젝트 맥락 ==="
echo "프로젝트: ow-on-gpu (EKS vLLM 멀티 모델 서빙 측정 환경, ap-northeast-2)"
echo "규칙의 원본: AGENT.md (CLAUDE.md가 불러옴). AWS 리소스를 바꾸기 전에 plan 또는 diff를 보여 주고 승인을 받습니다."

BFF_TAG=$(sed -n 's/^bff_image_tag *= *"\(.*\)"/\1/p' infra/terraform/bff.auto.tfvars 2>/dev/null | head -1)
[ -n "$BFF_TAG" ] && echo "마지막으로 빌드한 BFF 이미지 태그: $BFF_TAG (배포 여부는 클러스터에서 확인)"

if git rev-parse --git-dir >/dev/null 2>&1; then
    LAST_COMMIT=$(git log -1 --format="%h %s (%cr)" 2>/dev/null)
    [ -n "$LAST_COMMIT" ] && echo "마지막 커밋: $LAST_COMMIT"
    BRANCH=$(git branch --show-current 2>/dev/null)
    [ -n "$BRANCH" ] && echo "브랜치: $BRANCH"
    CHANGES=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
    [ "${CHANGES:-0}" -gt 0 ] && echo "커밋하지 않은 변경: ${CHANGES}개"
else
    echo "git 저장소가 아닙니다."
fi

# 작업 준비 상태
[ -f infra/terraform/.kubeconfig ] && echo "kubectl: KUBECONFIG=infra/terraform/.kubeconfig 을 씁니다(공유 장비의 기본 컨텍스트를 바꾸지 않음)" \
    || echo "경고: infra/terraform/.kubeconfig 이 없습니다. terraform output의 update_kubeconfig 명령으로 만듭니다."
[ -d app/web/node_modules ] || echo "경고: app/web/node_modules 가 없습니다. app/web/build.sh 가 npm ci부터 실행합니다."

# 문서 상태
CLAUDE_COUNT=$(find . -name "CLAUDE.md" -not -path "./.git/*" -not -path "*/node_modules/*" -not -path "*/.terraform/*" 2>/dev/null | wc -l | tr -d ' ')
ADR_COUNT=$(find docs/decisions -name 'ADR-*.md' 2>/dev/null | wc -l | tr -d ' ')
RESULT_COUNT=$(find results -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
echo "CLAUDE.md ${CLAUDE_COUNT}개, ADR ${ADR_COUNT}개, 측정 결과 디렉터리 ${RESULT_COUNT}개"

echo "====================="
