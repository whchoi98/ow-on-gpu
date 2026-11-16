#!/usr/bin/env bash
# WAF 속도 제한 확인. 한 IP에서 한도보다 많은 요청을 보내 403으로 막히는 시점과 풀리는 시점을 잰다.
# 정적 페이지(/)만 부르므로 BFF와 모델에는 부하가 가지 않는다. 막힌 동안에는 이 IP의 모든 요청이 403이다.
#
#   ./waf_rate_check.sh https://dxxxx.cloudfront.net [요청 수=400]
set -euo pipefail
URL=${1:?사용법: ./waf_rate_check.sh <CloudFront 주소> [요청 수]}
COUNT=${2:-400}
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$@"; }
now() { date +%s.%N; }
since() { awk -v a="$1" -v b="$(now)" 'BEGIN { printf "%.1f", b - a }'; }

echo "before: GET / -> $(code "$URL/")"
START=$(now)
echo "burst: $COUNT requests, status counts:"
seq "$COUNT" | xargs -P 20 -I{} curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 "$URL/" | sort | uniq -c
echo "burst finished after $(since "$START")s"

BLOCKED=""
for _ in $(seq 60); do
  if [ "$(code "$URL/")" = "403" ]; then BLOCKED=$(now); echo "blocked: first 403 at $(since "$START")s after burst start"; break; fi
  sleep 5
done
[ -n "$BLOCKED" ] || { echo "not blocked within 300s"; exit 1; }
echo "while blocked: POST /v1/chat/completions -> $(code -X POST -H 'Content-Type: application/json' -d '{}' "$URL/v1/chat/completions")"

# 풀릴 때까지 15초마다 한 번만 확인한다. 확인 요청도 횟수에 들어가므로 자주 보내지 않는다.
for _ in $(seq 60); do
  sleep 15
  if [ "$(code "$URL/")" != "403" ]; then echo "released: $(since "$BLOCKED")s after the first 403"; exit 0; fi
done
echo "still blocked after 900s"; exit 1
