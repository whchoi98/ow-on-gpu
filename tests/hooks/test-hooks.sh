#!/bin/bash
# .claude/hooks/*.sh 의 시험 (tests/run-all.sh가 source로 불러 실행한다)
# 실행기의 변수(TOTAL, PASSED, FAILED, SKIPPED, FAILURES)와 겹치지 않게 이 파일의 변수는 HK_로 시작한다.

# --- 있는지, 실행 권한, 문법 ---
for HK_NAME in check-doc-sync secret-scan session-context notify; do
    assert_file_exists "$HK_NAME.sh 있음" ".claude/hooks/$HK_NAME.sh"
    assert_file_executable "$HK_NAME.sh 실행 권한" ".claude/hooks/$HK_NAME.sh"
    assert_bash_syntax "$HK_NAME.sh bash 문법" ".claude/hooks/$HK_NAME.sh"
done

# --- settings.json의 훅 등록 ---
assert_file_exists "settings.json 있음" ".claude/settings.json"
assert_json_valid "settings.json은 JSON" ".claude/settings.json"

HK_SETTINGS=$(cat .claude/settings.json)
assert_contains "SessionStart 훅 등록" "$HK_SETTINGS" "session-context.sh"
assert_contains "PreToolUse 훅 등록" "$HK_SETTINGS" "secret-scan.sh"
assert_contains "PostToolUse 훅 등록" "$HK_SETTINGS" "check-doc-sync.sh"
assert_contains "Notification 훅 등록" "$HK_SETTINGS" "notify.sh"
assert_eq "PostToolUse matcher는 Write|Edit" "Write|Edit" "$(jq -r '.hooks.PostToolUse[0].matcher' .claude/settings.json)"

# 훅은 stdin의 JSON을 읽는다. 템플릿의 가짜 변수($TOOL_INPUT_PATH 등)가 돌아오면 안 된다
assert_not_contains "settings: 가짜 환경 변수 인자 없음" "$HK_SETTINGS" "TOOL_INPUT_PATH"

# PreToolUse는 exit 2로만 막는다. 명령이 종료 코드를 삼키면 막지 못한다
HK_PRE_CMD=$(jq -r '.hooks.PreToolUse[0].hooks[0].command' .claude/settings.json)
assert_not_contains "PreToolUse 명령이 종료 코드를 유지" "$HK_PRE_CMD" "|| true"
assert_eq "PreToolUse matcher는 Bash" "Bash" "$(jq -r '.hooks.PreToolUse[0].matcher' .claude/settings.json)"

HK_DENY=$(jq -r '.permissions.deny[]' .claude/settings.json)
assert_contains "deny: rm -rf" "$HK_DENY" "Bash(rm -rf:*)"
assert_contains "deny: 강제 push" "$HK_DENY" "Bash(git push --force:*)"
assert_contains "deny: .env 읽기" "$HK_DENY" "Read(./.env)"
assert_contains "deny: Terraform 상태 읽기" "$HK_DENY" "Read(./infra/terraform/terraform.tfstate)"

