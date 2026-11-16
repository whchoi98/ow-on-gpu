#!/bin/bash
# git 훅을 설치한다.
# 사용법: bash scripts/install-hooks.sh

set -e

cd "$(dirname "$0")/.."

HOOKS_DIR=".git/hooks"

if [ ! -d "$HOOKS_DIR" ]; then
    echo "ERROR: .git/hooks 디렉터리가 없습니다. git 저장소인지 확인합니다."
    exit 1
fi

# commit-msg 훅: Co-Authored-By 줄을 지운다
cat > "$HOOKS_DIR/commit-msg" << 'HOOK'
#!/bin/bash
# 커밋 메시지에서 Co-Authored-By 줄을 대소문자 구분 없이 지운다.
# Claude 같은 AI 도우미가 기여자로 올라가지 않게 한다.
# grep과 awk만 써서 macOS의 BSD 도구에서도 동작한다.
MSG="$1"
TMP="$(mktemp)" || exit 1
grep -viE '^[[:space:]]*co-authored-by[[:space:]]*:' "$MSG" > "$TMP" || true
# 지운 뒤에 남은 끝쪽 빈 줄을 없앤다
awk '{ line[NR] = $0 } END { n = NR; while (n > 0 && line[n] ~ /^[[:space:]]*$/) n--; for (i = 1; i <= n; i++) print line[i] }' \
    "$TMP" > "$MSG"
rm -f "$TMP"
HOOK
chmod +x "$HOOKS_DIR/commit-msg"
echo "commit-msg 훅을 설치했습니다 (AI 공동 저자 줄 제거)"

# pre-commit 훅: 스테이징한 파일의 비밀 값 검사. Claude Code 없이 커밋할 때도 동작한다.
cat > "$HOOKS_DIR/pre-commit" << 'HOOK'
#!/bin/bash
# 스테이징한 파일에 비밀 값으로 보이는 문자열이 있으면 커밋을 막는다.
exec bash "$(git rev-parse --show-toplevel)/.claude/hooks/secret-scan.sh" --staged
HOOK
chmod +x "$HOOKS_DIR/pre-commit"
echo "pre-commit 훅을 설치했습니다 (비밀 값 검사)"

echo "=== git 훅 설치 완료 ==="
