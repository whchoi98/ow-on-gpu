#!/bin/bash
# 파일을 고친 뒤 함께 맞춰야 할 문서를 알려 준다.
# PostToolUse(Write|Edit)가 부른다. Claude Code는 이벤트를 stdin의 JSON으로 넘긴다.
# 손으로 돌리거나 시험할 때는 경로를 인자로 준다.
# 모듈 문서(CLAUDE.md)는 고친 파일의 디렉터리에서 모듈 루트까지 올라가며 찾는다.

if [ "$#" -ge 1 ]; then
    FILE_PATH="$1"
    FROM_HOOK=false
else
    FILE_PATH=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)
    FROM_HOOK=true
fi
[ -z "$FILE_PATH" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR" 2>/dev/null || exit 0
FILE_PATH="${FILE_PATH#"$PROJECT_DIR"/}"
FILE_PATH="${FILE_PATH#./}"

# 이 프로젝트의 소스 디렉터리. 각각이 모듈이고 CLAUDE.md를 하나씩 가진다.
# docs, blog, results, reference, source-doc은 소스가 아니라서 넣지 않는다.
SOURCE_ROOTS="app bench infra jobs k8s tests"

MESSAGES=()

for ROOT in $SOURCE_ROOTS; do
    if [[ "$FILE_PATH" == ${ROOT}/* ]]; then
        DIR=$(dirname "$FILE_PATH")
        FOUND_CLAUDE=false
        CHECK_DIR="$DIR"
        while [ "$CHECK_DIR" != "." ] && [ -n "$CHECK_DIR" ]; do
            if [ -f "$CHECK_DIR/CLAUDE.md" ]; then
                FOUND_CLAUDE=true
                break
            fi
            [ "$CHECK_DIR" = "$ROOT" ] && break
            CHECK_DIR=$(dirname "$CHECK_DIR")
        done
        if ! $FOUND_CLAUDE; then
            MESSAGES+=("[doc-sync] $ROOT/CLAUDE.md가 없습니다. 모듈 문서를 만듭니다.")
        fi
        break
    fi
done

# 어떤 파일을 고쳤는지에 따라 함께 볼 문서. 규칙의 원본은 AGENT.md다.
case "$FILE_PATH" in
    */CLAUDE.md) ;;                 # 모듈 문서 자체를 고친 경우는 알리지 않는다
    app/bff/test_*.py) ;;
    app/bff/*.py)
        MESSAGES+=("[doc-sync] BFF 코드가 바뀌었습니다. 경로, 요청 헤더, 응답 헤더가 달라졌으면 docs/07-bff.md와 docs/api-reference.md를 고칩니다. 웹 검색이면 docs/10-web-search.md도 봅니다.")
        ;;
    app/web/src/*)
        MESSAGES+=("[doc-sync] 화면 코드가 바뀌었습니다. 새 문구는 tr(한국어, 영어) 쌍으로 넣습니다(npm test가 검사). 보기나 헤더가 달라졌으면 docs/07-bff.md를 고칩니다.")
        ;;
    k8s/*)
        MESSAGES+=("[doc-sync] 매니페스트가 바뀌었습니다. 적용 전에 kubectl diff를 보여 주고 승인을 받습니다(AGENT.md 작업 규칙). diff에 내가 쓰지 않은 줄이 있으면 무엇이 더하는지 먼저 확인합니다. 구성이 달라졌으면 AGENT.md의 확정된 결정과 해당 단계 문서(docs/03~07), docs/architecture.md를 고칩니다.")
        ;;
    infra/terraform/*.tf|infra/cdk-vpc/lib/*|infra/cdk-vpc/bin/*)
        MESSAGES+=("[doc-sync] 인프라 코드가 바뀌었습니다. 적용 전에 terraform plan(또는 cdk diff)을 보여 주고 승인을 받습니다(AGENT.md 작업 규칙). 리소스가 달라졌으면 docs/architecture.md의 Infrastructure 표와 docs/reference/iac.md를 고칩니다.")
        ;;
    bench/*)
        MESSAGES+=("[doc-sync] 측정 스크립트가 바뀌었습니다. 결과는 results/<날짜>-<항목>/에 원시 자료로 남기고, 커밋 전에 scripts/mask-identifiers.py로 환경 식별 값을 가립니다. 측정한 값만 docs/08-results.md에 적습니다.")
        ;;
    jobs/*)
        MESSAGES+=("[doc-sync] 적재 Job이 바뀌었습니다. S3 경로나 모델 목록이 달라졌으면 AGENT.md의 S3 구조와 docs/03-vllm.md를 고칩니다.")
        ;;
    docs/infographic/*.py)
        MESSAGES+=("[doc-sync] 인포그래픽 소스가 바뀌었습니다. docs/infographic/build.sh로 그림을 다시 만들고, 웹 화면이 쓰는 그림이면 app/web/build.sh도 다시 실행합니다.")
        ;;
esac

# 아키텍처나 확정된 결정을 고쳤는데 ADR이 하나도 없으면 알린다.
if [[ "$FILE_PATH" == docs/architecture.md || "$FILE_PATH" == AGENT.md ]]; then
    ADR_COUNT=$(find docs/decisions -name 'ADR-*.md' 2>/dev/null | wc -l)
    if [ "$ADR_COUNT" -eq 0 ]; then
        MESSAGES+=("[doc-sync] ADR이 없습니다. 대안을 견줘 내린 결정이면 /add-adr로 docs/decisions/에 남깁니다.")
    fi
fi

[ "${#MESSAGES[@]}" -eq 0 ] && exit 0

if $FROM_HOOK; then
    # additionalContext는 끝난 도구 호출을 막지 않고 Claude에게 전달된다. stdout의 보통 글은 전달되지 않는다.
    printf '%s\n' "${MESSAGES[@]}" | jq -Rs '{hookSpecificOutput: {hookEventName: "PostToolUse", additionalContext: .}}'
else
    printf '%s\n' "${MESSAGES[@]}"
fi
exit 0
