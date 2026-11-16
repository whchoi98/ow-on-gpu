#!/bin/bash
# .claude/hooks/secret-scan.sh 의 검출과 오검출 시험. 실제 검사기를 실행한다
# (tests/run-all.sh가 source로 불러 실행한다). 표본은 tests/fixtures/에서 읽어 실행할 때 합친다.
# 이 파일의 변수는 SP_로 시작한다.

SP_SCANNER=".claude/hooks/secret-scan.sh"

# --- 검출: 표본마다 .txt와 .md 양쪽에서 잡아야 한다 ---
while IFS=$'\t' read -r SP_NAME SP_PREFIX SP_BODY; do
    [[ -z "$SP_NAME" || "$SP_NAME" == \#* ]] && continue
    for SP_EXT in txt md; do
        SP_SAMPLE="$TEST_TMP/tp-sample.$SP_EXT"
        printf '%s%s\n' "$SP_PREFIX" "$SP_BODY" > "$SP_SAMPLE"
        if bash "$SP_SCANNER" --files "$SP_SAMPLE" >/dev/null 2>&1; then
            fail "검출 ($SP_EXT): $SP_NAME" "검사기가 표본을 잡지 못함"
        else
            pass "검출 ($SP_EXT): $SP_NAME"
        fi
    done
done < tests/fixtures/secret-samples.txt

# --- 환경 식별 값: 표본마다 검사기가 막고, 가리기 도구를 거치면 통과해야 한다 ---
while IFS=$'\t' read -r SP_NAME SP_PREFIX SP_BODY; do
    [[ -z "$SP_NAME" || "$SP_NAME" == \#* ]] && continue
    SP_SAMPLE="$TEST_TMP/id-sample.txt"
    printf 'value: %s%s end\n' "$SP_PREFIX" "$SP_BODY" > "$SP_SAMPLE"
    if bash "$SP_SCANNER" --files "$SP_SAMPLE" >/dev/null 2>&1; then
        fail "식별 값 검출: $SP_NAME" "검사기가 표본을 잡지 못함"
    else
        pass "식별 값 검출: $SP_NAME"
    fi
    python3 scripts/mask-identifiers.py "$SP_SAMPLE" >/dev/null 2>&1
    if bash "$SP_SCANNER" --files "$SP_SAMPLE" >/dev/null 2>&1; then
        pass "식별 값을 가리면 통과: $SP_NAME"
    else
        fail "식별 값을 가리면 통과: $SP_NAME" "가린 뒤에도 걸림: $(cat "$SP_SAMPLE")"
    fi
done < tests/fixtures/identifier-samples.txt

# 접근 로그와 Terraform 적용 로그는 파일 이름으로 정한 규칙이 더 있다
SP_SAMPLE="$TEST_TMP/alb-log-lines.txt"
printf 'http 2026-11-16T00:00:00Z %s:443 10.200.1.2:8080\n' "54.182.0.1" > "$SP_SAMPLE"
python3 scripts/mask-identifiers.py "$SP_SAMPLE" >/dev/null 2>&1
assert_eq "가리기: 접근 로그의 공인 IP는 가리고 프라이빗 IP는 둠" "http 2026-11-16T00:00:00Z <ip>:443 10.200.1.2:8080" "$(cat "$SP_SAMPLE")"
SP_SAMPLE="$TEST_TMP/terraform-apply.log"
printf 'aws_s3_bucket.web: Creation complete after 1s [id=demo-bucket]\ncognito_client_id = "abcdefghijklmnopqrstuvwxyz"\ncluster_name = "ow-on-gpu"\n' > "$SP_SAMPLE"
python3 scripts/mask-identifiers.py "$SP_SAMPLE" >/dev/null 2>&1
assert_eq "가리기: Terraform 로그의 리소스 ID와 출력값은 가리고 이름은 둠" \
    'aws_s3_bucket.web: Creation complete after 1s [id=<id>]|cognito_client_id = <masked>|cluster_name = "ow-on-gpu"|' "$(tr '\n' '|' < "$SP_SAMPLE")"
python3 scripts/mask-identifiers.py --check "$TEST_TMP/terraform-apply.log" >/dev/null 2>&1 \
    && pass "가리기: --check는 가릴 것이 없으면 exit 0" || fail "가리기: --check는 가릴 것이 없으면 exit 0" "0이 아님"
printf 'x %s%s\n' "sg-" "0123456789abcdef0" > "$TEST_TMP/check-sample.txt"
python3 scripts/mask-identifiers.py --check "$TEST_TMP/check-sample.txt" >/dev/null 2>&1 \
    && fail "가리기: --check는 가릴 것이 있으면 exit 1" "0을 돌려줌" || pass "가리기: --check는 가릴 것이 있으면 exit 1"
assert_contains "가리기: --check는 파일을 바꾸지 않음" "$(cat "$TEST_TMP/check-sample.txt")" "0123456789abcdef0"

# --- 오검출: 아래 줄은 하나도 걸리면 안 된다 ---
while IFS= read -r SP_LINE; do
    [ -z "$SP_LINE" ] && continue
    SP_SAMPLE="$TEST_TMP/fp-sample.md"
    printf '%s\n' "$SP_LINE" > "$SP_SAMPLE"
    if bash "$SP_SCANNER" --files "$SP_SAMPLE" >/dev/null 2>&1; then
        pass "오검출 없음: ${SP_LINE:0:40}"
    else
        fail "오검출 없음: ${SP_LINE:0:40}" "비밀 값이 아닌 줄이 걸림"
    fi
done < tests/fixtures/false-positives.txt

# --- 저장소의 파일이 검사를 통과하는지 ---
# git 저장소면 추적하는 파일과 새 파일(무시되지 않은 것)을 본다. 아니면 .gitignore와 같은 제외 규칙으로 찾는다.
if git rev-parse --git-dir >/dev/null 2>&1; then
    mapfile -t SP_FILES < <(git ls-files 2>/dev/null; git ls-files -o --exclude-standard 2>/dev/null)
    SP_SOURCE="git이 추적하는 파일과 새 파일"
else
    mapfile -t SP_FILES < <(find . -type f -not -path "*/node_modules/*" -not -path "*/.terraform/*" \
        -not -path "*/cdk.out/*" -not -path "*/dist/*" -not -path "*/__pycache__/*" -not -name "*.tfstate" \
        -not -name "*.tfstate.*" -not -name ".kubeconfig" -not -name ".env" -not -name "settings.local.json" \
        | sed 's#^\./##')
    SP_SOURCE="git 저장소가 아니어서 .gitignore와 같은 규칙으로 찾은 파일"
fi
if [ "${#SP_FILES[@]}" -gt 0 ] && bash "$SP_SCANNER" --files "${SP_FILES[@]}" >/dev/null 2>&1; then
    pass "저장소: $SP_SOURCE ${#SP_FILES[@]}개가 검사를 통과"
else
    fail "저장소: $SP_SOURCE 가 검사를 통과" "$(bash "$SP_SCANNER" --files "${SP_FILES[@]}" 2>&1 | head -3)"
fi

# --- 건너뛰는 파일과 금지한 파일 ---
bash "$SP_SCANNER" --files .env.example >/dev/null 2>&1 \
    && pass "건너뜀: .env.example은 검사하지 않음" || fail "건너뜀: .env.example은 검사하지 않음" "걸림"
bash "$SP_SCANNER" --files tests/fixtures/secret-samples.txt >/dev/null 2>&1 \
    && pass "건너뜀: 시험 자료는 검사하지 않음" || fail "건너뜀: 시험 자료는 검사하지 않음" "걸림"
for SP_PATH in .env .claude/settings.local.json infra/terraform/terraform.tfstate infra/terraform/terraform.tfstate.backup \
               infra/terraform/.kubeconfig; do
    bash "$SP_SCANNER" --files "$SP_PATH" >/dev/null 2>&1 \
        && fail "금지: $SP_PATH 는 항상 막음" "통과시킴" \
        || pass "금지: $SP_PATH 는 항상 막음"
done
SP_SKIP_LINE=$(grep -m1 '^SKIP_PATTERNS=' "$SP_SCANNER" || true)
assert_not_contains "검사기: Markdown을 건너뛰지 않음" "$SP_SKIP_LINE" "'*.md'"

# --- 회귀: AWS secret 패턴이 PCRE로 컴파일돼야 한다 (길이가 변하는 lookbehind 금지) ---
# grep은 "못 찾음"에 1, 패턴 오류에 2를 돌려준다
SP_AWS_REGEX=$(grep -oP "^\s+'\Kaws_secret_access_key[^']*" "$SP_SCANNER" | head -1 || true)
SP_REGEX_STATUS=0
echo "x" | grep -P -- "$SP_AWS_REGEX" >/dev/null 2>&1 || SP_REGEX_STATUS=$?
if [ -n "$SP_AWS_REGEX" ] && [ "$SP_REGEX_STATUS" -le 1 ]; then
    pass "AWS secret 정규식이 컴파일됨"
else
    fail "AWS secret 정규식이 컴파일됨" "패턴이 없거나 grep -P 오류 (상태 $SP_REGEX_STATUS)"
fi
# 모든 패턴이 컴파일되는지도 본다. 오류가 2>/dev/null에 가려지면 그 패턴은 영원히 못 잡는다
SP_BAD=""
while IFS= read -r SP_REGEX; do
    SP_REGEX_STATUS=0
    echo "x" | grep -P -- "$SP_REGEX" >/dev/null 2>&1 || SP_REGEX_STATUS=$?
    [ "$SP_REGEX_STATUS" -gt 1 ] && SP_BAD="$SP_BAD ${SP_REGEX:0:20}"
done < <(sed -n "/^PATTERNS=(/,/^)/p; /^IDENTIFIER_PATTERNS=(/,/^)/p" "$SP_SCANNER" | grep -oP "^\s+'\K[^']+(?=')")
assert_eq "검사기의 모든 패턴이 컴파일됨" "" "$SP_BAD"
SP_COUNT=$(sed -n "/^IDENTIFIER_PATTERNS=(/,/^)/p" "$SP_SCANNER" | grep -cP "^\s+'" || true)
[ "$SP_COUNT" -ge 10 ] && pass "검사기에 환경 식별 값 패턴이 있음 (${SP_COUNT}개)" || fail "검사기에 환경 식별 값 패턴이 있음" "${SP_COUNT}개"
