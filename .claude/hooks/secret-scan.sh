#!/bin/bash
# 커밋되기 전에 파일에 비밀 값과 환경 식별 값이 있는지 본다.
# 이 저장소는 공개 저장소에 올라간다. 계정 ID, ARN, CloudFront 주소 같은 값은 올리지 않는다(AGENT.md 작업 규칙).
#
# 실행 방식:
#   (인자 없음)       PreToolUse 훅(matcher: Bash). stdin의 이벤트 JSON을 읽고 `git commit` 명령일 때만 동작한다.
#                     exit 2면 도구 호출이 막히고 stderr의 이유가 Claude에게 전달된다.
#   --staged          git pre-commit 훅(scripts/install-hooks.sh가 설치). exit 1이면 커밋이 막힌다.
#   --files F [F..]   준 파일만 본다(손으로 돌리거나 시험할 때). 비밀 값이 있으면 exit 1.
#
# 이 저장소의 문서와 측정 원시 자료는 대부분 Markdown과 JSON이라 *.md도 검사한다.

PATTERNS=(
    'AKIA[0-9A-Z]{16}'                                              # AWS Access Key ID
    'aws_secret_access_key\s{0,5}[=:]\s{0,5}["\x27]?[A-Za-z0-9/+=]{40}' # AWS Secret Key(앞뒤 문맥 포함)
    'sk-[A-Za-z0-9]{20}T3BlbkFJ[A-Za-z0-9]{20}'                     # OpenAI API Key
    'sk-ant-[A-Za-z0-9-]{90,}'                                      # Anthropic API Key
    'hf_[A-Za-z0-9]{34}'                                            # Hugging Face 토큰(모델 적재 Job이 쓴다)
    'ghp_[A-Za-z0-9]{36}'                                           # GitHub Personal Access Token
    'gho_[A-Za-z0-9]{36}'                                           # GitHub OAuth Token
    'github_pat_[A-Za-z0-9_]{82}'                                   # GitHub Fine-grained PAT
    'xoxb-[0-9]+-[A-Za-z0-9]+'                                      # Slack Bot Token
    'xoxp-[0-9]+-[A-Za-z0-9]+'                                      # Slack User Token
    'sk_live_[A-Za-z0-9]{24,}'                                      # Stripe Secret Key
    'rk_live_[A-Za-z0-9]{24,}'                                      # Stripe Restricted Key
    'AIza[A-Za-z0-9_-]{35}'                                         # Google API Key
    'ya29\.[A-Za-z0-9_-]{50,}'                                      # Google OAuth Token
    'DefaultEndpointsProtocol=https;Account'                        # Azure Connection String
    'password\s*[:=]\s*["\x27][^"\x27]{8,}'                         # 비밀번호 대입
    'secret\s*[:=]\s*["\x27][^"\x27]{8,}'                           # secret 대입
    'api[_-]?key\s*[:=]\s*["\x27][^"\x27]{8,}'                      # API 키 대입
)

# AWS 환경을 식별하는 값. 비밀은 아니지만 올리지 않는다. scripts/mask-identifiers.py가 같은 종류를 자리 표시로 바꾼다.
# 763104351884는 AWS가 공개한 Deep Learning Containers 레지스트리 계정이라 막지 않는다(k8s/decider의 이미지 주소).
IDENTIFIER_PATTERNS=(
    'arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:([0-9]{12}|<account-id>):'                # 계정이 든 ARN(가린 계정 포함)
    '(?<![0-9])(?!763104351884)[0-9]{12}\.dkr\.ecr\.'                               # ECR 레지스트리 주소의 계정 ID
    '(account=|AWSLogs/|"Account": "|"OwnerId": ")[0-9]{12}(?![0-9])'              # 그 밖의 자리의 계정 ID
    '\b[a-z0-9]{10,16}\.cloudfront\.net\b'                                          # CloudFront 도메인
    '\b[a-z]{2}-[a-z]+-[0-9]_[A-Za-z0-9]{9}\b'                                      # Cognito 사용자 풀 ID
    '\b[A-Za-z0-9-]+\.(elb\.[a-z0-9-]+|[a-z0-9-]+\.elb)\.amazonaws\.com\b'        # 로드 밸런서 주소
    '\b(app|net)/[A-Za-z0-9-]{1,32}/[0-9a-f]{16}\b'                                 # 로드 밸런서 ID
    '\b[A-Fa-f0-9]{32}\.[a-z0-9]+\.[a-z0-9-]+\.eks\.amazonaws\.com\b'             # EKS 엔드포인트
    '\bws-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'           # Prometheus 작업 공간 ID
    '\bow-on-gpu-([a-z]+-)*[0-9a-f]{16,}\b'                                         # 버킷 이름의 무작위 접미사
    '\b(vpc|subnet|sgr|sg|eni|eipalloc|nat|igw|rtb|vpce|i)-[0-9a-f]{8,17}\b'        # VPC, 서브넷, 보안 그룹, 인스턴스 ID
    '\bvo_[A-Za-z0-9]{10,}\b'                                                       # CloudFront VPC origin ID
    '(?<![0-9.])(?!10\.|127\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)([0-9]{1,3}\.){3}[0-9]{1,3}/32\b'  # 공인 IP 하나를 가리키는 CIDR
)

