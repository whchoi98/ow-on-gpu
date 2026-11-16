#!/bin/bash
# Claude Code 이벤트를 웹훅으로 알린다.
# Notification 이벤트가 부른다(stdin의 JSON). 손으로 돌리거나 시험할 때는
# `notify.sh <이벤트> <메시지>`처럼 인자를 준다.
# 환경 변수 CLAUDE_NOTIFY_WEBHOOK이 비어 있으면 아무것도 하지 않는다.

WEBHOOK_URL="${CLAUDE_NOTIFY_WEBHOOK:-}"
[ -z "$WEBHOOK_URL" ] && exit 0

if [ "$#" -ge 1 ]; then
    EVENT="${1:-unknown}"
    MESSAGE="${2:-Claude Code event occurred}"
else
    INPUT=$(cat)
    EVENT=$(jq -r '.notification_type // .hook_event_name // "unknown"' <<<"$INPUT" 2>/dev/null)
    MESSAGE=$(jq -r '.message // "Claude Code event occurred"' <<<"$INPUT" 2>/dev/null)
fi

# 메시지의 따옴표나 줄바꿈이 JSON을 깨지 않게 jq로 본문을 만든다
PAYLOAD=$(jq -n \
    --arg text "[$EVENT] $MESSAGE" \
    --arg project "$(basename "${CLAUDE_PROJECT_DIR:-$(pwd)}")" \
    --arg branch "$(git branch --show-current 2>/dev/null || echo unknown)" \
    --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '{text: $text, project: $project, branch: $branch, timestamp: $timestamp}')

# 기다리지 않고 보낸다
curl -s -X POST "$WEBHOOK_URL" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" > /dev/null 2>&1 &
