"""BFF: OpenAI 호환 /v1/chat/completions를 받아 모델을 정하고 게이트웨이로 넘긴다.

스트리밍 응답은 모으지 않고 받은 그대로 흘려보낸다.
"""
import asyncio
import json
from dataclasses import replace
import os
import re
import time
import uuid

from aiohttp import ClientError, ClientSession, ClientTimeout, web

import auth
import routing
import websearch
from texts import language, text

GATEWAY_URL = os.environ["GATEWAY_URL"].rstrip("/")
WAKE_API_URL = os.environ["WAKE_API_URL"].rstrip("/")
DECIDER_MIN_CONFIDENCE = float(os.environ.get("DECIDER_MIN_CONFIDENCE", "0.6"))
DECIDER_TIMEOUT = float(os.environ.get("DECIDER_TIMEOUT_SECONDS", "2"))
SESSION_TTL = float(os.environ.get("SESSION_TTL_SECONDS", "1800"))
# 깨운 직후에는 게이트웨이가 Qwen 파드를 다시 잡을 때까지 503이 온다(docs/06-sleep.md에서 약 1.4초).
WAKE_RETRY_SECONDS = float(os.environ.get("WAKE_RETRY_SECONDS", "10"))
# vLLM의 priority는 값이 작을수록 먼저 처리된다.
PRIORITY = {"interactive": 0, "batch": 10}
# 요청 하나에서 모델이 도구를 부를 수 있는 횟수(차례). 마지막 차례 뒤에는 도구 없이 답하게 한다.
MAX_TOOL_ROUNDS = 3

DECIDER_QUESTIONS = {
    "route": {
        "type": "choice",
        "instructions": "이 요청을 처리할 모델을 고르세요.",
        "criteria": {
            "gemma": "고객 상담, 주문 조회, 번역, 요약처럼 텍스트만 다루는 요청",
            "qwen": "이미지나 문서를 읽어야 하거나 코드를 작성하고 고치는 요청",
        },
    },
    "policy": {"type": "noul", "instructions": "이 요청에 이름, 연락처, 주소, 계좌 같은 개인정보가 들어 있습니까?"},
    "thinking": {"type": "noul", "instructions": "이 요청에 답하려면 여러 단계를 거친 추론이 필요합니까?"},
}


def order_tool(lang):
    return {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": text("order.tool", lang),
            "parameters": {
                "type": "object",
                "properties": {"order_id": {"type": "string", "description": text("order.tool.order_id", lang)}},
                "required": ["order_id"],
            },
        },
    }


# 함수 호출 흐름을 보여 주기 위한 고정 데이터. status와 carrier는 texts.TEXTS의 키이고 조회할 때 요청의 언어로 바꾼다.
ORDERS = {
    "A-1024": {"order_id": "A-1024", "status": "order.in_transit", "carrier": "order.carrier", "eta": "2026-11-16"},
    "A-1025": {"order_id": "A-1025", "status": "order.delivered", "carrier": "order.carrier",
               "delivered_at": "2026-11-12"},
}

sessions = {}  # 세션 ID -> (결정, 만료 시각). 태스크마다 따로 가진다.

# 스트림에서 내용이 담긴 첫 조각을 찾는다. "reasoning_content"와 빈 내용("content":"")은 맞지 않는다.
CONTENT = re.compile(rb'"content":\s?"[^"]')


class Timing:
    """요청 하나의 구간 시각. 구간별 TTFT 측정(bench/ttft)이 요청 ID로 이 로그를 찾는다."""

    def __init__(self):
        self.started = time.monotonic()
        self.first_chunk = None    # 게이트웨이에서 본문의 첫 바이트를 받은 시각
        self.first_content = None  # 내용이 담긴 첫 조각을 클라이언트로 내보낸 시각
        self.size = 0

    def saw(self, chunk):
        now = time.monotonic()
        if self.first_chunk is None:
            self.first_chunk = now
        if self.first_content is None and CONTENT.search(chunk):
            self.first_content = now
        self.size += len(chunk)

    def since_start(self, at):
        return None if at is None else round((at - self.started) * 1000, 1)


