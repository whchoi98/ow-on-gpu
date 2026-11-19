#!/usr/bin/env bash
# Cognito 사용자 풀에 로그인 사용자를 만든다. 사용자 풀은 가입을 막아 두었으므로 이 방법으로만 사용자가 생긴다.
#
#   ./create-user.sh <이메일>
#
# 비밀번호는 프롬프트로 받거나 환경 변수 USER_PASSWORD로 넘긴다. 파일과 Terraform state에는 남기지 않는다.
# 같은 이메일로 다시 실행하면 비밀번호만 바꾼다.
# 환경은 TF_WORKSPACE로 고른다(infra/terraform/environments.tf). 사용자 풀은 환경마다 따로다.
set -euo pipefail
cd "$(dirname "$0")"

EMAIL=${1:?사용법: ./create-user.sh <이메일>}
POOL=$(terraform -chdir=../../infra/terraform output -raw cognito_user_pool_id)
# 사용자 풀 ID는 <리전>_<값> 꼴이다.
REGION=${POOL%%_*}

if [ -z "${USER_PASSWORD:-}" ]; then
  read -r -s -p "비밀번호: " USER_PASSWORD
  echo
fi

if ! aws cognito-idp admin-get-user --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" >/dev/null 2>&1; then
  # 초대 메일을 보내지 않는다. 아래에서 비밀번호를 바로 확정한다.
  aws cognito-idp admin-create-user --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" \
    --user-attributes Name=email,Value="$EMAIL" Name=email_verified,Value=true \
    --message-action SUPPRESS --query 'User.UserStatus' --output text
fi

# 비밀번호가 명령줄 인자로 드러나지 않도록 본인만 읽는 임시 파일로 넘기고 바로 지운다.
# AWS CLI 2.38.5는 --cli-input-json을 표준 입력이나 프로세스 치환에서 읽지 못했다(Invalid JSON received).
INPUT=$(mktemp)
trap 'rm -f "$INPUT"' EXIT
jq -n --arg pool "$POOL" --arg user "$EMAIL" --arg password "$USER_PASSWORD" \
  '{UserPoolId: $pool, Username: $user, Password: $password, Permanent: true}' > "$INPUT"
aws cognito-idp admin-set-user-password --region "$REGION" --cli-input-json "file://$INPUT"

aws cognito-idp admin-get-user --region "$REGION" --user-pool-id "$POOL" --username "$EMAIL" \
  --query '{status: UserStatus, enabled: Enabled}' --output json