# --- check-doc-sync의 동작 ---
HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "" 2>&1 || true)
assert_eq "check-doc-sync: 빈 경로는 출력 없음" "" "$HK_OUT"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "README.md" 2>&1 || true)
assert_eq "check-doc-sync: 소스가 아닌 파일은 조용함" "" "$HK_OUT"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "app/bff/bff.py" 2>&1 || true)
assert_contains "check-doc-sync: BFF 코드는 API 문서를 알림" "$HK_OUT" "docs/api-reference.md"
assert_not_contains "check-doc-sync: app/CLAUDE.md를 찾음" "$HK_OUT" "CLAUDE.md가 없습니다"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "app/bff/test_bff.py" 2>&1 || true)
assert_eq "check-doc-sync: BFF 시험 파일은 조용함" "" "$HK_OUT"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "app/web/src/Chat.jsx" 2>&1 || true)
assert_contains "check-doc-sync: 화면 코드는 tr() 쌍을 알림" "$HK_OUT" "tr(한국어, 영어)"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "k8s/bff/bff.yaml" 2>&1 || true)
assert_contains "check-doc-sync: 매니페스트는 kubectl diff 승인을 알림" "$HK_OUT" "kubectl diff"
assert_contains "check-doc-sync: 매니페스트는 쓰지 않은 줄 확인을 알림" "$HK_OUT" "내가 쓰지 않은 줄"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "infra/terraform/app.tf" 2>&1 || true)
assert_contains "check-doc-sync: Terraform은 plan 승인을 알림" "$HK_OUT" "terraform plan"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "bench/ttft/segments.py" 2>&1 || true)
assert_contains "check-doc-sync: 측정 스크립트는 원시 자료 위치를 알림" "$HK_OUT" "results/"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "docs/infographic/flow.py" 2>&1 || true)
assert_contains "check-doc-sync: 인포그래픽 소스는 다시 빌드를 알림" "$HK_OUT" "docs/infographic/build.sh"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "k8s/CLAUDE.md" 2>&1 || true)
assert_eq "check-doc-sync: 모듈 문서 자체를 고치면 조용함" "" "$HK_OUT"

HK_OUT=$(bash .claude/hooks/check-doc-sync.sh "tests/hooks/test-hooks.sh" 2>&1 || true)
assert_not_contains "check-doc-sync: tests/CLAUDE.md를 찾음" "$HK_OUT" "CLAUDE.md가 없습니다"

# 훅 방식: stdin의 JSON을 읽고 PostToolUse JSON을 낸다. 보통 글로 내면 Claude에게 전달되지 않는다
HK_OUT=$(echo "{\"tool_input\":{\"file_path\":\"$PROJECT_ROOT/k8s/gemma/deployment.yaml\"}}" \
    | bash .claude/hooks/check-doc-sync.sh 2>&1 || true)
assert_eq "check-doc-sync: 훅 방식은 PostToolUse JSON을 냄" "PostToolUse" \
    "$(echo "$HK_OUT" | jq -r '.hookSpecificOutput.hookEventName // empty' 2>/dev/null || true)"
assert_contains "check-doc-sync: 훅 방식의 내용에 알림이 있음" \
    "$(echo "$HK_OUT" | jq -r '.hookSpecificOutput.additionalContext // empty' 2>/dev/null || true)" "kubectl diff"

# 모듈 문서와 ADR 알림은 저장소 상태에 따라 달라지므로 임시 디렉터리에서 본다
HK_SYNC="$TEST_TMP/sync-project"
mkdir -p "$HK_SYNC/k8s/demo" "$HK_SYNC/docs/decisions"
echo "kind: Deployment" > "$HK_SYNC/k8s/demo/a.yaml"
HK_OUT=$(CLAUDE_PROJECT_DIR="$HK_SYNC" bash .claude/hooks/check-doc-sync.sh "k8s/demo/a.yaml" 2>&1 || true)
assert_contains "check-doc-sync: 모듈 문서가 없으면 알림" "$HK_OUT" "k8s/CLAUDE.md가 없습니다"
echo "# k8s" > "$HK_SYNC/k8s/CLAUDE.md"
HK_OUT=$(CLAUDE_PROJECT_DIR="$HK_SYNC" bash .claude/hooks/check-doc-sync.sh "k8s/demo/a.yaml" 2>&1 || true)
assert_not_contains "check-doc-sync: 모듈 루트의 CLAUDE.md를 찾음" "$HK_OUT" "CLAUDE.md가 없습니다"

