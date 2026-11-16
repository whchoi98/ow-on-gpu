#!/usr/bin/env python3
"""CloudFront 주소로 대화 요청을 보내 SSE 이벤트가 도착한 시각을 기록한다. 표준 라이브러리만 쓴다.

  USER_PASSWORD=... python3 stream_check.py --url https://dxxxx.cloudfront.net \
      --email demo@example.com --client-id <앱 클라이언트 ID> --task support --out result.json

로그인은 Cognito InitiateAuth(USER_PASSWORD_AUTH)로 한다. 비밀번호는 환경 변수 USER_PASSWORD로만 받는다.
응답이 중간에서 모였다가 한꺼번에 나오면 이벤트 도착 시각이 끝에 몰린다.
"""
import argparse
import http.client
import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request


def sign_in(region, client_id, email, password):
    request = urllib.request.Request(
        f"https://cognito-idp.{region}.amazonaws.com/",
        data=json.dumps({"AuthFlow": "USER_PASSWORD_AUTH", "ClientId": client_id,
                         "AuthParameters": {"USERNAME": email, "PASSWORD": password}}).encode(),
        headers={"Content-Type": "application/x-amz-json-1.1",
                 "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["AuthenticationResult"]["AccessToken"]


def call(url, method, path, headers, body=None):
    """(상태 코드, 헤더, 응답 객체, 연결)을 돌려준다. 본문은 호출한 쪽이 읽는다."""
    parsed = urllib.parse.urlparse(url)
    connection = http.client.HTTPSConnection(parsed.netloc, timeout=120)
    connection.request(method, path, body=json.dumps(body).encode() if body is not None else None, headers=headers)
    response = connection.getresponse()
    return response.status, dict(response.getheaders()), response, connection


def status_only(url, method, path, headers, body=None):
    status, _, response, connection = call(url, method, path, headers, body)
    response.read()
    connection.close()
    return status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--region", default="ap-northeast-2")
    parser.add_argument("--task", default="support")
    parser.add_argument("--prompt", default="주문 번호 A-1024의 배송 상태를 알려 주세요.")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--out")
    args = parser.parse_args()

    body = {"messages": [{"role": "user", "content": args.prompt}], "stream": True, "max_tokens": args.max_tokens}
    json_headers = {"Content-Type": "application/json"}
    result = {"url": args.url, "task": args.task, "prompt": args.prompt, "checks": {}}

    # 로그인 없이는 통과하지 못해야 한다.
    result["checks"]["post_without_token"] = status_only(args.url, "POST", "/v1/chat/completions", json_headers, body)
    result["checks"]["post_with_bad_token"] = status_only(
        args.url, "POST", "/v1/chat/completions", {**json_headers, "Authorization": "Bearer not-a-token"}, body)

    token = sign_in(args.region, args.client_id, args.email, os.environ["USER_PASSWORD"])
    authorized = {**json_headers, "Authorization": "Bearer " + token}
    # BFF에는 이 경로가 없다. 인증을 통과하면 404, CloudFront가 GET의 Authorization 헤더를 떼면 401이 온다.
    result["checks"]["get_unknown_path_with_token"] = status_only(args.url, "GET", "/v1/none", authorized)

    headers = {**authorized, "x-session-id": f"stream-check-{int(time.time())}"}
    if args.task:
        headers["x-task"] = args.task
    started = time.monotonic()
    status, response_headers, response, connection = call(args.url, "POST", "/v1/chat/completions", headers, body)
    headers_at = time.monotonic() - started
    events, text, raw = [], "", b""
    while True:
        line = response.readline()
        if not line:
            break
        raw += line
        at = time.monotonic() - started
        decoded = line.decode("utf-8", "replace").strip()
        if not decoded.startswith("data: ") or decoded == "data: [DONE]":
            continue
        delta = (json.loads(decoded[6:]).get("choices") or [{}])[0].get("delta", {}).get("content")
        if delta:
            events.append({"ms": round(at * 1000, 1), "content": delta})
            text += delta
    total = time.monotonic() - started
    connection.close()

    arrivals = [event["ms"] for event in events]
    gaps = [round(b - a, 1) for a, b in zip(arrivals, arrivals[1:])]
    keep = ("content-type", "x-bff-model", "x-bff-decision", "x-bff-sensitive", "x-request-id", "x-cache", "via",
            "transfer-encoding", "content-encoding")
    result.update({
        "status": status,
        "response_headers": {k: v for k, v in response_headers.items() if k.lower() in keep},
        "headers_ms": round(headers_at * 1000, 1),
        "first_content_ms": arrivals[0] if arrivals else None,
        "last_content_ms": arrivals[-1] if arrivals else None,
        "total_ms": round(total * 1000, 1),
        "content_events": len(events),
        "gap_ms": {"median": statistics.median(gaps), "max": max(gaps), "min": min(gaps),
                   # 같은 순간(1ms 안)에 붙어서 온 이벤트의 비율. 버퍼링되면 1에 가까워진다.
                   "share_under_1ms": round(sum(1 for g in gaps if g < 1) / len(gaps), 3)} if gaps else None,
        "text": text,
        "events": events,
    })
    if status != 200:
        result["error_body"] = raw.decode("utf-8", "replace")[:2000]
    if args.out:
        with open(args.out, "w") as out:
            json.dump(result, out, ensure_ascii=False, indent=1)
    summary = {k: v for k, v in result.items() if k not in ("events", "text")}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    print("--- 응답\n" + text)
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