# 검사하지 않는 파일: 자리만 있는 템플릿, 잠금 파일, 그리고 검사기 자신의 시험 자료
SKIP_PATTERNS=('.env.example' '*secret-scan.sh' '*package-lock.json' '*yarn.lock'
               'tests/fixtures/*' 'tests/hooks/test-secret-patterns.sh')

# 내용과 상관없이 커밋하면 안 되는 파일. Terraform 상태에는 레지스트리 토큰이 들어 있다.
FORBIDDEN_PATHS=('.env' '.claude/settings.local.json' 'infra/terraform/terraform.tfstate'
                 'infra/terraform/terraform.tfstate.backup' 'infra/terraform/.kubeconfig')

scan_files() {
    local found=0 file pattern regex skip combined status
    local -a candidates=() hits=()
    for file in "$@"; do
        skip=false
        for pattern in "${SKIP_PATTERNS[@]}"; do
            [[ "$file" == $pattern ]] && skip=true && break
        done
        $skip && continue
        for pattern in "${FORBIDDEN_PATHS[@]}"; do
            if [ "$file" = "$pattern" ]; then
                echo "[secret-scan] $file 은 커밋하면 안 되는 파일입니다" >&2
                found=1
            fi
        done
        [ -f "$file" ] && candidates+=("$file")
    done
    [ "${#candidates[@]}" -eq 0 ] && return $found

    # 모든 패턴을 하나로 묶어 먼저 본다. 걸린 파일만 패턴별로 다시 봐서 무엇이 걸렸는지 알린다.
    combined=$(printf '(?:%s)|' "${PATTERNS[@]}" "${IDENTIFIER_PATTERNS[@]}")
    combined="${combined%|}"
    # 패턴이 컴파일되지 않으면 grep이 아무것도 찾지 못한 것처럼 보인다. 그 경우 통과시키지 않고 막는다.
    status=0
    echo "x" | grep -qP -- "$combined" 2>/dev/null || status=$?
    if [ "$status" -gt 1 ]; then
        echo "[secret-scan] 검사 패턴에 오류가 있어 검사할 수 없습니다 (grep 상태 $status)" >&2
        return 1
    fi
    # -I는 바이너리 파일을 건너뛴다
    mapfile -d '' -t hits < <(printf '%s\0' "${candidates[@]}" | xargs -0 grep -IlZP -- "$combined" 2>/dev/null)
    for file in "${hits[@]}"; do
        for regex in "${PATTERNS[@]}"; do
            if grep -IqP -- "$regex" "$file" 2>/dev/null; then
                echo "[secret-scan] $file 에 비밀 값으로 보이는 문자열이 있습니다 (패턴: ${regex:0:30}...)" >&2
                found=1
            fi
        done
        for regex in "${IDENTIFIER_PATTERNS[@]}"; do
            if grep -IqP -- "$regex" "$file" 2>/dev/null; then
                echo "[secret-scan] $file 에 환경 식별 값이 있습니다 (패턴: ${regex:0:30}...). python3 scripts/mask-identifiers.py $file 로 가립니다" >&2
                found=1
            fi
        done
    done
    return $found
}

report_blocked() {
    echo "" >&2
    echo "[secret-scan] 막음: 커밋하려는 파일에 비밀 값이나 환경 식별 값이 있습니다." >&2
    echo "[secret-scan] 비밀 값은 지우고 .env(커밋하지 않음)에 두거나 명령의 환경 변수로 넘깁니다." >&2
    echo "[secret-scan] 계정 ID, ARN, CloudFront 주소 같은 식별 값은 scripts/mask-identifiers.py로 가립니다. 환경별 값이 든 파일은 *.example만 추적합니다." >&2
}

case "${1:-}" in
    --files)
        shift
        scan_files "$@" || { report_blocked; exit 1; }
        exit 0
        ;;
    --staged)
        mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
        [ "${#FILES[@]}" -eq 0 ] && exit 0
        scan_files "${FILES[@]}" || { report_blocked; exit 1; }
        exit 0
        ;;
esac

# PreToolUse 방식
COMMAND=$(jq -r '.tool_input.command // empty' 2>/dev/null)
[[ "$COMMAND" =~ git[[:space:]]+([^|;&]*[[:space:]])?commit ]] || exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

mapfile -t FILES < <(git diff --cached --name-only --diff-filter=ACM 2>/dev/null)
# `git add ... && git commit`이나 `commit -a`는 이 훅이 돈 뒤에 파일을 스테이징한다.
# 그래서 수정된 파일과 추적하지 않는(무시되지 않은) 파일도 함께 본다.
if [[ "$COMMAND" =~ git[[:space:]]+add || "$COMMAND" =~ commit[[:space:]].*[[:space:]](-[a-zA-Z]*a[a-zA-Z]*|--all)([[:space:]]|$) ]]; then
    mapfile -t -O "${#FILES[@]}" FILES < <(git ls-files -m -o --exclude-standard 2>/dev/null)
fi
[ "${#FILES[@]}" -eq 0 ] && exit 0

mapfile -t FILES < <(printf '%s\n' "${FILES[@]}" | sort -u)
scan_files "${FILES[@]}" || { report_blocked; exit 2; }
exit 0
