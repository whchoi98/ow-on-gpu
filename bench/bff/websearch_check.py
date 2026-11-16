#!/usr/bin/env python3
"""CloudFront 주소로 웹 검색을 켠 요청을 보내 도구 호출, 출처, 답변의 출처 번호를 확인한다. 표준 라이브러리만 쓴다.

  USER_PASSWORD=... python3 websearch_check.py --url https://dxxxx.cloudfront.net \
      --email demo@example.com --client-id <앱 클라이언트 ID> --out results/<날짜>-websearch

로그인은 Cognito InitiateAuth(USER_PASSWORD_AUTH)로 한다. 비밀번호는 환경 변수 USER_PASSWORD로만 받는다.
확인하는 것
  1. 웹 검색을 켠 요청: x-bff-search가 on이고, 검색 알림(검색어, BFF가 잰 검색 시간, 출처)이 오고, 답변에 [n]이 붙는다
  2. 켜지 않은 요청: x-bff-search가 off이고 검색하지 않는다
  3. 민감 정보가 있는 요청: 켜도 x-bff-search가 sensitive이고 검색하지 않는다
  4. 스트리밍이 아닌 요청: 본문에 bff_sources가 온다
"""
import argparse
import http.client
import json
import os
import pathlib
import re
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


def ask(url, token, prompt, task="", search=True, stream=True, max_tokens=700):
    """요청 하나를 보내고 헤더, 검색 알림, 답변, 시각을 모아 돌려준다."""
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token}
    if task:
        headers["x-task"] = task
    if search:
        headers["x-web-search"] = "on"
    body = {"messages": [{"role": "user", "content": prompt}], "stream": stream, "max_tokens": max_tokens}
    connection = http.client.HTTPSConnection(urllib.parse.urlparse(url).netloc, timeout=280)
    started = time.monotonic()
    connection.request("POST", "/v1/chat/completions", body=json.dumps(body).encode(), headers=headers)
    response = connection.getresponse()
    got = {k.lower(): v for k, v in response.getheaders()}
    result = {"prompt": prompt, "task": task, "asked_search": search, "stream": stream, "status": response.status,
              "model": got.get("x-bff-model"), "decision": got.get("x-bff-decision"), "search": got.get("x-bff-search"),
              "sensitive": got.get("x-bff-sensitive"), "request_id": got.get("x-request-id"),
              "notes": [], "answer": "", "first_content_ms": None}
    if not stream or response.status != 200:
        raw = response.read().decode("utf-8", "replace")
        connection.close()
        result["total_ms"] = round((time.monotonic() - started) * 1000, 1)
        try:
            parsed = json.loads(raw)
            result["answer"] = parsed["choices"][0]["message"].get("content") or ""
            result["bff_sources"] = parsed.get("bff_sources")
        except (ValueError, KeyError, IndexError):
            result["error"] = raw[:300]
        return result
    for line in response:
        text = line.decode("utf-8", "replace").strip()
        if text.startswith(": bff "):
            result["notes"].append(json.loads(text[6:]))
        elif text.startswith("data: ") and text != "data: [DONE]":
            delta = (json.loads(text[6:]).get("choices") or [{}])[0].get("delta", {})
            if delta.get("content"):
                if result["first_content_ms"] is None:
                    result["first_content_ms"] = round((time.monotonic() - started) * 1000, 1)
                result["answer"] += delta["content"]
    connection.close()
    result["total_ms"] = round((time.monotonic() - started) * 1000, 1)
    return result


def summarize(result):
    searches = [note for note in result["notes"] if note.get("name") == "web_search"]
    numbers = {source["n"] for note in searches for source in note.get("sources", [])}
    cited = {int(n) for group in re.findall(r"\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\]", result["answer"]) for n in group.split(",")}
    return {"searches": len(searches), "search_ms": [note.get("search_ms") for note in searches],
            "sources": len(numbers), "cited": sorted(cited), "cited_known": sorted(cited & numbers),
            "errors": [note["error"] for note in searches if note.get("error")]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--region", default="ap-northeast-2")
    parser.add_argument("--models", default="gemma,qwen", help="웹 검색을 켠 요청을 보낼 모델")
    parser.add_argument("--out")
    args = parser.parse_args()
    token = sign_in(args.region, args.client_id, args.email, os.environ["USER_PASSWORD"])

    cases = {
        # 번역 업무는 Gemma, 코딩 업무는 Qwen으로 간다.
        "gemma": ("summarize", "Amazon Bedrock AgentCore Web Search API를 쓸 수 있는 AWS 리전을 검색해서 알려 주세요."),
        "qwen": ("coding", "Kubernetes 최신 릴리스의 주요 변경점을 검색해서 세 가지로 정리해 주세요."),
    }
    rows, failed = [], []

    def check(name, condition):
        print(("통과  " if condition else "실패  ") + name, flush=True)
        if not condition:
            failed.append(name)

    for model in [m for m in args.models.split(",") if m]:
        task, prompt = cases[model]
        result = ask(args.url, token, prompt, task=task)
        info = summarize(result)
        rows.append({"case": f"search-on-{model}", **result, "summary": info})
        print(f"\n[{model}] 모델 {result['model']}, x-bff-search {result['search']}, 검색 {info['searches']}회 {info['search_ms']}ms, "
              f"출처 {info['sources']}개, 답변의 번호 {info['cited']}, 첫 내용 {result['first_content_ms']}ms, 전체 {result['total_ms']}ms")
        check(f"{model}: 검색 도구가 붙음(x-bff-search: on)", result["status"] == 200 and result["search"] == "on")
        check(f"{model}: 모델이 검색을 불렀고 출처가 옴", info["searches"] >= 1 and info["sources"] >= 1 and not info["errors"])
        check(f"{model}: 답변의 출처 번호가 받은 출처 안에 있음", bool(info["cited"]) and info["cited"] == info["cited_known"])

    result = ask(args.url, token, "안녕하세요를 영어로 옮겨 주세요.", task="translate", search=False, max_tokens=64)
    rows.append({"case": "search-off", **result, "summary": summarize(result)})
    check("켜지 않은 요청: x-bff-search off, 검색 없음", result["search"] == "off" and not result["notes"])

    result = ask(args.url, token, "제 주민등록번호 900101-1234567로 가입된 서비스가 있는지 검색해 주세요.", max_tokens=128)
    rows.append({"case": "search-sensitive", **result, "summary": summarize(result)})
    check("민감 정보 요청: x-bff-search sensitive, 검색 없음",
          result["search"] == "sensitive" and result["sensitive"] == "true" and not result["notes"])

    if "gemma" in args.models:
        result = ask(args.url, token, cases["gemma"][1], task="summarize", stream=False)
        rows.append({"case": "search-non-streaming", **result})
        check("스트리밍이 아닌 요청: bff_sources가 옴", result["status"] == 200 and bool(result.get("bff_sources")))

    if args.out:
        directory = pathlib.Path(args.out)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "websearch-check.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print("\n실패 " + str(len(failed)) + "건" + (": " + ", ".join(failed) if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