HK_OUT=$(CLAUDE_PROJECT_DIR="$HK_SYNC" bash .claude/hooks/check-doc-sync.sh "docs/architecture.md" 2>&1 || true)
assert_contains "check-doc-sync: ADR이 없으면 아키텍처 변경에서 알림" "$HK_OUT" "ADR이 없습니다"
echo "# ADR" > "$HK_SYNC/docs/decisions/ADR-001-x.md"
HK_OUT=$(CLAUDE_PROJECT_DIR="$HK_SYNC" bash .claude/hooks/check-doc-sync.sh "docs/architecture.md" 2>&1 || true)
assert_not_contains "check-doc-sync: ADR이 있으면 알리지 않음" "$HK_OUT" "ADR이 없습니다"
HK_OUT=$(CLAUDE_PROJECT_DIR="$HK_SYNC" bash .claude/hooks/check-doc-sync.sh "k8s/demo/a.yaml" 2>&1 || true)
assert_not_contains "check-doc-sync: 매니페스트 변경에는 ADR을 알리지 않음" "$HK_OUT" "ADR이 없습니다"

# --- secret-scan의 동작 (PreToolUse 방식, 따로 만든 git 저장소) ---
HK_OUT=$(echo '{"tool_input":{"command":"ls -la"}}' | bash .claude/hooks/secret-scan.sh 2>&1; echo "exit=$?")
assert_eq "secret-scan: 커밋이 아닌 명령은 조용히 통과" "exit=0" "$HK_OUT"

HK_SCAN="$TEST_TMP/scan-repo"
mkdir -p "$HK_SCAN"
git -C "$HK_SCAN" init -q
echo '# 안내' > "$HK_SCAN/clean.md"
git -C "$HK_SCAN" add clean.md
HK_STATUS=$(echo '{"tool_input":{"command":"git commit -m test"}}' \
    | CLAUDE_PROJECT_DIR="$HK_SCAN" bash .claude/hooks/secret-scan.sh >/dev/null 2>&1; echo $?)
assert_eq "secret-scan: 깨끗한 파일은 커밋 허용" "0" "$HK_STATUS"

# 완전한 키 문자열을 저장소에 두지 않으려고 실행할 때 합친다
HK_KEY_PREFIX="AKIA"
HK_KEY_BODY="IOSFODNN7EXAMPLE"
echo "키: ${HK_KEY_PREFIX}${HK_KEY_BODY}" > "$HK_SCAN/leak.md"
HK_STATUS=$(echo '{"tool_input":{"command":"git add -A && git commit -m test"}}' \
    | CLAUDE_PROJECT_DIR="$HK_SCAN" bash .claude/hooks/secret-scan.sh >/dev/null 2>&1; echo $?)
assert_eq "secret-scan: 스테이징 전의 비밀 값도 'git add && commit'에서 exit 2로 막음" "2" "$HK_STATUS"

git -C "$HK_SCAN" add leak.md
HK_STATUS=$(bash -c "cd '$HK_SCAN' && bash '$PROJECT_ROOT/.claude/hooks/secret-scan.sh' --staged" >/dev/null 2>&1; echo $?)
assert_eq "secret-scan: --staged(git pre-commit)는 exit 1로 막음" "1" "$HK_STATUS"

# 내용이 비어 있어도 Terraform 상태 파일은 막는다
HK_STATE="$TEST_TMP/state-repo"
mkdir -p "$HK_STATE/infra/terraform"
git -C "$HK_STATE" init -q
echo '{}' > "$HK_STATE/infra/terraform/terraform.tfstate"
git -C "$HK_STATE" add -f infra/terraform/terraform.tfstate
HK_STATUS=$(echo '{"tool_input":{"command":"git commit -m state"}}' \
    | CLAUDE_PROJECT_DIR="$HK_STATE" bash .claude/hooks/secret-scan.sh >/dev/null 2>&1; echo $?)
assert_eq "secret-scan: 스테이징한 Terraform 상태 파일을 exit 2로 막음" "2" "$HK_STATUS"

