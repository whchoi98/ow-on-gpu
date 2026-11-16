"""BFF 문구의 한영 전환(x-lang)을 실제 모델까지 보내 확인한다. 동작 확인용이고 시간 측정이 아니다.

배포된 BFF 파드 안에서 실행한다. 같은 앱을 토큰 검증기만 바꿔 127.0.0.1:18080에 띄우고 그쪽으로 요청을 보낸다.
배포된 8080 포트의 서비스와 그 로그는 건드리지 않는다. 로그인 비밀번호가 필요 없다.

    kubectl -n app exec -i <bff 파드> -- python - < bench/bff/lang_check_in_pod.py > in-pod.json

인자를 주면 이름에 그 말이 든 요청만 보낸다. 예: python - "no task" "search gemma" (잠든 Qwen을 깨우지 않으려 할 때)
"""
import asyncio
import contextlib
import io
import json
import re
import sys
import uuid

import aiohttp
from aiohttp import web

import bff

EN_SEARCH = "What is the latest stable Kubernetes release? Search the web and answer in two sentences."
KO_SEARCH = "쿠버네티스 최신 안정 버전이 무엇인지 웹에서 찾아 두 문장으로 답해 주세요."
SEARCH = {"x-web-search": "on"}

# (이름, 헤더, 질문). x-task가 있으면 Decider를 거치지 않고 업무 종류로 모델이 정해진다.
CASES = [
    ("en order A-1024", {"x-lang": "en", "x-task": "support"}, "Where is my order A-1024?"),
    ("en order A-9999", {"x-lang": "en", "x-task": "support"}, "Can you check order A-9999 for me?"),
    ("ko order A-1024", {"x-lang": "ko", "x-task": "support"}, "주문 A-1024 지금 어디쯤인가요?"),
    ("en search gemma", {"x-lang": "en", "x-task": "summarize", **SEARCH}, EN_SEARCH),
    ("ko search gemma", {"x-lang": "ko", "x-task": "summarize", **SEARCH}, KO_SEARCH),
    ("en search qwen", {"x-lang": "en", "x-task": "coding", **SEARCH}, EN_SEARCH),
    ("en search no task", {"x-lang": "en", **SEARCH}, EN_SEARCH),
    ("ko search no task", {"x-lang": "ko", **SEARCH}, KO_SEARCH),
]


class AnyToken:
    async def verify(self, http, token):
        return {"sub": "lang-check"}


async def ask(client, name, headers, question):
    out = {"case": name, "question": question}
    body = {"messages": [{"role": "user", "content": question}], "stream": True, "max_tokens": 400}
    headers = {"Authorization": "Bearer x", "x-session-id": uuid.uuid4().hex, **headers}
    async with client.post("http://127.0.0.1:18080/v1/chat/completions", json=body, headers=headers) as response:
        out["status"] = response.status
        if response.status != 200:
            out["body"] = (await response.text())[:300]
            return out
        for key in ("x-bff-model", "x-bff-decision", "x-bff-search", "x-bff-reason"):
            out[key] = response.headers.get(key)
        content, tool_calls = [], []
        async for raw in response.content:
            line = raw.decode().strip()
            if line.startswith(": bff "):
                tool_calls.append(json.loads(line[6:]))
            elif line.startswith("data: ") and line != "data: [DONE]":
                for choice in json.loads(line[6:]).get("choices", []):
                    content.append(choice.get("delta", {}).get("content") or "")
    out["tool_calls"] = tool_calls
    out["answer"] = "".join(content).strip()
    sources = max((len(call.get("sources", [])) for call in tool_calls), default=0)
    cited = sorted({int(number) for number in re.findall(r"\[(\d+)\]", out["answer"])})
    out["sources"], out["cited"] = sources, cited
    out["cited_within_sources"] = all(1 <= number <= sources for number in cited) if cited else None
    return out


async def main():
    runner = web.AppRunner(bff.create_app(AnyToken()), access_log=None)
    await runner.setup()
    await web.TCPSite(runner, "127.0.0.1", 18080).start()
    results = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=240)) as client:
        for case in [case for case in CASES if not sys.argv[1:] or any(word in case[0] for word in sys.argv[1:])]:
            try:
                results.append(await ask(client, *case))
            except Exception as error:
                results.append({"case": case[0], "error": repr(error)})
    await runner.cleanup()
    return results


logs = io.StringIO()
with contextlib.redirect_stdout(logs):  # bff.log()의 출력이 결과 JSON에 섞이지 않게 따로 받는다
    results = asyncio.run(main())
print(json.dumps({"results": results}, ensure_ascii=False, indent=1))
