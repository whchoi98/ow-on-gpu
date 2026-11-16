#!/bin/bash
# 프로젝트 구조와 문서의 시험 (tests/run-all.sh가 source로 불러 실행한다)
# 이 파일의 변수와 함수는 ST_, st_로 시작한다.

# 두 언어 문서에서 한 언어 구역만 꺼낸다. $1 파일, $2 english|korean
st_section() {
    if [ "$2" = english ]; then
        sed -n '/<a id="english"><\/a>/,/<a id="korean"><\/a>/p' "$1" | sed '$d'
    else
        sed -n '/<a id="korean"><\/a>/,$p' "$1"
    fi
}
# 코드 블록 안의 줄을 뺀다(코드 주석의 #을 제목으로 세지 않게)
st_outside_code() { awk '/^```/{inside=!inside; next} !inside'; }
st_count() { grep -cE -- "$1" || true; }
ST_HANGUL='[\x{AC00}-\x{D7A3}]'

# --- 루트의 파일 ---
for ST_FILE in CLAUDE.md AGENT.md README.md CHANGELOG.md .gitignore .env.example .editorconfig .mcp.json; do
    assert_file_exists "루트: $ST_FILE" "$ST_FILE"
done
assert_json_valid ".mcp.json은 JSON" ".mcp.json"
assert_eq ".mcp.json에 mcpServers 키" "object" "$(jq -r '.mcpServers | type' .mcp.json 2>/dev/null || true)"

# --- CLAUDE.md: AGENT.md를 불러오고 정해진 구역을 가진다 ---
grep -qx '@AGENT.md' CLAUDE.md && pass "CLAUDE.md: @AGENT.md 줄이 있음" \
    || fail "CLAUDE.md: @AGENT.md 줄이 있음" "이 줄이 없으면 규칙이 세션에 실리지 않음"
for ST_HEAD in "Overview" "Tech Stack" "Project Structure" "Conventions" "Key Commands" "Auto-Sync Rules" "Implementation References"; do
    grep -qx "## $ST_HEAD" CLAUDE.md && pass "CLAUDE.md: 구역 '$ST_HEAD'" || fail "CLAUDE.md: 구역 '$ST_HEAD'" "제목 없음"
done
for ST_HEAD in "확정된 결정" "작업 규칙" "디렉터리 구조" "알려진 함정"; do
    grep -qx "## $ST_HEAD" AGENT.md && pass "AGENT.md: 구역 '$ST_HEAD'" || fail "AGENT.md: 구역 '$ST_HEAD'" "CLAUDE.md가 가리키는 구역이 없음"
done

# --- 모듈 문서: 훅의 SOURCE_ROOTS와 실제 디렉터리가 맞는지 ---
ST_ROOTS=$(sed -n 's/^SOURCE_ROOTS="\(.*\)"/\1/p' .claude/hooks/check-doc-sync.sh)
[ -n "$ST_ROOTS" ] && pass "check-doc-sync: SOURCE_ROOTS를 읽음 ($ST_ROOTS)" || fail "check-doc-sync: SOURCE_ROOTS를 읽음" "값 없음"
for ST_ROOT in $ST_ROOTS; do
    assert_file_exists "모듈 문서: $ST_ROOT/CLAUDE.md" "$ST_ROOT/CLAUDE.md"
    for ST_HEAD in "Role" "Key Files" "Rules"; do
        grep -qx "## $ST_HEAD" "$ST_ROOT/CLAUDE.md" 2>/dev/null && pass "$ST_ROOT/CLAUDE.md: 구역 '$ST_HEAD'" \
            || fail "$ST_ROOT/CLAUDE.md: 구역 '$ST_HEAD'" "제목 없음"
    done
done
# 새 최상위 디렉터리가 생기면 소스인지 아닌지 정해야 한다
ST_NON_SOURCE="docs blog results reference source-doc scripts tools"
ST_UNKNOWN=""
for ST_DIR in */; do
    ST_DIR="${ST_DIR%/}"
    case " $ST_ROOTS $ST_NON_SOURCE " in *" $ST_DIR "*) ;; *) ST_UNKNOWN="$ST_UNKNOWN $ST_DIR" ;; esac
done
assert_eq "최상위 디렉터리가 모두 소스 또는 비소스 목록에 있음" "" "$ST_UNKNOWN"

