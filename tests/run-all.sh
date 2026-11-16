#!/bin/bash
# 하네스 시험의 실행기.
# 사용법: bash tests/run-all.sh [시험 파일 이름의 일부]
# 예:     bash tests/run-all.sh            # 전부
#         bash tests/run-all.sh hooks       # 훅 시험만
#         bash tests/run-all.sh structure   # 구조 시험만
#
# 시험 파일은 source로 불러 같은 셸에서 돌린다. -e는 일부러 쓰지 않는다. 아무것도 찾지 못한 grep이
# 실행을 끊으면 안 되기 때문이다. 모든 확인은 pass, fail, skip으로 보고한다.

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0
FAILURES=()

export TEST_RUNNER_ACTIVE=1

pass() {
    TOTAL=$((TOTAL + 1))
    PASSED=$((PASSED + 1))
    echo -e "  ${GREEN}✓${NC} $1"
}

fail() {
    TOTAL=$((TOTAL + 1))
    FAILED=$((FAILED + 1))
    FAILURES+=("$1: $2")
    echo -e "  ${RED}✗${NC} $1"
    echo -e "    ${RED}이유: $2${NC}"
}

skip() {
    TOTAL=$((TOTAL + 1))
    SKIPPED=$((SKIPPED + 1))
    echo -e "  ${YELLOW}○${NC} $1 (건너뜀: $2)"
}

assert_eq() {
    local desc="$1" expected="$2" actual="$3"
    [ "$expected" = "$actual" ] && pass "$desc" || fail "$desc" "기대 '$expected', 실제 '$actual'"
}

assert_contains() {
    local desc="$1" haystack="$2" needle="$3"
    printf '%s\n' "$haystack" | grep -qF -- "$needle" && pass "$desc" || fail "$desc" "출력에 '$needle'이 없음"
}

assert_not_contains() {
    local desc="$1" haystack="$2" needle="$3"
    printf '%s\n' "$haystack" | grep -qF -- "$needle" && fail "$desc" "출력에 '$needle'이 있으면 안 됨" || pass "$desc"
}

assert_file_exists() {
    local desc="$1" filepath="$2"
    [ -f "$filepath" ] && pass "$desc" || fail "$desc" "파일 없음: $filepath"
}

assert_file_executable() {
    local desc="$1" filepath="$2"
    [ -x "$filepath" ] && pass "$desc" || fail "$desc" "실행 권한 없음: $filepath"
}

assert_json_valid() {
    local desc="$1" filepath="$2"
    python3 -m json.tool "$filepath" > /dev/null 2>&1 && pass "$desc" || fail "$desc" "JSON이 아님: $filepath"
}

assert_bash_syntax() {
    local desc="$1" filepath="$2"
    bash -n "$filepath" 2>/dev/null && pass "$desc" || fail "$desc" "bash 문법 오류: $filepath"
}

FILTER="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
export CLAUDE_PROJECT_DIR="$PROJECT_ROOT"

# 임시 파일과 임시 git 저장소를 둘 자리
TEST_TMP="$(mktemp -d "${TMPDIR:-/tmp}/harness-tests.XXXXXX")"
trap 'case "$TEST_TMP" in */harness-tests.*) rm -rf -- "$TEST_TMP" ;; esac' EXIT

echo -e "${CYAN}=== 하네스 시험 ===${NC}"
echo ""

TEST_FILES=$(find "$SCRIPT_DIR" -name "test-*.sh" | sort)

for test_file in $TEST_FILES; do
    test_name=$(basename "$test_file" .sh)
    if [ -n "$FILTER" ] && ! echo "$test_name" | grep -q -- "$FILTER"; then
        continue
    fi
    echo -e "${CYAN}▸ $test_name${NC}"
    # shellcheck source=/dev/null
    source "$test_file"
    echo ""
done

echo -e "${CYAN}=== 결과 ===${NC}"
echo -e "  전체:   $TOTAL"
echo -e "  ${GREEN}통과:   $PASSED${NC}"
[ "$FAILED" -gt 0 ] && echo -e "  ${RED}실패:   $FAILED${NC}" || echo -e "  실패:   0"
[ "$SKIPPED" -gt 0 ] && echo -e "  ${YELLOW}건너뜀: $SKIPPED${NC}" || echo -e "  건너뜀: 0"

if [ "${#FAILURES[@]}" -gt 0 ]; then
    echo ""
    echo -e "${RED}=== 실패한 시험 ===${NC}"
    for f in "${FAILURES[@]}"; do
        echo -e "  ${RED}✗${NC} $f"
    done
    exit 1
fi

if [ "$TOTAL" -eq 0 ] || [ "$TOTAL" -ne $((PASSED + FAILED + SKIPPED)) ]; then
    echo -e "${RED}카운터가 맞지 않거나 실행한 시험이 없습니다 (고른 이름: '$FILTER'). 시험 파일이 실행기의 변수를 덮어썼을 수 있습니다.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}모든 시험이 통과했습니다.${NC}"