def log(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def lookup_order(order_id, lang):
    order = ORDERS.get(order_id, {"order_id": order_id, "status": "order.not_found"})
    return {key: text(value, lang) if key in ("status", "carrier") else value for key, value in order.items()}


# 추론 과정을 한국어로 쓰게 하는 지시문. 2026-11-14에 확인한 바로는 Qwen3.8-27B는 이 문구를 따르고
# (추론의 한글 비율 0.96), Gemma 4 31B는 어떤 문구에도 영어로 추론했다. 첫 문장을 정해 주는 부분을 빼면 Qwen도 따르지 않았다.
THINKING_IN_KOREAN = ("당신의 추론 과정(thinking)은 사용자에게 그대로 보입니다. 추론 과정의 모든 문장을 한국어로만 쓰세요. "
                      "영어 문장은 쓰지 마세요. 추론의 첫 문장을 \"사용자의 질문을 정리하면\"으로 시작하세요.")


def with_instruction(messages, text):
    """시스템 메시지에 지시문을 더한 새 목록을 돌려준다."""
    if messages and messages[0].get("role") == "system" and isinstance(messages[0].get("content"), str):
        return [{**messages[0], "content": messages[0]["content"] + "\n\n" + text}] + messages[1:]
    return [{"role": "system", "content": text}] + messages


def with_korean_thinking(messages):
    """시스템 메시지에 한국어 추론 지시문을 더한 새 목록을 돌려준다."""
    return with_instruction(messages, THINKING_IN_KOREAN)


async def run_tool(call, sources, lang):
    """모델이 부른 도구 하나를 실행한다. (모델에 돌려줄 결과, 화면에 알릴 내용)을 돌려준다.

    sources가 None이면 이 요청에는 웹 검색을 붙이지 않은 것이다.
    """
    name = call["function"]["name"]
    try:
        arguments = json.loads(call["function"]["arguments"] or "{}")
    except ValueError:
        arguments = {}
    if not isinstance(arguments, dict):
        arguments = {}
    if name == "web_search" and sources is not None:
        result, note = await websearch.run(arguments.get("query"), sources, lang)
        # 검색어는 사용자의 글에서 나오므로 로그에는 길이와 건수만 남긴다.
        log("tool_call", name=name, query_chars=len(note["query"]), results=len(result["results"]),
            search_ms=note.get("search_ms"), error=note.get("error"))
        return result, note
    if name == "get_order":
        result = lookup_order(arguments.get("order_id", ""), lang)
        log("tool_call", name=name, arguments=call["function"]["arguments"], result=result)
        return result, {}
    log("tool_call", name=name, error="unknown_tool")
    return {"error": text("tool.unknown", lang, name=name)}, {"error": "unknown_tool"}


def unavailable(detail):
    """Decider가 답하지 못했을 때의 기본 결정. 이유를 함께 남긴다."""
    return replace(routing.FALLBACK, reason={"why": "decider_unavailable", "detail": detail,
                                             "timeout_s": DECIDER_TIMEOUT})


async def ask_decider(http, state):
    try:
        async with http.post(GATEWAY_URL + "/decide", json={"state": state[-2000:], "questions": DECIDER_QUESTIONS},
                             timeout=ClientTimeout(total=DECIDER_TIMEOUT)) as response:
            if response.status != 200:
                return unavailable(f"status {response.status}")
            return routing.from_decider((await response.json())["answers"], DECIDER_MIN_CONFIDENCE)
    except asyncio.TimeoutError:
        return unavailable("timeout")
    except (ClientError, ValueError, KeyError):
        return unavailable("error")


async def decide(http, session_id, messages, task, priority, eval_model=None):
    # 성능 평가 요청은 세션과 Decider를 거치지 않는다.
    if eval_model:
        return routing.for_evaluation(messages, eval_model), False
    now = time.monotonic()
    cached = sessions.get(session_id)
    if cached and cached[1] > now:
        decision = cached[0]
        # 형식이 정해진 민감 정보는 세션에 결정이 있어도 메시지마다 확인한다.
        pattern = None if decision.sensitive else routing.sensitive_kind(routing.message_text(messages))
        if pattern:
            decision = routing.with_sensitive(decision, pattern)
            sessions[session_id] = (decision, now + SESSION_TTL)
        return decision, True
    decision = routing.decide_without_decider(messages, task, priority)
    if decision is None:
        decision = await ask_decider(http, routing.message_text(messages[-1:]))
    if session_id:
        if len(sessions) >= 10000:
            for key in [k for k, (_, expiry) in sessions.items() if expiry <= now] or list(sessions)[:1000]:
                del sessions[key]
        sessions[session_id] = (decision, now + SESSION_TTL)
    return decision, False


async def wake_qwen(http, lang):
    async with http.post(WAKE_API_URL + "/wake", timeout=ClientTimeout(total=60)) as response:
        body = await response.json()
        if response.status != 200:
            failure = {"error": {"message": text("wake.failed", lang), "detail": body}}
            raise web.HTTPBadGateway(text=json.dumps(failure), content_type="application/json")
        return body.get("was_sleeping", False)


async def open_upstream(http, body, headers, retry_503_until):
    """게이트웨이에 요청을 보내고 응답 객체를 돌려준다. 깨운 직후의 503은 잠깐 다시 시도한다."""
    while True:
        response = await http.post(GATEWAY_URL + "/v1/chat/completions", json=body, headers=headers,
                                   timeout=ClientTimeout(total=None, sock_connect=5))
        if response.status == 503 and time.monotonic() < retry_503_until:
            response.release()
            await asyncio.sleep(0.2)
            continue
        return response


async def relay_raw(request, upstream, extra_headers, timing):
    """받은 바이트를 그대로 흘려보낸다."""
    response = web.StreamResponse(status=upstream.status, headers=extra_headers)
    response.content_type = upstream.content_type
    if upstream.content_type == "text/event-stream":
        response.headers["Cache-Control"] = "no-cache"
    await response.prepare(request)
    async for chunk in upstream.content.iter_any():
        await response.write(chunk)
        timing.saw(chunk)
    await response.write_eof()
    return response


async def relay_with_tools(request, http, upstream, body, headers, extra_headers, timing, sources, lang):
    """도구를 붙인 요청의 스트림. 내용은 그대로 흘려보내고, 모델이 도구를 부르면 실행해서 이어서 묻는다."""
    response = web.StreamResponse(status=200, headers={**extra_headers, "Cache-Control": "no-cache"})
    response.content_type = "text/event-stream"
    await response.prepare(request)
    for round_number in range(MAX_TOOL_ROUNDS + 1):
        calls = {}
        finish = None
        forwarded = False  # 직전 data 줄을 내보냈는지. 삼킨 이벤트의 빈 줄은 내보내지 않는다.
        async for line in upstream.content:
            text = line.decode("utf-8", "replace").strip()
            if not text:
                if forwarded:
                    await response.write(line)
                continue
            if not text.startswith("data: ") or text == "data: [DONE]":
                forwarded = finish != "tool_calls"
                if forwarded:
                    await response.write(line)
                continue
            choice = (json.loads(text[6:]).get("choices") or [{}])[0]
            for call in choice.get("delta", {}).get("tool_calls") or []:
                slot = calls.setdefault(call.get("index", 0), {"id": "", "name": "", "arguments": ""})
                slot["id"] = call.get("id") or slot["id"]
                slot["name"] = call.get("function", {}).get("name") or slot["name"]
                slot["arguments"] += call.get("function", {}).get("arguments") or ""
            finish = choice.get("finish_reason") or finish
            forwarded = not calls and finish != "tool_calls"
            if forwarded:
                await response.write(line)
                timing.saw(line)
        upstream.release()
        if finish != "tool_calls" or round_number == MAX_TOOL_ROUNDS:
            break
        tool_calls = [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": c["arguments"]}}
                      for c in calls.values()]
        body["messages"] = body["messages"] + [{"role": "assistant", "content": None, "tool_calls": tool_calls}]
        for call in tool_calls:
            result, detail = await run_tool(call, sources, lang)
            # SSE 주석 줄(":"로 시작)로 도구 호출을 알린다. OpenAI 형식의 클라이언트는 주석을 무시하고,
            # 확인용 페이지는 이 줄로 흐름 그림에 도구 호출 단계를 표시하고 웹 검색의 출처 목록을 만든다.
            note = {"event": "tool_call", "name": call["function"]["name"],
                    "ms": timing.since_start(time.monotonic()), **detail}
            await response.write((": bff " + json.dumps(note) + "\n\n").encode())
            body["messages"].append({"role": "tool", "tool_call_id": call["id"],
                                     "content": json.dumps(result, ensure_ascii=False)})
        if round_number == MAX_TOOL_ROUNDS - 1:
            body["tool_choice"] = "none"  # 도구를 더 부르지 않고 지금까지의 결과로 답하게 한다
        upstream = await open_upstream(http, body, headers, 0)
    await response.write_eof()
    return response


async def chat(request):
    timing = Timing()
    started = timing.started
    received_at = round(time.time() * 1000)
    http = request.app["http"]
    lang = language(request.headers)  # 화면의 한영 전환이 x-lang으로 보낸다. BFF가 만드는 문구의 언어를 정한다.
    try:
        body = await request.json()
        messages = body["messages"]
    except (ValueError, KeyError):
        return web.json_response({"error": {"message": text("request.messages_required", lang)}}, status=400)
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    session_id = request.headers.get("x-session-id", "")
    task = request.headers.get("x-task", "")
    priority = request.headers.get("x-priority") if request.headers.get("x-priority") in PRIORITY else None

    eval_model = request.headers.get("x-eval-model", "")
    if eval_model and eval_model not in routing.MODELS:
        return web.json_response({"error": {"message": text("request.bad_eval_model", lang)}}, status=400)

    decision, cached = await decide(http, session_id, messages, task, priority, eval_model)
    decided = time.monotonic()
    if decision.sensitive and routing.has_image(messages):
        return web.json_response({"error": {"message": text("request.sensitive_image", lang)}}, status=422)

    body["model"] = decision.model_name
    body["priority"] = PRIORITY[decision.priority]
    body.setdefault("chat_template_kwargs", {}).setdefault("enable_thinking", decision.thinking)
    # 평가 요청은 두 모델의 조건을 맞춘다: thinking을 끄고 주문 조회 도구를 넣지 않는다.
    if decision.source == "eval":
        body["chat_template_kwargs"]["enable_thinking"] = False
    elif body["chat_template_kwargs"]["enable_thinking"] and request.headers.get("x-thinking-language") == "ko":
        body["messages"] = with_korean_thinking(messages)
    # BFF가 실행하는 도구: 상담 업무의 주문 조회, 그리고 요청이 켰을 때의 웹 검색.
    # 민감 정보가 있는 요청은 검색어가 리전 밖으로 나가지 않도록 웹 검색을 붙이지 않는다.
    # 모델을 정하지 못해 기본값으로 보낸 요청(fallback)도 민감 정보 요청으로 다뤄 붙이지 않는다.
    # 민감 정보가 있어서가 아니므로 화면이 이유를 구분하도록 값만 따로 알린다.
    managed = "tools" not in body and decision.source != "eval"
    wants_search = request.headers.get("x-web-search") == "on"
    search = ("off" if not wants_search else "disabled" if not websearch.enabled() else
              "fallback" if decision.source == "fallback" else
              "sensitive" if decision.sensitive else "on" if managed else "off")
    sources = websearch.Sources() if search == "on" else None
    tools = (([order_tool(lang)] if managed and task == "support" else [])
             + ([websearch.tool(lang)] if sources is not None else []))
    use_tools = bool(tools)
    if use_tools:
        body["tools"] = tools
    if sources is not None:
        body["messages"] = with_instruction(body["messages"], websearch.instruction(lang))
    headers = {"x-llm-d-inference-objective": decision.objective, "x-request-id": request_id}

    retry_until = 0
    if decision.model == "qwen" and await wake_qwen(http, lang):
        retry_until = time.monotonic() + WAKE_RETRY_SECONDS
    woke = time.monotonic()

    upstream = await open_upstream(http, body, headers, retry_until)
    decide_ms = round((decided - started) * 1000, 1)
    wake_ms = round((woke - decided) * 1000, 1)
    upstream_headers_ms = round((time.monotonic() - woke) * 1000, 1)
    # x-bff-reason은 이렇게 정한 근거, x-bff-timing은 BFF 안에서 구간마다 걸린 시간이다. 화면의 흐름 그림이 이 값을 쓴다.
    # 헤더 값이라서 ASCII로만 쓴다(json.dumps의 기본 동작).
    extra = {"x-request-id": request_id, "x-bff-model": decision.model_name, "x-bff-decision": decision.source,
             "x-bff-sensitive": str(decision.sensitive).lower(),
             "x-bff-thinking": str(decision.thinking).lower(),
             # on: 검색 도구를 붙임, off: 요청하지 않음, sensitive: 민감 정보라 붙이지 않음, disabled: 설정되지 않음
             "x-bff-search": search,
             "x-bff-reason": json.dumps({**decision.reason, "cached": cached}, separators=(",", ":")),
             "x-bff-timing": json.dumps({"decide_ms": decide_ms, "wake_ms": wake_ms, "upstream_ms": upstream_headers_ms,
                                         "woke": retry_until > 0, "tools": use_tools}, separators=(",", ":"))}
    # trace_id는 ALB가 붙인 X-Amzn-Trace-Id다. ALB 접근 로그의 같은 요청과 이 값으로 잇는다.
    log("chat", request_id=request_id, trace_id=request.headers.get("X-Amzn-Trace-Id", ""), received_at=received_at,
        user=request.get("user"), session=session_id, task=task, model=decision.model_name,
        objective=decision.objective, thinking=decision.thinking, sensitive=decision.sensitive, source=decision.source,
        reason=decision.reason,
        cached=cached, stream=bool(body.get("stream")), search=search, upstream_status=upstream.status,
        decide_ms=decide_ms, wake_ms=wake_ms, upstream_headers_ms=upstream_headers_ms)

    def finished():
        log("chat_end", request_id=request_id, first_chunk_ms=timing.since_start(timing.first_chunk),
            first_content_ms=timing.since_start(timing.first_content), bytes=timing.size,
            total_ms=timing.since_start(time.monotonic()))

    if use_tools and body.get("stream") and upstream.status == 200:
        try:
            return await relay_with_tools(request, http, upstream, body, headers, extra, timing, sources, lang)
        finally:
            finished()
    if use_tools and upstream.status == 200:
        result = await upstream.json()
        for round_number in range(MAX_TOOL_ROUNDS):
            message = result["choices"][0]["message"]
            if not message.get("tool_calls"):
                break
            body["messages"] = body["messages"] + [message]
            for call in message["tool_calls"]:
                found, _ = await run_tool(call, sources, lang)
                body["messages"].append({"role": "tool", "tool_call_id": call["id"],
                                         "content": json.dumps(found, ensure_ascii=False)})
            if round_number == MAX_TOOL_ROUNDS - 1:
                body["tool_choice"] = "none"
            async with await open_upstream(http, body, headers, 0) as again:
                result = await again.json()
        # 스트리밍이 아닌 응답에는 출처 목록을 본문에 함께 넣는다. OpenAI 형식의 클라이언트는 모르는 키를 무시한다.
        if sources is not None and sources.items:
            result["bff_sources"] = sources.items
        finished()
        return web.json_response(result, headers=extra)
    try:
        return await relay_raw(request, upstream, extra, timing)
    finally:
        finished()


async def route_only(request):
    """모델을 부르지 않고 결정만 돌려준다. 화면의 "경로 판단"이 쓴다. 세션에는 저장하지 않는다."""
    http = request.app["http"]
    try:
        messages = (await request.json())["messages"]
    except (ValueError, KeyError):
        message = text("request.messages_required", language(request.headers))
        return web.json_response({"error": {"message": message}}, status=400)
    task = request.headers.get("x-task", "")
    started = time.monotonic()
    decision, _ = await decide(http, "", messages, task, None)
    return web.json_response({
        "model": decision.model_name, "decision": decision.source, "reason": decision.reason,
        "sensitive": decision.sensitive, "thinking": decision.thinking, "objective": decision.objective,
        "rejected": decision.sensitive and routing.has_image(messages),
        "decide_ms": round((time.monotonic() - started) * 1000, 1),
    })


async def probe(http, name, method, path, **kwargs):
    """게이트웨이 뒤의 구성 요소 하나가 응답하는지 본다."""
    started = time.monotonic()
    try:
        async with http.request(method, GATEWAY_URL + path, timeout=ClientTimeout(total=3), **kwargs) as response:
            body = await response.json(content_type=None) if response.status == 200 else None
            return name, {"ok": response.status == 200, "status": response.status,
                          "ms": round((time.monotonic() - started) * 1000, 1), "body": body}
    except (ClientError, asyncio.TimeoutError, ValueError) as error:
        return name, {"ok": False, "status": None, "ms": round((time.monotonic() - started) * 1000, 1),
                      "error": type(error).__name__}


async def status(request):
    """두 모델과 Decider의 응답 여부. 잠든 Qwen은 Service에서 빠져 있어 응답하지 않는 것으로 나온다."""
    http = request.app["http"]
    question = {"route": DECIDER_QUESTIONS["route"]}
    results = dict(await asyncio.gather(
        probe(http, "gemma", "GET", "/v1/models", headers={"x-model": routing.MODELS["gemma"]}),
        probe(http, "qwen", "GET", "/v1/models", headers={"x-model": routing.MODELS["qwen"]}),
        probe(http, "decider", "POST", "/decide", json={"state": "상태 확인", "questions": question}),
    ))
    for name in ("gemma", "qwen"):
        body = results[name].pop("body", None)
        served = (body or {}).get("data") or [{}]
        results[name]["model"] = served[0].get("id")
        results[name]["max_model_len"] = served[0].get("max_model_len")
    results["decider"].pop("body", None)
    return web.json_response({"components": results, "checked_at": round(time.time() * 1000)})


async def mock_order(request):
    return web.json_response(lookup_order(request.match_info["order_id"], language(request.headers)))


async def healthz(request):
    return web.json_response({"status": "ok"})


@web.middleware
async def require_login(request, handler):
    """/healthz(ALB 상태 확인)를 뺀 모든 경로에서 Cognito 액세스 토큰을 요구한다."""
    if request.path == "/healthz":
        return await handler(request)
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    try:
        if scheme.lower() != "bearer" or not token:
            raise auth.AuthError("auth.login_required")
        claims = await request.app["verifier"].verify(request.app["http"], token.strip())
    except auth.AuthError as error:
        # 로그에는 언어와 무관한 키를 남기고, 응답 본문은 요청의 언어로 쓴다.
        log("auth_rejected", path=request.path, reason=str(error))
        message = text(str(error), language(request.headers))
        return web.json_response({"error": {"message": message}}, status=401, headers={"WWW-Authenticate": "Bearer"})
    request["user"] = claims.get("sub")
    return await handler(request)


async def on_startup(app):
    app["http"] = ClientSession()


async def on_cleanup(app):
    await app["http"].close()


def create_app(verifier):
    app = web.Application(client_max_size=20 * 1024 * 1024, middlewares=[require_login])
    app["verifier"] = verifier
    app.add_routes([
        web.post("/v1/chat/completions", chat),
        web.post("/v1/route", route_only),
        web.get("/v1/status", status),
        web.get("/mock/orders/{order_id}", mock_order),
        web.get("/healthz", healthz),
    ])
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    # 인증 설정이 없으면 뜨지 않는다. 인증 없이 열리는 경로를 두지 않기 위해서다.
    verifier = auth.CognitoVerifier(os.environ["COGNITO_ISSUER"], os.environ["COGNITO_CLIENT_ID"])
    web.run_app(create_app(verifier), port=int(os.environ.get("PORT", "8080")), access_log=None)