# --- 스킬: frontmatter와 이름 ---
for ST_DIR in .claude/skills/*/; do
    ST_SKILL=$(basename "$ST_DIR")
    assert_file_exists "스킬 $ST_SKILL: SKILL.md" "$ST_DIR/SKILL.md"
    head -1 "$ST_DIR/SKILL.md" | grep -qx -- '---' && pass "스킬 $ST_SKILL: frontmatter 시작" \
        || fail "스킬 $ST_SKILL: frontmatter 시작" "첫 줄이 ---가 아님"
    assert_eq "스킬 $ST_SKILL: name이 디렉터리 이름과 같음" "$ST_SKILL" \
        "$(sed -n '2,/^---$/s/^name: //p' "$ST_DIR/SKILL.md" | head -1)"
    ST_DESC=$(sed -n '2,/^---$/s/^description: //p' "$ST_DIR/SKILL.md" | head -1)
    [ "${#ST_DESC}" -ge 30 ] && pass "스킬 $ST_SKILL: description 있음 (${#ST_DESC}자)" \
        || fail "스킬 $ST_SKILL: description 있음" "너무 짧거나 없음"
done
[ -d .claude/skills/code-review ] && fail "스킬: 내장 /code-review를 가리지 않음" ".claude/skills/code-review가 있음" \
    || pass "스킬: 내장 /code-review를 가리지 않음"

# --- 에이전트: .md와 frontmatter (.yml은 불러오지 않는다) ---
assert_eq "에이전트: .yml 파일 없음" "0" "$(find .claude/agents -name '*.yml' -o -name '*.yaml' | wc -l | tr -d ' ')"
for ST_FILE in .claude/agents/*.md; do
    ST_AGENT=$(basename "$ST_FILE" .md)
    assert_eq "에이전트 $ST_AGENT: name이 파일 이름과 같음" "$ST_AGENT" "$(sed -n '2,/^---$/s/^name: //p' "$ST_FILE" | head -1)"
    for ST_KEY in description tools; do
        sed -n '2,/^---$/p' "$ST_FILE" | grep -q "^$ST_KEY: " && pass "에이전트 $ST_AGENT: $ST_KEY" \
            || fail "에이전트 $ST_AGENT: $ST_KEY" "frontmatter에 없음"
    done
done
assert_file_exists "에이전트: code-reviewer" ".claude/agents/code-reviewer.md"
assert_file_exists "에이전트: security-auditor" ".claude/agents/security-auditor.md"

# --- 명령 ---
for ST_CMD in review test-all deploy; do
    assert_file_exists "명령 /$ST_CMD" ".claude/commands/$ST_CMD.md"
    sed -n '2,/^---$/p' ".claude/commands/$ST_CMD.md" 2>/dev/null | grep -q "^description: " && pass "명령 /$ST_CMD: description" \
        || fail "명령 /$ST_CMD: description" "frontmatter에 없음"
done
# 배포 명령은 적용 명령을 미리 허용하지 않는다. 승인 절차가 사라지기 때문이다
ST_ALLOWED=$(sed -n '2,/^---$/s/^allowed-tools: //p' .claude/commands/deploy.md)
for ST_WORD in "terraform" "kubectl" "install.sh" "build.sh"; do
    assert_not_contains "명령 /deploy: $ST_WORD 를 미리 허용하지 않음" "$ST_ALLOWED" "$ST_WORD"
done

# --- 문서가 있는지 ---
for ST_FILE in docs/architecture.md docs/onboarding.md docs/api-reference.md docs/decisions/.template.md \
               docs/runbooks/.template.md docs/reference/INDEX.md; do
    assert_file_exists "문서: $ST_FILE" "$ST_FILE"
done

# --- 두 언어 문서: 두 구역의 구조가 같다 ---
for ST_FILE in README.md CHANGELOG.md docs/architecture.md docs/decisions/.template.md docs/runbooks/.template.md docs/reference/*.md; do
    ST_EN_LINE=$(grep -n -m1 '<a id="english"></a>' "$ST_FILE" | cut -d: -f1)
    ST_KO_LINE=$(grep -n -m1 '<a id="korean"></a>' "$ST_FILE" | cut -d: -f1)
    if [ -n "$ST_EN_LINE" ] && [ -n "$ST_KO_LINE" ] && [ "$ST_EN_LINE" -lt "$ST_KO_LINE" ]; then
        pass "$ST_FILE: english, korean 표식이 차례대로 있음"
    else
        fail "$ST_FILE: english, korean 표식이 차례대로 있음" "표식이 없거나 순서가 다름"
        continue
    fi
    ST_EN=$(st_section "$ST_FILE" english)
    ST_KO=$(st_section "$ST_FILE" korean)
    assert_eq "$ST_FILE: 두 구역의 제목 수" \
        "$(printf '%s\n' "$ST_EN" | st_outside_code | st_count '^#{1,4} ')" "$(printf '%s\n' "$ST_KO" | st_outside_code | st_count '^#{1,4} ')"
    assert_eq "$ST_FILE: 두 구역의 코드 블록 수" \
        "$(printf '%s\n' "$ST_EN" | st_count '^```')" "$(printf '%s\n' "$ST_KO" | st_count '^```')"
    assert_eq "$ST_FILE: 두 구역의 표 줄 수" \
        "$(printf '%s\n' "$ST_EN" | st_count '^\|')" "$(printf '%s\n' "$ST_KO" | st_count '^\|')"
    assert_eq "$ST_FILE: 두 구역의 목록 줄 수" \
        "$(printf '%s\n' "$ST_EN" | st_outside_code | st_count '^- ')" "$(printf '%s\n' "$ST_KO" | st_outside_code | st_count '^- ')"
    if printf '%s\n' "$ST_EN" | grep -qP "$ST_HANGUL"; then
        fail "$ST_FILE: 영어 구역에 한글이 없음" "$(printf '%s\n' "$ST_EN" | grep -m1 -P "$ST_HANGUL" | cut -c1-60)"
    else
        pass "$ST_FILE: 영어 구역에 한글이 없음"
    fi
    printf '%s\n' "$ST_KO" | grep -qP "$ST_HANGUL" && pass "$ST_FILE: 한국어 구역에 한글이 있음" \
        || fail "$ST_FILE: 한국어 구역에 한글이 있음" "한글 없음"
done
# 그림은 두 구역에 같은 것이 들어간다
assert_eq "docs/architecture.md: 두 구역의 Mermaid 그림이 같음" \
    "$(st_section docs/architecture.md english | sed -n '/^```mermaid/,/^```$/p' | md5sum | cut -d' ' -f1)" \
    "$(st_section docs/architecture.md korean | sed -n '/^```mermaid/,/^```$/p' | md5sum | cut -d' ' -f1)"
[ "$(st_section docs/architecture.md english | st_count '^```mermaid')" -ge 2 ] && pass "docs/architecture.md: Mermaid 그림이 둘 이상" \
    || fail "docs/architecture.md: Mermaid 그림이 둘 이상" "전체 그림과 흐름 그림이 있어야 함"

# --- README: 필요한 구역이 차례대로 있다 ---
assert_eq "README: 영어 구역의 차례" \
    "Overview|Features|Prerequisites|Installation|Usage|Configuration|Project Structure|Testing|API Documentation|Contributing|License|Contact|" \
    "$(st_section README.md english | st_outside_code | sed -n 's/^## //p' | tr '\n' '|')"
assert_eq "README: 한국어 구역의 차례" \
    "개요|주요 기능|사전 요구 사항|설치 방법|사용법|환경 설정|프로젝트 구조|테스트|API 문서|기여 방법|라이선스|연락처|" \
    "$(st_section README.md korean | st_outside_code | sed -n 's/^## //p' | tr '\n' '|')"

# --- CHANGELOG: 두 구역의 버전 목록이 같고 분류 제목은 영어다 ---
ST_EN=$(st_section CHANGELOG.md english)
ST_KO=$(st_section CHANGELOG.md korean)
assert_contains "CHANGELOG: 영어 구역에 [Unreleased]" "$ST_EN" "## [Unreleased]"
assert_contains "CHANGELOG: 한국어 구역에 [Unreleased]" "$ST_KO" "## [Unreleased]"
assert_eq "CHANGELOG: 두 구역의 버전 목록이 같음" \
    "$(printf '%s\n' "$ST_EN" | grep -oP '^## \[\K[^]]+' | tr '\n' ' ')" "$(printf '%s\n' "$ST_KO" | grep -oP '^## \[\K[^]]+' | tr '\n' ' ')"
assert_eq "CHANGELOG: 한국어 구역의 분류 제목도 영어" "" \
    "$(printf '%s\n' "$ST_KO" | grep -E '^### ' | grep -vE '^### (Added|Changed|Deprecated|Removed|Fixed|Security)$' | tr '\n' ' ')"

# --- 참조 문서: 색인과 CLAUDE.md의 목록이 파일과 맞는지 ---
for ST_FILE in docs/reference/*.md; do
    ST_LAYER=$(basename "$ST_FILE" .md)
    [ "$ST_LAYER" = INDEX ] && continue
    grep -qF "($ST_LAYER.md)" docs/reference/INDEX.md && pass "INDEX.md: $ST_LAYER.md를 가리킴" \
        || fail "INDEX.md: $ST_LAYER.md를 가리킴" "색인에 없음"
    sed -n '/<!-- AUTO-MANAGED:references -->/,/<!-- \/AUTO-MANAGED -->/p' CLAUDE.md | grep -qF "(docs/reference/$ST_LAYER.md)" \
        && pass "CLAUDE.md: docs/reference/$ST_LAYER.md를 가리킴" || fail "CLAUDE.md: docs/reference/$ST_LAYER.md를 가리킴" "AUTO-MANAGED 구역에 없음"
done
ST_MISSING=""
while IFS= read -r ST_LINK; do
    [ -f "docs/reference/$ST_LINK" ] || ST_MISSING="$ST_MISSING $ST_LINK"
done < <(grep -oP '\]\(\K[a-z-]+\.md(?=\))' docs/reference/INDEX.md | sort -u)
assert_eq "INDEX.md: 가리키는 파일이 모두 있음" "" "$ST_MISSING"

# --- 문서가 적은 경로가 실제로 있는지 ---
# 백틱 안의 값 가운데 경로 모양(디렉터리 구분자가 있고 자리 표시가 없는 것)만 본다.
# 커밋하지 않는 파일과 자리 표시 이름은 뺀다.
st_paths() { grep -oP '`\K[^`]+(?=`)' "$1" | grep -P '^\.?[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)+/?$|^[A-Za-z0-9_-]+/$' \
    | grep -vE '\.kubeconfig$|bff\.auto\.tfvars$|cdk\.context\.json$|params\.yaml$|prometheus\.yml$|storage-s3\.yaml$|params\.env$|terraform\.tfvars$|node_modules|ADR-NNN|terraform\.tfstate|settings\.local\.json|^feat/|^fix/' | sort -u; }
for ST_FILE in CLAUDE.md docs/reference/*.md docs/onboarding.md docs/api-reference.md .claude/commands/*.md .claude/skills/*/SKILL.md .claude/agents/*.md; do
    ST_MISSING=""
    while IFS= read -r ST_PATH; do
        [ -e "$ST_PATH" ] || ST_MISSING="$ST_MISSING $ST_PATH"
    done < <(st_paths "$ST_FILE")
    assert_eq "$ST_FILE: 적은 경로가 모두 있음" "" "$ST_MISSING"
done
# 모듈 문서의 경로는 모듈 디렉터리 기준이거나 저장소 루트 기준이다
for ST_ROOT in $ST_ROOTS; do
    ST_MISSING=""
    while IFS= read -r ST_PATH; do
        [ -e "$ST_ROOT/$ST_PATH" ] || [ -e "$ST_PATH" ] || ST_MISSING="$ST_MISSING $ST_PATH"
    done < <(st_paths "$ST_ROOT/CLAUDE.md")
    assert_eq "$ST_ROOT/CLAUDE.md: 적은 경로가 모두 있음" "" "$ST_MISSING"
done
ST_MISSING=""
while IFS= read -r ST_PATH; do
    [ -e "$ST_PATH" ] || ST_MISSING="$ST_MISSING $ST_PATH"
done < <(grep -oP '^- \*\*\K[^*]+(?=\*\*)' docs/architecture.md | sort -u)
assert_eq "docs/architecture.md: 구성 요소의 경로가 모두 있음" "" "$ST_MISSING"

# --- 만든 문서에 식별 값이 없는지 ---
ST_LEAK=""
for ST_FILE in CLAUDE.md README.md CHANGELOG.md docs/architecture.md docs/onboarding.md docs/api-reference.md docs/reference/*.md \
               app/CLAUDE.md bench/CLAUDE.md infra/CLAUDE.md jobs/CLAUDE.md k8s/CLAUDE.md tests/CLAUDE.md \
               .claude/commands/*.md .claude/skills/*/SKILL.md .claude/agents/*.md .claude/hooks/*.sh scripts/*.sh scripts/*.py; do
    # 763104351884는 AWS가 공개한 Deep Learning Containers 레지스트리 계정이다(검사기의 허용 목록에 적혀 있다)
    sed 's/763104351884//g' "$ST_FILE" | grep -qE '(^|[^0-9])[0-9]{12}([^0-9]|$)|[a-z0-9]+\.cloudfront\.net|[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.(com|net)' && ST_LEAK="$ST_LEAK $ST_FILE"
done
assert_eq "만든 문서와 도구에 계정 ID, CloudFront 도메인, 이메일이 없음" "" "$ST_LEAK"

# --- .gitignore와 .env.example ---
ST_IGNORE=$(cat .gitignore)
for ST_RULE in ".env" "*.tfstate" ".kubeconfig" "node_modules/" ".claude/settings.local.json" ".terraform/"; do
    printf '%s\n' "$ST_IGNORE" | grep -qxF -- "$ST_RULE" && pass ".gitignore: $ST_RULE" || fail ".gitignore: $ST_RULE" "규칙 없음"
done
grep -qE '^USER_PASSWORD=' .env.example && fail ".env.example: 데모 계정 비밀번호 자리를 두지 않음" "USER_PASSWORD= 줄이 있음" \
    || pass ".env.example: 데모 계정 비밀번호 자리를 두지 않음"
assert_eq ".env.example: 값이 있는 변수는 비밀이 아닌 둘뿐" "AWS_REGION KUBECONFIG " \
    "$(grep -E '^[A-Z_]+=.+' .env.example | cut -d= -f1 | sort | tr '\n' ' ')"

# --- 환경별 값이 든 파일: 예시만 추적하고, 예시는 실제 파일을 가린 것과 같다 ---
for ST_FILE in k8s/base/params.yaml k8s/observability/prometheus.yml bench/coldstart/k8s/storage-s3.yaml \
               jobs/model-sync/params.env infra/terraform/terraform.tfvars; do
    assert_file_exists "예시 파일: $ST_FILE.example" "$ST_FILE.example"
    grep -qE '<(suffix|amp-workspace-id|ip)>' "$ST_FILE.example" 2>/dev/null && pass "$ST_FILE.example: 자리 표시가 있음" \
        || fail "$ST_FILE.example: 자리 표시가 있음" "자리 표시가 없음"
    printf '%s\n' "$ST_IGNORE" | grep -qxF -- "$ST_FILE" && pass ".gitignore: $ST_FILE" || fail ".gitignore: $ST_FILE" "규칙 없음"
    if git rev-parse --git-dir >/dev/null 2>&1; then
        git ls-files --error-unmatch "$ST_FILE" >/dev/null 2>&1 && fail "$ST_FILE 을 추적하지 않음" "추적 중" || pass "$ST_FILE 을 추적하지 않음"
    else
        skip "$ST_FILE 을 추적하지 않음" "git 저장소가 아님"
    fi
    if [ -f "$ST_FILE" ]; then
        assert_eq "$ST_FILE.example 이 실제 파일을 가린 것과 같음" "$(python3 scripts/mask-identifiers.py --stdout "$ST_FILE" | md5sum)" "$(md5sum < "$ST_FILE.example")"
    else
        skip "$ST_FILE.example 이 실제 파일을 가린 것과 같음" "실제 파일이 없음(새로 받은 저장소)"
    fi
done
assert_file_executable "scripts/mask-identifiers.py 실행 권한" "scripts/mask-identifiers.py"

# --- 시험 파일이 실행기의 변수를 덮어쓰지 않는지 ---
assert_eq "시험 파일이 실행기의 카운터를 대입하지 않음" "" \
    "$(grep -lE '^[[:space:]]*(TOTAL|PASSED|FAILED|SKIPPED|FAILURES|FILTER|PROJECT_ROOT|TEST_TMP)=' tests/*/test-*.sh | tr '\n' ' ')"
head -12 tests/run-all.sh | grep -q '^set -uo pipefail' && pass "run-all.sh: set -e를 쓰지 않음" \
    || fail "run-all.sh: set -e를 쓰지 않음" "-e가 있으면 아무것도 못 찾은 grep이 실행을 끊음"
