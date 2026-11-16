"""Qwen 깨우기 API. 표준 라이브러리만 쓴다.

  POST /wake     Qwen의 /is_sleeping을 확인하고, 잠들어 있으면 /wake_up을 호출한다
  GET  /healthz  이 서버의 상태 확인용

깨우는 동작만 한다. sleep은 이 API로 할 수 없다.
"""
import json
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QWEN = os.environ["QWEN_ADMIN_URL"].rstrip("/")
# 같은 복제본에 깨우기 요청이 겹치면 한 번만 /wake_up을 호출하고 나머지는 결과를 기다린다.
lock = threading.Lock()


def qwen(method, path, timeout):
    request = urllib.request.Request(QWEN + path, data=b"" if method == "POST" else None, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def wake():
    with lock:
        if not qwen("GET", "/is_sleeping", 5)["is_sleeping"]:
            return {"was_sleeping": False, "awake": True}
        started = time.monotonic()
        qwen("POST", "/wake_up", 120)
        seconds = round(time.monotonic() - started, 3)
        # 다른 복제본이 동시에 깨웠을 수도 있으므로 결과는 상태를 다시 읽어 판단한다.
        awake = not qwen("GET", "/is_sleeping", 5)["is_sleeping"]
        return {"was_sleeping": True, "awake": awake, "wake_seconds": seconds}


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body):
        data = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            self.respond(200, {"status": "ok"})
        else:
            self.respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/wake":
            self.respond(404, {"error": "not found"})
            return
        try:
            result = wake()
        except OSError as e:
            self.respond(502, {"error": f"Qwen에 닿지 못했습니다: {e}"})
            return
        print(json.dumps({"event": "wake", **result}), flush=True)
        self.respond(200 if result["awake"] else 502, result)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