# --- session-context ---
HK_OUT=$(bash .claude/hooks/session-context.sh 2>&1 || true)
assert_contains "session-context: 머리글" "$HK_OUT" "프로젝트 맥락"
assert_contains "session-context: 규칙의 원본을 알림" "$HK_OUT" "AGENT.md"
assert_contains "session-context: 승인 규칙을 알림" "$HK_OUT" "승인"
assert_contains "session-context: 문서 수를 알림" "$HK_OUT" "CLAUDE.md "
if [ -f infra/terraform/bff.auto.tfvars ]; then
    HK_TAG=$(sed -n 's/^bff_image_tag *= *"\(.*\)"/\1/p' infra/terraform/bff.auto.tfvars | head -1)
    assert_contains "session-context: 마지막으로 빌드한 BFF 태그" "$HK_OUT" "$HK_TAG"
else
    skip "session-context: 마지막으로 빌드한 BFF 태그" "bff.auto.tfvars가 없음(커밋하지 않는 파일)"
fi
# 맥락에 식별 값이 섞이면 안 된다
if printf '%s\n' "$HK_OUT" | grep -qE '[0-9]{12}|cloudfront\.net'; then
    fail "session-context: 계정 ID나 사이트 주소를 내지 않음" "출력에 식별 값이 있음"
else
    pass "session-context: 계정 ID나 사이트 주소를 내지 않음"
fi

# --- AI 공동 저자 줄 제거 ---
assert_eq "settings: 커밋 attribution 끔" "" "$(jq -r '.attribution.commit' .claude/settings.json)"
assert_eq "settings: PR attribution 끔" "" "$(jq -r '.attribution.pr' .claude/settings.json)"

HK_MSG="$TEST_TMP/msg-repo"
mkdir -p "$HK_MSG/scripts"
git -C "$HK_MSG" init -q
cp scripts/install-hooks.sh "$HK_MSG/scripts/"
bash "$HK_MSG/scripts/install-hooks.sh" >/dev/null
assert_file_executable "install-hooks: pre-commit 설치" "$HK_MSG/.git/hooks/pre-commit"
assert_file_executable "install-hooks: commit-msg 설치" "$HK_MSG/.git/hooks/commit-msg"
printf 'feat: sample\n\nBody line.\n\nCo-Authored-By: Claude <noreply@anthropic.com>\nco-authored-by: Bot <b@x>\n  CO-AUTHORED-BY: Other <o@x>\n\n' \
    > "$HK_MSG/msg.txt"
bash "$HK_MSG/.git/hooks/commit-msg" "$HK_MSG/msg.txt"
HK_MSG_OUT=$(cat "$HK_MSG/msg.txt")
assert_not_contains "commit-msg: Co-Authored-By를 대소문자 구분 없이 지움" "$(echo "$HK_MSG_OUT" | tr '[:upper:]' '[:lower:]')" "co-authored-by"
assert_contains "commit-msg: 제목과 본문은 남김" "$HK_MSG_OUT" "Body line."
assert_eq "commit-msg: 끝에 빈 줄 없음" "Body line." "$(tail -n 1 "$HK_MSG/msg.txt")"

# git 저장소가 아니면 설치 스크립트가 실패로 알린다
HK_NOGIT="$TEST_TMP/no-git"
mkdir -p "$HK_NOGIT/scripts"
cp scripts/install-hooks.sh "$HK_NOGIT/scripts/"
HK_STATUS=$(GIT_CEILING_DIRECTORIES="$TEST_TMP" bash "$HK_NOGIT/scripts/install-hooks.sh" >/dev/null 2>&1; echo $?)
assert_eq "install-hooks: git 저장소가 아니면 exit 1" "1" "$HK_STATUS"

# --- notify ---
HK_OUT=$(CLAUDE_NOTIFY_WEBHOOK="" bash .claude/hooks/notify.sh "test" "msg" 2>&1 || true)
assert_eq "notify: 웹훅 주소가 없으면 출력 없음" "" "$HK_OUT"
