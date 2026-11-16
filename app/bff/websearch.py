"""웹 검색 도구. 모델이 web_search를 부르면 BFF가 Amazon Bedrock AgentCore Web Search(InvokeWebSearch)로 검색한다.

추론은 Gemma와 Qwen이 한다. 언제 검색할지, 무엇을 검색할지, 결과로 어떻게 답할지를 모델이 정하고,
BFF는 검색을 대신 실행해 결과에 번호를 붙여 돌려준다. 번호와 주소는 화면이 출처 목록으로 보여 준다
(AgentCore Web Search의 이용 조건: 검색 결과를 쓴 출력에는 출처와 링크를 표시해야 한다).

- 권한: 태스크 역할의 bedrock-agentcore:InvokeWebSearch. 자격 증명을 코드에 두지 않는다.
- 리전: InvokeWebSearch는 서울 리전에 없다(2026-11-15). WEB_SEARCH_REGION으로 부를 리전을 정하고(배포 값은 us-east-1),
  비어 있으면 웹 검색을 쓰지 않는다. 검색어는 그 리전으로 나간다.
"""
import asyncio
import datetime
import os
import time
import zoneinfo

import routing
from texts import text

REGION = os.environ.get("WEB_SEARCH_REGION", "")
MAX_RESULTS = int(os.environ.get("WEB_SEARCH_MAX_RESULTS", "5"))
# 결과 하나의 본문은 1,000자에서 1,600자였다(2026-11-15, 2건). 모델에 넘기는 길이를 제한해 입력 토큰을 줄인다.
TEXT_CHARS = int(os.environ.get("WEB_SEARCH_TEXT_CHARS", "1200"))
TIMEOUT = float(os.environ.get("WEB_SEARCH_TIMEOUT_SECONDS", "8"))
QUERY_CHARS = 200  # InvokeWebSearch의 searchQuery 상한
WEB_SEARCH_ID = "web-search.v1"


def tool(lang="ko"):
    """모델 요청에 붙이는 도구 정의. 설명은 요청의 언어를 따른다."""
    return {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": text("search.tool", lang),
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": text("search.tool.query", lang)}},
                "required": ["query"],
            },
        },
    }


_client = None


def enabled():
    return bool(REGION)


def instruction(lang="ko", now=None):
    """검색 도구를 붙인 요청의 시스템 메시지에 더하는 지시문. 모델은 오늘 날짜를 모르므로 함께 알려 준다."""
    today = (now or datetime.datetime.now(zoneinfo.ZoneInfo("Asia/Seoul"))).strftime("%Y-%m-%d")
    return text("search.instruction", lang, today=today)


def invoke(query):
    """InvokeWebSearch를 부른다(블로킹). 시험은 이 함수를 바꿔 끼운다."""
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config
        _client = boto3.client("bedrock-agentcore", region_name=REGION,
                               config=Config(connect_timeout=3, read_timeout=TIMEOUT, retries={"max_attempts": 2}))
    return _client.invoke_web_search(webSearchId=WEB_SEARCH_ID, searchQuery=query, maxResults=MAX_RESULTS)["results"]


class Sources:
    """요청 하나에서 모은 출처. 검색을 여러 번 해도 번호가 이어지고, 같은 주소는 같은 번호를 쓴다."""

    def __init__(self):
        self.items = []  # {"n", "title", "url", "published_at"}
        self._by_url = {}

    def add(self, result):
        url = result["url"]
        if url not in self._by_url:
            published = result.get("publishedAt")
            item = {"n": len(self.items) + 1, "title": result.get("title") or url, "url": url,
                    "published_at": published.strftime("%Y-%m-%d") if hasattr(published, "strftime") else published}
            self.items.append(item)
            self._by_url[url] = item
        return self._by_url[url]


async def run(query, sources, lang="ko"):
    """검색을 실행한다. (모델에 돌려줄 도구 결과, 화면과 로그에 남길 알림)을 돌려준다."""
    query = " ".join(str(query or "").split())[:QUERY_CHARS]
    note = {"query": query, "sources": []}
    if not query:
        note["error"] = "empty_query"
        return {"error": text("search.empty_query", lang), "results": []}, note
    # 모델이 만든 검색어에 형식이 정해진 민감 정보가 들어 있으면 밖으로 보내지 않는다.
    if routing.sensitive_kind(query):
        note.update(query="", error="sensitive_query")
        return {"error": text("search.sensitive_query", lang), "results": []}, note
    started = time.monotonic()
    try:
        found = await asyncio.wait_for(asyncio.to_thread(invoke, query), TIMEOUT + 4)
    except Exception as error:  # 검색이 실패해도 답변은 이어 간다. 모델에는 실패했다고 알린다.
        note.update(error=type(error).__name__, search_ms=round((time.monotonic() - started) * 1000, 1))
        return {"query": query, "error": text("search.failed", lang), "results": []}, note
    note["search_ms"] = round((time.monotonic() - started) * 1000, 1)
    results = []
    for result in found:
        # 주소가 없는 결과는 출처를 표시할 수 없으므로 쓰지 않는다.
        if not result.get("url") or not result.get("text"):
            continue
        item = sources.add(result)
        results.append({**item, "text": result["text"][:TEXT_CHARS]})
        if item not in note["sources"]:
            note["sources"].append(item)
    return {"query": query, "results": results}, note
