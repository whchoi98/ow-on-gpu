#!/usr/bin/env python3
"""Qwen의 sleep 진입 시간, 복귀 시간, 복귀 뒤 다시 요청을 받기까지의 시간을 잰다. 표준 라이브러리만 쓴다.

클러스터 안에서 실행한다. 한 번의 순환은 다음과 같다.
  1. 관리용 Service로 /sleep?level=1&mode=wait를 호출하고 걸린 시간을 잰다
  2. 일반 Service에서 파드가 빠질 때까지 기다린다(NotReady 전환 확인)
  3. 깨우기 API의 /wake를 호출하고 걸린 시간을 잰다
  4. 일반 Service가 다시 응답할 때까지, 그리고 게이트웨이로 보낸 대화 요청이 성공할 때까지의 시간을 잰다

출력은 한 줄에 JSON 하나다. 시각은 UTC이고, 파드의 Ready 전환 시각과 맞춰 볼 수 있게 밀리초까지 적는다.

  python3 measure.py --cycles 3
"""
import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.request

ADMIN = "http://vllm-qwen-admin.inference.svc:8000"
SERVICE = "http://vllm-qwen.inference.svc:8000"
WAKE_API = "http://qwen-wake-api.inference.svc:8080"
GATEWAY = "http://inference-gateway.inference.svc"
CHAT = {
    "model": "qwen38-27b",
    "messages": [{"role": "user", "content": "1부터 5까지 더하면 얼마인가요? 숫자만 답하세요."}],
    "max_tokens": 8,
    "temperature": 0,
    "chat_template_kwargs": {"enable_thinking": False},
}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def call(method, url, body=None, timeout=300):
    data = json.dumps(body).encode() if body is not None else (b"" if method == "POST" else None)
    request = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    # vLLM의 /health는 본문 없이 200을 준다.
    return json.loads(raw) if raw else None


def ok(method, url, body=None, timeout=2):
    try:
        call(method, url, body, timeout)
        return True
    except (OSError, urllib.error.HTTPError):
        return False


def wait_until(condition, limit, interval=0.05):
    started = time.monotonic()
    while time.monotonic() - started < limit:
        if condition():
            return round(time.monotonic() - started, 3)
        time.sleep(interval)
    return None


def cycle(index):
    record = {"event": "cycle", "index": index}
    if call("GET", ADMIN + "/is_sleeping", timeout=5)["is_sleeping"]:
        raise SystemExit("시작할 때 Qwen이 이미 잠들어 있습니다")
    if not ok("POST", GATEWAY + "/v1/chat/completions", CHAT, timeout=60):
        raise SystemExit("시작할 때 게이트웨이로 보낸 요청이 실패했습니다")

    record["sleep_called_at"] = now()
    started = time.monotonic()
    call("POST", ADMIN + "/sleep?level=1&mode=wait")
    record["sleep_seconds"] = round(time.monotonic() - started, 3)
    record["sleeping"] = call("GET", ADMIN + "/is_sleeping", timeout=5)["is_sleeping"]
    # 일반 Service는 Ready인 파드만 돌려준다. 응답이 끊기면 NotReady로 전환된 것이다.
    record["service_gone_after_sleep_seconds"] = wait_until(lambda: not ok("GET", SERVICE + "/health", timeout=1), 30)

    record["wake_called_at"] = now()
    started = time.monotonic()
    wake = call("POST", WAKE_API + "/wake")
    record["wake_api_seconds"] = round(time.monotonic() - started, 3)
    record["wake_returned_at"] = now()
    record["wake_api_response"] = wake
    returned = time.monotonic()
    record["service_back_after_wake_seconds"] = wait_until(lambda: ok("GET", SERVICE + "/health", timeout=1), 60)
    gateway = wait_until(lambda: ok("POST", GATEWAY + "/v1/chat/completions", CHAT, timeout=30), 60)
    # 게이트웨이 값은 일반 Service를 기다린 시간을 포함해 깨우기 응답 시점부터 센다.
    record["gateway_ok_after_wake_seconds"] = None if gateway is None else round(time.monotonic() - returned, 3)
    record["gateway_ok_at"] = now()
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--pause", type=float, default=10, help="순환 사이에 쉬는 시간(초)")
    args = parser.parse_args()
    records = []
    for i in range(args.cycles):
        records.append(cycle(i))
        time.sleep(args.pause)
    summary = {"event": "summary", "cycles": len(records)}
    for key in ("sleep_seconds", "wake_api_seconds", "service_gone_after_sleep_seconds",
                "service_back_after_wake_seconds", "gateway_ok_after_wake_seconds"):
        values = [r[key] for r in records if r[key] is not None]
        summary[key] = {"values": values, "min": min(values), "max": max(values)} if values else None
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
