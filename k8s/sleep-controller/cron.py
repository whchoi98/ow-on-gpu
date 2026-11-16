"""CronJob이 실행하는 명령. 표준 라이브러리만 쓴다.

  python3 cron.py sleep   Qwen이 깨어 있으면 level 1 sleep으로 보낸다
  python3 cron.py wake    깨우기 API를 호출한다
"""
import json
import os
import sys
import time
import urllib.request


def call(method, url, timeout):
    request = urllib.request.Request(url, data=b"" if method == "POST" else None, method=method)
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response), round(time.monotonic() - started, 3)


def main():
    action = sys.argv[1]
    if action == "sleep":
        qwen = os.environ["QWEN_ADMIN_URL"].rstrip("/")
        if call("GET", qwen + "/is_sleeping", 5)[0]["is_sleeping"]:
            result = {"action": "sleep", "already_sleeping": True}
        else:
            # mode=wait는 진행 중인 요청이 끝난 뒤에 잠든다. 기본값 abort는 진행 중인 요청을 끊는다.
            _, seconds = call("POST", qwen + "/sleep?level=1&mode=wait", 600)
            sleeping = call("GET", qwen + "/is_sleeping", 5)[0]["is_sleeping"]
            result = {"action": "sleep", "already_sleeping": False, "sleeping": sleeping, "seconds": seconds}
        ok = result.get("already_sleeping") or result.get("sleeping")
    elif action == "wake":
        body, seconds = call("POST", os.environ["WAKE_API_URL"].rstrip("/") + "/wake", 180)
        result = {"action": "wake", "seconds": seconds, **body}
        ok = body["awake"]
    else:
        raise SystemExit(f"알 수 없는 명령: {action}")
    print(json.dumps(result), flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
