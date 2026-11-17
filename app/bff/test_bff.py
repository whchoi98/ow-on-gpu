"""BFF 시험. 게이트웨이와 깨우기 API를 대신하는 서버를 같은 프로세스에 띄워 실제 HTTP로 확인한다.

  python -m unittest test_bff -v
"""
import asyncio
import base64
import datetime
import hashlib
import hmac
import json
import os
import time
import unittest

import jwt
from aiohttp import ClientSession, web
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

os.environ["GATEWAY_URL"] = "http://127.0.0.1:18101"
os.environ["WAKE_API_URL"] = "http://127.0.0.1:18102"
os.environ["WAKE_RETRY_SECONDS"] = "3"
os.environ["WEB_SEARCH_REGION"] = "test-region"  # 실제 검색은 하지 않는다. websearch.invoke를 바꿔 끼운다.

import auth  # noqa: E402
import bff  # noqa: E402
import routing  # noqa: E402
import texts  # noqa: E402
import websearch  # noqa: E402

CHUNK_GAP = 0.15
BFF_URL = "http://127.0.0.1:18100"
# Cognito 사용자 풀의 대역. 시험용 키로 서명하고 같은 프로세스에서 JWKS를 내준다.
ISSUER = "http://127.0.0.1:18103/pool"
CLIENT_ID = "test-client"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def claims(**overrides):
    return {"iss": ISSUER, "client_id": CLIENT_ID, "token_use": "access", "sub": "user-1",
            "exp": int(time.time()) + 300, **overrides}


def token(key=KEY, kid="k1", **overrides):
    return jwt.encode(claims(**overrides), key, algorithm="RS256", headers={"kid": kid})


def b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def unsigned_token():
    head = b64url(json.dumps({"alg": "none", "typ": "JWT", "kid": "k1"}).encode())
    return (head + b"." + b64url(json.dumps(claims()).encode()) + b".").decode()


def hs256_token_signed_with_public_key():
    """공개 키를 HMAC 비밀로 쓴 토큰. 검증기가 머리말의 alg를 믿으면 통과한다."""
    pem = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    signing = b64url(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "k1"}).encode()) + b"." + \
        b64url(json.dumps(claims()).encode())
    return (signing + b"." + b64url(hmac.new(pem, signing, hashlib.sha256).digest())).decode()


class Stub:
    """게이트웨이(/decide, /v1/chat/completions)와 깨우기 API(/wake)의 대역."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.chats, self.decides, self.wakes, self.jwks_fetches = [], 0, 0, 0
        self.sleeping = False
        self.unavailable_until = 0

    async def jwks(self, request):
        self.jwks_fetches += 1
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key())
        jwk = json.loads(jwk) if isinstance(jwk, str) else jwk
        return web.json_response({"keys": [{**jwk, "kid": "k1", "use": "sig", "alg": "RS256"}]})

    async def decide(self, request):
        self.decides += 1
        state = (await request.json())["state"]
        if "장애" in state:
            return web.Response(status=500)
        route = {"choice": "qwen" if "코드" in state else "gemma", "confidence": 0.3 if "애매" in state else 0.9}
        return web.json_response({"answers": {
            "route": {"type": "choice", **route},
            "policy": {"type": "noul", "noul": 0.95 if "제 이름은" in state else 0.5 if "모호" in state else 0.05},
            "thinking": {"type": "noul", "noul": 0.9 if "코드" in state else 0.1},
        }})

    async def models(self, request):
        name = request.headers.get("x-model")
        if name == "qwen38-27b" and self.sleeping:  # 잠든 파드는 Service에서 빠져 게이트웨이가 503을 준다
            return web.json_response({"error": "no endpoint"}, status=503)
        return web.json_response({"data": [{"id": name, "max_model_len": 16384 if name.startswith("gemma") else 32768}]})

    async def wake(self, request):
        self.wakes += 1
        was = self.sleeping
        if was:
            self.sleeping = False
            self.unavailable_until = time.monotonic() + 0.5
        return web.json_response({"was_sleeping": was, "awake": True})

    async def chat(self, request):
        body = await request.json()
        self.chats.append({"body": body, "headers": dict(request.headers)})
        if body["model"] == "qwen38-27b" and (self.sleeping or time.monotonic() < self.unavailable_until):
            return web.json_response({"error": {"message": "no endpoint"}}, status=503)
        names = [tool["function"]["name"] for tool in body.get("tools") or []]
        last = body["messages"][-1]
        # 모델의 대역: 주문을 물으면 get_order를, "검색"이 들어 있으면 web_search를 부른다.
        # "끝없이"가 있으면 도구 결과를 받고도 계속 검색하려 한다(tool_choice가 none이면 멈춘다).
        if "get_order" in names and last["role"] == "user" and "주문" in str(last):
            name, arguments = "get_order", ['{"order_id": ', '"A-1024"}']
        elif "web_search" in names and body.get("tool_choice") != "none" and (
                (last["role"] == "user" and "검색" in str(last)) or "끝없이" in str(body["messages"])):
            name, arguments = "web_search", ['{"query": ', '"서울 날씨"}']
        else:
            name = None
        if not body.get("stream"):
            if name:
                message = {"role": "assistant", "content": None, "tool_calls": [
                    {"id": "call_1", "type": "function", "function": {"name": name, "arguments": "".join(arguments)}}]}
            else:
                message = {"role": "assistant", "content": "답변입니다"}
            return web.json_response({"model": body["model"], "choices": [{"message": message, "finish_reason": "stop"}]})
        response = web.StreamResponse(headers={"Content-Type": "text/event-stream"})
        await response.prepare(request)
        if name:
            deltas = [{"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": name, "arguments": ""}}]}] + \
                     [{"tool_calls": [{"index": 0, "function": {"arguments": part}}]} for part in arguments]
            finish = "tool_calls"
        else:
            deltas = [{"content": "하나"}, {"content": "둘"}, {"content": "셋"}]
            finish = "stop"
        for delta in deltas:
            await response.write(f"data: {json.dumps({'choices': [{'delta': delta}]}, ensure_ascii=False)}\n\n".encode())
            await asyncio.sleep(CHUNK_GAP)
        await response.write(f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': finish}]})}\n\n".encode())
        await response.write(b"data: [DONE]\n\n")
        return response


def user(text):
    return {"messages": [{"role": "user", "content": text}]}


class RoutingRules(unittest.TestCase):
    def test_sensitive_formats(self):
        self.assertTrue(routing.has_sensitive("주민번호는 900101-1234567입니다"))
        self.assertTrue(routing.has_sensitive("9001011234567"))
        self.assertTrue(routing.has_sensitive("카드 4111 1111 1111 1111로 결제"))
        self.assertTrue(routing.has_sensitive("4111-1111-1111-1111"))
        self.assertFalse(routing.has_sensitive("카드 4111 1111 1111 1112"))  # Luhn 불일치
        self.assertFalse(routing.has_sensitive("전화는 010-1234-5678, 주문 번호는 A-1024"))
        self.assertFalse(routing.has_sensitive("2026-11-14 10:35:46에 주문"))

    def test_decider_confidence(self):
        ok = {"route": {"choice": "qwen", "confidence": 0.9}, "policy": {"noul": 0.05}, "thinking": {"noul": 0.8}}
        self.assertEqual(routing.from_decider(ok, 0.6), routing.Decision("qwen", "interactive", True, False, "decider"))
        # 모델 선택만 불확실하면 기본 모델로 보내되, 개인정보가 없다는 판단은 그대로 쓴다.
        low_route = {**ok, "route": {"choice": "qwen", "confidence": 0.5}}
        self.assertEqual(routing.from_decider(low_route, 0.6),
                         routing.Decision("gemma", "interactive", False, False, "fallback"))
        self.assertEqual(routing.from_decider({**low_route, "policy": {"noul": 0.95}}, 0.6), routing.FALLBACK)
        low_policy = {**ok, "policy": {"noul": 0.6}}  # 0.5에서 0.1 떨어져 신뢰도 0.2
        self.assertEqual(routing.from_decider(low_policy, 0.6), routing.FALLBACK)
        self.assertEqual(routing.from_decider({**low_route, "policy": {"noul": 0.6}}, 0.6), routing.FALLBACK)
        pii = {**ok, "policy": {"noul": 0.95}}
        self.assertEqual(routing.from_decider(pii, 0.6).model, "gemma")
        self.assertEqual(routing.from_decider({}, 0.6), routing.FALLBACK)


class BffHttp(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stub = Stub()
        bff.sessions.clear()
        gateway = web.Application()
        gateway.add_routes([web.post("/decide", self.stub.decide), web.post("/v1/chat/completions", self.stub.chat),
                            web.get("/v1/models", self.stub.models)])
        wake = web.Application()
        wake.add_routes([web.post("/wake", self.stub.wake)])
        cognito = web.Application()
        cognito.add_routes([web.get("/pool/.well-known/jwks.json", self.stub.jwks)])
        self.runners = []
        for app, port in ((gateway, 18101), (wake, 18102), (cognito, 18103),
                          (bff.create_app(auth.CognitoVerifier(ISSUER, CLIENT_ID)), 18100)):
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "127.0.0.1", port).start()
            self.runners.append(runner)
        # 기존 시험은 로그인한 사용자로 보낸다. 인증 시험만 토큰 없는 세션(anon)을 쓴다.
        self.http = ClientSession(headers={"Authorization": "Bearer " + token()})
        self.anon = ClientSession()

    async def asyncTearDown(self):
        await self.http.close()
        await self.anon.close()
        for runner in self.runners:
            await runner.cleanup()

    async def post(self, body, **headers):
        async with self.http.post("http://127.0.0.1:18100/v1/chat/completions", json=body, headers=headers) as r:
            return r.status, dict(r.headers), await r.read()

    async def test_task_sets_model_objective_and_priority(self):
        status, headers, _ = await self.post(user("환불 규정이 궁금해요"), **{"x-task": "support"})
        sent = self.stub.chats[-1]
        self.assertEqual((status, sent["body"]["model"], sent["body"]["priority"]), (200, "gemma-4-31b", 0))
        self.assertEqual(sent["headers"]["x-llm-d-inference-objective"], "gemma-interactive")
        self.assertEqual(sent["body"]["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(headers["x-bff-model"], "gemma-4-31b")
        await self.post(user("이 문장을 번역해 주세요"), **{"x-task": "translate"})
        sent = self.stub.chats[-1]
        self.assertEqual((sent["body"]["priority"], sent["headers"]["x-llm-d-inference-objective"]), (10, "gemma-batch"))
        self.assertEqual(self.stub.decides, 0)

    async def test_sensitive_rule_wins_over_task_and_skips_decider(self):
        _, headers, _ = await self.post(user("코드 고쳐 주세요. 주민번호 900101-1234567"), **{"x-task": "coding"})
        self.assertEqual(self.stub.chats[-1]["body"]["model"], "gemma-4-31b")
        self.assertEqual((headers["x-bff-decision"], headers["x-bff-sensitive"]), ("rule", "true"))
        self.assertEqual((self.stub.decides, self.stub.wakes), (0, 0))

    async def test_image_goes_to_qwen_after_wake_call(self):
        body = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "색상을 알려 주세요"}, {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}}]}]}
        await self.post(body)
        self.assertEqual((self.stub.chats[-1]["body"]["model"], self.stub.wakes), ("qwen38-27b", 1))

    async def test_sensitive_image_is_rejected(self):
        body = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "카드 4111 1111 1111 1111"}, {"type": "image_url", "image_url": {"url": "x"}}]}]}
        status, _, _ = await self.post(body)
        self.assertEqual((status, len(self.stub.chats)), (422, 0))

    async def test_decider_used_once_per_session(self):
        _, headers, _ = await self.post(user("이 코드에서 버그를 찾아 주세요"), **{"x-session-id": "s1"})
        sent = self.stub.chats[-1]["body"]
        self.assertEqual((sent["model"], sent["chat_template_kwargs"]["enable_thinking"]), ("qwen38-27b", True))
        self.assertEqual(headers["x-bff-decision"], "decider")
        await self.post(user("고맙습니다"), **{"x-session-id": "s1"})
        self.assertEqual((self.stub.decides, self.stub.chats[-1]["body"]["model"]), (1, "qwen38-27b"))
        # 같은 세션에서 민감 정보가 나오면 그 뒤로는 Gemma
        await self.post(user("제 주민번호는 900101-1234567"), **{"x-session-id": "s1"})
        self.assertEqual(self.stub.chats[-1]["body"]["model"], "gemma-4-31b")
        await self.post(user("다음 질문"), **{"x-session-id": "s1"})
        self.assertEqual((self.stub.decides, self.stub.chats[-1]["body"]["model"]), (1, "gemma-4-31b"))

    async def test_decider_low_confidence_or_failure_falls_back(self):
        # 애매: 모델 선택의 신뢰도만 낮음. 모호: 개인정보 판단의 신뢰도가 낮음. 장애: Decider가 답하지 않음.
        for text, sensitive in (("애매한 요청", "false"), ("모호한 요청", "true"), ("애매하고 모호한 요청", "true"),
                                ("장애 상황", "true")):
            _, headers, _ = await self.post(user(text))
            sent = self.stub.chats[-1]["body"]
            self.assertEqual((sent["model"], sent["chat_template_kwargs"]["enable_thinking"]), ("gemma-4-31b", False))
            self.assertEqual((headers["x-bff-decision"], headers["x-bff-sensitive"]), ("fallback", sensitive), text)

    async def test_decider_policy_sends_personal_data_to_gemma(self):
        await self.post(user("제 이름은 홍길동이고 코드 좀 봐 주세요"))
        self.assertEqual(self.stub.chats[-1]["body"]["model"], "gemma-4-31b")

    async def test_sleeping_qwen_is_woken_and_503_retried(self):
        self.stub.sleeping = True
        status, _, _ = await self.post(user("함수를 고쳐 주세요"), **{"x-task": "coding"})
        self.assertEqual((status, self.stub.wakes), (200, 1))
        self.assertGreater(len(self.stub.chats), 1)  # 503을 받고 다시 보냄

    async def test_stream_is_relayed_chunk_by_chunk(self):
        arrivals, data = [], b""
        async with self.http.post("http://127.0.0.1:18100/v1/chat/completions",
                                  json={**user("안녕하세요"), "stream": True}, headers={"x-task": "translate"}) as r:
            self.assertEqual(r.headers["Content-Type"], "text/event-stream")
            async for chunk in r.content.iter_any():
                arrivals.append(time.monotonic())
                data += chunk
        self.assertIn("하나", data.decode())
        self.assertTrue(data.decode().rstrip().endswith("data: [DONE]"))
        gaps = [b - a for a, b in zip(arrivals, arrivals[1:])]
        # 모아서 보냈다면 간격 없이 한 번에 도착한다.
        self.assertGreaterEqual(len(arrivals), 3)
        self.assertGreaterEqual(sum(1 for g in gaps if g > CHUNK_GAP * 0.6), 2)

    async def test_support_tool_call_flow_streaming(self):
        _, _, data = await self.post({**user("주문 A-1024 어디쯤인가요"), "stream": True}, **{"x-task": "support"})
        text = data.decode()
        self.assertNotIn("tool_calls", text)
        # 삼킨 도구 호출 이벤트의 빈 줄이 앞에 남지 않는다. 맨 앞은 도구 호출을 알리는 주석 줄이고 그 뒤가 data다.
        first, second = text.split("\n\n")[:2]
        self.assertTrue(first.startswith(": bff ") and json.loads(first[6:])["name"] == "get_order")
        self.assertTrue(second.startswith("data: "))
        self.assertIn("하나", text)
        self.assertEqual(text.count("[DONE]"), 1)
        second = self.stub.chats[-1]["body"]["messages"]
        self.assertEqual(second[-1]["role"], "tool")
        self.assertIn("배송 중", second[-1]["content"])

    async def test_support_tool_call_flow_non_streaming(self):
        status, _, data = await self.post(user("주문 A-1024 어디쯤인가요"), **{"x-task": "support"})
        self.assertEqual((status, json.loads(data)["choices"][0]["message"]["content"]), (200, "답변입니다"))
        self.assertEqual(self.stub.chats[-1]["body"]["messages"][-1]["role"], "tool")

    def search_with(self, results=None, error=None):
        """websearch.invoke를 대역으로 바꾸고, 받은 검색어 목록을 돌려준다."""
        queries = []

        def fake(query):
            queries.append(query)
            if error:
                raise error
            return results if results is not None else [
                {"title": "서울 주간 예보", "url": "https://weather.example/seoul", "text": "이번 주 서울은 맑습니다. " * 200,
                 "publishedAt": datetime.datetime(2026, 11, 14, 9, 0, tzinfo=datetime.timezone.utc)},
                {"title": "주소 없는 결과", "text": "출처를 표시할 수 없는 결과"},
                {"url": "https://news.example/a", "text": "제목과 날짜가 없는 결과"},
            ]

        original = websearch.invoke
        websearch.invoke = fake
        self.addCleanup(setattr, websearch, "invoke", original)
        return queries

    def notes(self, data):
        return [json.loads(block[6:]) for block in data.decode().split("\n\n") if block.startswith(": bff ")]

    async def test_web_search_tool_flow_streaming(self):
        queries = self.search_with()
        _, headers, data = await self.post({**user("이번 주 서울 날씨를 검색해 주세요"), "stream": True},
                                           **{"x-task": "translate", "x-web-search": "on"})
        self.assertEqual(headers["x-bff-search"], "on")
        self.assertEqual(queries, ["서울 날씨"])
        first, second = self.stub.chats[-2]["body"], self.stub.chats[-1]["body"]
        self.assertEqual([tool["function"]["name"] for tool in first["tools"]], ["web_search"])
        # 모델은 오늘 날짜를 모른다. 검색 지시문과 함께 시스템 메시지로 알려 준다.
        self.assertEqual(first["messages"][0]["role"], "system")
        self.assertRegex(first["messages"][0]["content"], r"오늘은 \d{4}-\d{2}-\d{2}")
        # 주소가 없는 결과는 출처를 표시할 수 없어 뺀다. 본문은 정한 길이로 자른다.
        found = json.loads(second["messages"][-1]["content"])
        self.assertEqual([(r["n"], r["url"]) for r in found["results"]],
                         [(1, "https://weather.example/seoul"), (2, "https://news.example/a")])
        self.assertEqual(len(found["results"][0]["text"]), websearch.TEXT_CHARS)
        # 화면은 주석 줄의 출처로 목록을 만든다. 본문은 화면에 보내지 않는다.
        note, = self.notes(data)
        self.assertEqual((note["name"], note["query"]), ("web_search", "서울 날씨"))
        self.assertEqual(note["sources"], [
            {"n": 1, "title": "서울 주간 예보", "url": "https://weather.example/seoul", "published_at": "2026-11-14"},
            {"n": 2, "title": "https://news.example/a", "url": "https://news.example/a", "published_at": None}])
        self.assertIn("하나", data.decode())
        self.assertNotIn("tool_calls", data.decode())

    async def test_web_search_is_attached_only_when_the_request_asks(self):
        queries = self.search_with()
        _, headers, _ = await self.post(user("이번 주 서울 날씨를 검색해 주세요"), **{"x-task": "translate"})
        self.assertEqual(headers["x-bff-search"], "off")
        self.assertNotIn("tools", self.stub.chats[-1]["body"])
        # 상담 업무에 검색을 켜면 주문 조회와 함께 붙는다.
        await self.post(user("안녕하세요"), **{"x-task": "support", "x-web-search": "on"})
        self.assertEqual([tool["function"]["name"] for tool in self.stub.chats[-1]["body"]["tools"]],
                         ["get_order", "web_search"])
        # 성능 평가 요청은 두 모델의 조건을 맞추려고 도구를 붙이지 않는다.
        _, headers, _ = await self.post(user("검색해 주세요"), **{"x-eval-model": "gemma", "x-web-search": "on"})
        self.assertEqual(headers["x-bff-search"], "off")
        self.assertNotIn("tools", self.stub.chats[-1]["body"])
        self.assertEqual(queries, [])

    async def test_web_search_is_not_attached_to_sensitive_requests(self):
        queries = self.search_with()
        _, headers, _ = await self.post(user("900101-1234567 이 사람을 검색해 주세요"), **{"x-web-search": "on"})
        self.assertEqual((headers["x-bff-search"], headers["x-bff-sensitive"]), ("sensitive", "true"))
        self.assertNotIn("tools", self.stub.chats[-1]["body"])
        self.assertEqual(queries, [])

    async def test_web_search_runs_when_only_the_model_choice_is_uncertain(self):
        """모델 선택만 불확실하고 개인정보가 없다는 판단이 기준 이상이면 기본 모델(Gemma)에 검색 도구를 붙인다."""
        queries = self.search_with()
        _, headers, data = await self.post({**user("애매한 검색 요청"), "stream": True}, **{"x-web-search": "on"})
        self.assertEqual((headers["x-bff-search"], headers["x-bff-decision"], headers["x-bff-sensitive"]),
                         ("on", "fallback", "false"))
        self.assertEqual(self.stub.chats[0]["body"]["model"], "gemma-4-31b")
        self.assertEqual(queries, ["서울 날씨"])
        self.assertEqual(len(self.notes(data)[0]["sources"]), 2)

    async def test_web_search_on_a_fallback_request_is_reported_as_fallback(self):
        """개인정보가 없다는 판단을 얻지 못한 요청은 민감 정보 요청과 똑같이 다루되, 화면이 이유를 구분하도록 값만 다르게 알린다."""
        queries = self.search_with()
        for text in ("모호한 검색 요청", "애매하고 모호한 검색 요청", "장애 상황 검색"):
            _, headers, _ = await self.post(user(text), **{"x-web-search": "on"})
            self.assertEqual((headers["x-bff-search"], headers["x-bff-decision"], headers["x-bff-sensitive"]),
                             ("fallback", "fallback", "true"), text)
            self.assertEqual(self.stub.chats[-1]["body"]["model"], "gemma-4-31b")
            self.assertNotIn("tools", self.stub.chats[-1]["body"])
        # 검색을 켜지 않은 요청은 기본값으로 보냈어도 off다.
        _, headers, _ = await self.post(user("모호한 요청"))
        self.assertEqual((headers["x-bff-search"], headers["x-bff-decision"]), ("off", "fallback"))
        self.assertEqual(queries, [])

    async def test_web_search_failure_is_told_to_the_model_and_the_page(self):
        self.search_with(error=RuntimeError("AccessDeniedException"))
        status, _, data = await self.post({**user("검색해 주세요"), "stream": True},
                                          **{"x-task": "translate", "x-web-search": "on"})
        note, = self.notes(data)
        self.assertEqual((status, note["error"], note["sources"]), (200, "RuntimeError", []))
        self.assertIn("실패", json.loads(self.stub.chats[-1]["body"]["messages"][-1]["content"])["error"])
        self.assertIn("하나", data.decode())

    async def test_tool_rounds_are_capped_and_the_last_round_must_answer(self):
        queries = self.search_with()
        _, _, data = await self.post({**user("끝없이 검색해 주세요"), "stream": True},
                                     **{"x-task": "translate", "x-web-search": "on"})
        self.assertEqual(len(queries), bff.MAX_TOOL_ROUNDS)
        self.assertEqual(self.stub.chats[-1]["body"]["tool_choice"], "none")
        self.assertIn("하나", data.decode())
        # 같은 주소가 다시 나와도 번호는 하나다.
        self.assertEqual({source["n"] for note in self.notes(data) for source in note["sources"]}, {1, 2})

    async def test_web_search_non_streaming_returns_sources_with_the_answer(self):
        self.search_with()
        status, _, data = await self.post(user("검색해 주세요"), **{"x-task": "translate", "x-web-search": "on"})
        body = json.loads(data)
        self.assertEqual((status, body["choices"][0]["message"]["content"]), (200, "답변입니다"))
        self.assertEqual([source["url"] for source in body["bff_sources"]],
                         ["https://weather.example/seoul", "https://news.example/a"])

    async def test_search_query_with_sensitive_format_is_not_sent(self):
        queries = self.search_with()
        result, note = await websearch.run("홍길동 900101-1234567", websearch.Sources())
        self.assertEqual((queries, result["results"], note["error"], note["query"]), ([], [], "sensitive_query", ""))
        # 검색어는 API 상한인 200자로 자른다.
        await websearch.run("가" * 300, websearch.Sources())
        self.assertEqual(len(queries[0]), 200)

    async def test_mock_order_api(self):
        async with self.http.get("http://127.0.0.1:18100/mock/orders/A-1024") as r:
            self.assertEqual((await r.json())["status"], "배송 중")

    async def test_english_page_gets_english_texts(self):
        """화면이 x-lang: en을 보내면 BFF가 만드는 문구가 영어다. 보내지 않으면 한국어 그대로다."""
        english = {"x-lang": "en"}
        # 오류 본문
        async with self.anon.post(BFF_URL + "/v1/chat/completions", json=user("hi"), headers=english) as r:
            self.assertEqual((r.status, (await r.json())["error"]["message"]), (401, "Sign-in is required"))
        async with self.anon.post(BFF_URL + "/v1/chat/completions", json=user("hi")) as r:
            self.assertEqual((await r.json())["error"]["message"], "로그인이 필요합니다")
        async with self.http.post(BFF_URL + "/v1/chat/completions", json={}, headers=english) as r:
            self.assertEqual((r.status, (await r.json())["error"]["message"]), (400, "A JSON body with messages is required"))
        image = {"messages": [{"role": "user", "content": [
            {"type": "text", "text": "card 4111 1111 1111 1111"}, {"type": "image_url", "image_url": {"url": "x"}}]}]}
        status, _, data = await self.post(image, **english)
        self.assertEqual(status, 422)
        self.assertNotRegex(json.loads(data)["error"]["message"], "[가-힣]")
        # 주문 조회: 도구 설명과 돌려주는 데이터
        async with self.http.get(BFF_URL + "/mock/orders/A-1024", headers=english) as r:
            self.assertEqual(await r.json(), {"order_id": "A-1024", "status": "In transit", "carrier": "Hanbit Express",
                                              "eta": "2026-11-16"})
        async with self.http.get(BFF_URL + "/mock/orders/Z-1", headers=english) as r:
            self.assertEqual((await r.json())["status"], "Order not found")
        await self.post({**user("주문 A-1024 어디쯤인가요"), "stream": True}, **{"x-task": "support", **english})
        first, second = self.stub.chats[-2]["body"], self.stub.chats[-1]["body"]
        self.assertNotRegex(json.dumps(first["tools"], ensure_ascii=False), "[가-힣]")
        self.assertIn("In transit", second["messages"][-1]["content"])
        # 웹 검색: 도구 설명, 지시문, 실패했을 때 모델에 주는 문구
        self.search_with(error=RuntimeError("AccessDeniedException"))
        await self.post({**user("이번 주 서울 날씨를 검색해 주세요"), "stream": True},
                        **{"x-task": "translate", "x-web-search": "on", **english})
        first, second = self.stub.chats[-2]["body"], self.stub.chats[-1]["body"]
        self.assertNotRegex(json.dumps(first["tools"], ensure_ascii=False), "[가-힣]")
        self.assertRegex(first["messages"][0]["content"], r"^Today is \d{4}-\d{2}-\d{2}")
        self.assertNotRegex(first["messages"][0]["content"], "[가-힣]")
        self.assertNotRegex(json.loads(second["messages"][-1]["content"])["error"], "[가-힣]")

    def test_every_text_has_both_languages(self):
        for key, (korean, english) in texts.TEXTS.items():
            with self.subTest(key):
                self.assertRegex(korean, "[가-힣]")
                self.assertNotRegex(english, "[가-힣]")
                self.assertEqual(sorted(texts.FIELDS.findall(korean)), sorted(texts.FIELDS.findall(english)))
        self.assertEqual((texts.language({"x-lang": "en"}), texts.language({"x-lang": "fr"}), texts.language({})),
                         ("en", "ko", "ko"))

    async def test_reason_header_explains_each_decision(self):
        async def reason(text, **headers):
            _, response_headers, _ = await self.post(user(text), **headers)
            return response_headers["x-bff-decision"], json.loads(response_headers["x-bff-reason"])

        self.assertEqual(await reason("안녕하세요", **{"x-task": "coding"}), ("task", {"task": "coding", "cached": False}))
        self.assertEqual(await reason("카드 4111 1111 1111 1111로 결제"), ("rule", {"pattern": "card", "cached": False}))
        self.assertEqual(await reason("주민번호는 900101-1234567입니다", **{"x-task": "coding"}),
                         ("rule", {"pattern": "rrn", "cached": False}))
        source, detail = await reason("이 코드 좀 봐 주세요", **{"x-session-id": "s-reason"})
        self.assertEqual(source, "decider")
        self.assertEqual(detail, {"route": "qwen", "route_confidence": 0.9, "policy": 0.05, "thinking": 0.9,
                                  "min_confidence": 0.6, "cached": False})
        # 같은 세션의 다음 요청은 저장된 결정과 근거를 그대로 쓴다.
        source, detail = await reason("이어서 질문합니다", **{"x-session-id": "s-reason"})
        self.assertEqual((source, detail["route"], detail["cached"]), ("decider", "qwen", True))
        # 세션 도중 민감 정보가 나오면 규칙이 이긴다.
        source, detail = await reason("제 번호는 900101-1234567", **{"x-session-id": "s-reason"})
        self.assertEqual((source, detail["pattern"], detail["during_session"]), ("rule", "rrn", True))
        source, detail = await reason("애매한 요청입니다")
        self.assertEqual((source, detail["why"], detail["low"], detail["route_confidence"]),
                         ("fallback", "low_confidence", ["route"], 0.3))
        source, detail = await reason("장애 상황을 확인합니다")
        self.assertEqual((source, detail["why"], detail["detail"]), ("fallback", "decider_unavailable", "status 500"))
        source, detail = await reason("제 이름은 홍길동입니다")  # policy 0.95: 개인정보로 판단
        self.assertEqual((source, detail["policy"]), ("decider", 0.95))
        # 헤더 값은 ASCII여야 한다.
        _, response_headers, _ = await self.post(user("안녕하세요"), **{"x-task": "support"})
        self.assertTrue(response_headers["x-bff-reason"].isascii())

    async def test_timing_header_reports_each_step_inside_the_bff(self):
        _, headers, _ = await self.post(user("안녕하세요"), **{"x-task": "translate"})
        timing = json.loads(headers["x-bff-timing"])
        self.assertEqual((timing["woke"], timing["tools"], timing["wake_ms"]), (False, False, 0.0))
        self.assertGreater(timing["upstream_ms"], 0)
        self.stub.sleeping = True
        _, headers, _ = await self.post(user("함수를 고쳐 주세요"), **{"x-task": "coding"})
        timing = json.loads(headers["x-bff-timing"])
        self.assertTrue(timing["woke"])                       # 잠들어 있어서 깨웠다
        self.assertGreaterEqual(timing["upstream_ms"], 400)   # 깨운 직후의 503을 다시 시도한 시간
        _, headers, _ = await self.post(user("주문 A-1024 어디쯤인가요"), **{"x-task": "support"})
        self.assertTrue(json.loads(headers["x-bff-timing"])["tools"])

    async def test_evaluation_request_goes_to_the_requested_model(self):
        for model, name in (("gemma", "gemma-4-31b"), ("qwen", "qwen38-27b")):
            status, headers, _ = await self.post({**user("주문 A-1024 어디쯤인가요"), "chat_template_kwargs": {"enable_thinking": True}},
                                                 **{"x-eval-model": model, "x-task": "support", "x-session-id": "s-eval"})
            sent = self.stub.chats[-1]
            self.assertEqual((status, headers["x-bff-model"], headers["x-bff-decision"]), (200, name, "eval"))
            # 두 모델의 조건을 맞춘다: 같은 우선순위, thinking 끔, 도구 없음.
            self.assertEqual(sent["headers"]["x-llm-d-inference-objective"], f"{model}-interactive")
            self.assertEqual((sent["body"]["priority"], sent["body"]["chat_template_kwargs"]["enable_thinking"]), (0, False))
            self.assertNotIn("tools", sent["body"])
        self.assertEqual((self.stub.decides, self.stub.wakes), (0, 1))  # Decider는 부르지 않고, Qwen만 깨우기 확인을 한다
        # 데이터 정책이 먼저다. 민감 정보가 있으면 Qwen을 요청해도 Gemma로 간다.
        _, headers, _ = await self.post(user("주민번호는 900101-1234567입니다"), **{"x-eval-model": "qwen"})
        self.assertEqual((headers["x-bff-model"], headers["x-bff-decision"]), ("gemma-4-31b", "rule"))
        status, _, _ = await self.post(user("안녕하세요"), **{"x-eval-model": "llama"})
        self.assertEqual(status, 400)

    async def test_korean_thinking_instruction_only_when_asked_and_thinking_is_on(self):
        ask = {"x-thinking-language": "ko"}
        await self.post(user("이 코드 좀 봐 주세요"), **ask)  # Decider: thinking 0.9
        messages = self.stub.chats[-1]["body"]["messages"]
        self.assertEqual((messages[0]["role"], messages[-1]["content"]), ("system", "이 코드 좀 봐 주세요"))
        self.assertIn("한국어로만", messages[0]["content"])
        await self.post({"messages": [{"role": "system", "content": "간결하게 답합니다."}, {"role": "user", "content": "이 코드 좀 봐 주세요"}]}, **ask)
        messages = self.stub.chats[-1]["body"]["messages"]
        self.assertEqual(len(messages), 2)
        self.assertTrue(messages[0]["content"].startswith("간결하게 답합니다.") and "한국어로만" in messages[0]["content"])
        await self.post(user("이 코드 좀 봐 주세요"))  # 헤더가 없으면 넣지 않는다
        self.assertEqual(len(self.stub.chats[-1]["body"]["messages"]), 1)
        await self.post(user("안녕하세요"), **{"x-task": "translate", **ask})  # thinking이 꺼져 있으면 넣지 않는다
        self.assertEqual(len(self.stub.chats[-1]["body"]["messages"]), 1)

    async def test_route_only_returns_the_decision_without_calling_a_model(self):
        async def route(text, **headers):
            async with self.http.post(BFF_URL + "/v1/route", json=user(text), headers=headers) as r:
                return r.status, await r.json()

        status, body = await route("이 코드 좀 봐 주세요")
        self.assertEqual((status, body["model"], body["decision"], body["thinking"]), (200, "qwen38-27b", "decider", True))
        self.assertEqual(body["reason"]["route_confidence"], 0.9)
        _, body = await route("주민번호는 900101-1234567입니다", **{"x-task": "coding"})
        self.assertEqual((body["model"], body["decision"], body["sensitive"], body["reason"]["pattern"]),
                         ("gemma-4-31b", "rule", True, "rrn"))
        _, body = await route("안녕하세요", **{"x-task": "translate"})
        self.assertEqual((body["decision"], body["objective"]), ("task", "gemma-batch"))
        self.assertEqual((self.stub.chats, self.stub.wakes, self.stub.decides), ([], 0, 1))  # 모델과 깨우기 API는 부르지 않는다
        async with self.anon.post(BFF_URL + "/v1/route", json=user("안녕하세요")) as r:
            self.assertEqual(r.status, 401)

    async def test_status_reports_each_component(self):
        async with self.http.get(BFF_URL + "/v1/status") as r:
            components = (await r.json())["components"]
        self.assertEqual({name: item["ok"] for name, item in components.items()}, {"gemma": True, "qwen": True, "decider": True})
        self.assertEqual((components["gemma"]["model"], components["qwen"]["max_model_len"]), ("gemma-4-31b", 32768))
        self.stub.sleeping = True
        async with self.http.get(BFF_URL + "/v1/status") as r:
            components = (await r.json())["components"]
        self.assertEqual((components["qwen"]["ok"], components["qwen"]["status"], components["gemma"]["ok"]), (False, 503, True))
        self.assertEqual(self.stub.wakes, 0)  # 상태 확인은 Qwen을 깨우지 않는다
        async with self.anon.get(BFF_URL + "/v1/status") as r:
            self.assertEqual(r.status, 401)

    async def test_timing_log_ties_request_to_alb_trace(self):
        events = []
        original, bff.log = bff.log, lambda event, **fields: events.append({"event": event, **fields})
        try:
            await self.post({**user("안녕하세요"), "stream": True},
                            **{"x-task": "translate", "x-request-id": "req-1", "X-Amzn-Trace-Id": "Root=1-abc"})
            await self.post({**user("주문 A-1024 어디쯤인가요"), "stream": True}, **{"x-task": "support", "x-request-id": "req-2"})
        finally:
            bff.log = original
        started = next(e for e in events if e["event"] == "chat" and e["request_id"] == "req-1")
        self.assertEqual(started["trace_id"], "Root=1-abc")
        for request_id in ("req-1", "req-2"):
            end = next(e for e in events if e["event"] == "chat_end" and e["request_id"] == request_id)
            # 첫 내용은 첫 Chunk보다 먼저일 수 없고, 전체 시간 안에 있다.
            self.assertGreater(end["first_chunk_ms"], 0)
            self.assertGreaterEqual(end["first_content_ms"], end["first_chunk_ms"])
            self.assertGreaterEqual(end["total_ms"], end["first_content_ms"])
            self.assertGreater(end["bytes"], 0)

    async def chat_status(self, authorization):
        headers = {"x-task": "translate", **({"Authorization": authorization} if authorization else {})}
        async with self.anon.post(BFF_URL + "/v1/chat/completions", json=user("안녕하세요"), headers=headers) as r:
            return r.status

    async def test_request_without_valid_token_is_rejected(self):
        cases = {
            "토큰 없음": None,
            "Bearer가 아님": "Basic ZGVtbzpkZW1v",
            "JWT 형식이 아님": "Bearer not-a-jwt",
            "만료": "Bearer " + token(exp=int(time.time()) - 10),
            "다른 키로 서명": "Bearer " + token(key=OTHER_KEY),
            "다른 발급자": "Bearer " + token(iss="http://127.0.0.1:18103/other"),
            "다른 앱 클라이언트": "Bearer " + token(client_id="someone-else"),
            "ID 토큰": "Bearer " + token(token_use="id"),
            "서명 없음": "Bearer " + unsigned_token(),
            "공개 키로 HS256 서명": "Bearer " + hs256_token_signed_with_public_key(),
        }
        for name, authorization in cases.items():
            with self.subTest(name):
                self.assertEqual(await self.chat_status(authorization), 401)
        self.assertEqual((self.stub.chats, self.stub.decides), ([], 0))  # 게이트웨이까지 가지 않는다
        self.assertEqual(await self.chat_status("Bearer " + token()), 200)

    async def test_only_healthz_is_open(self):
        async with self.anon.get(BFF_URL + "/healthz") as r:
            self.assertEqual(r.status, 200)
        async with self.anon.get(BFF_URL + "/mock/orders/A-1024") as r:
            self.assertEqual(r.status, 401)

    async def test_unknown_key_id_does_not_refetch_keys_each_time(self):
        for _ in range(3):
            self.assertEqual(await self.chat_status("Bearer " + token(kid="unknown")), 401)
        self.assertEqual(self.stub.jwks_fetches, 1)
        self.assertEqual(await self.chat_status("Bearer " + token()), 200)
        self.assertEqual(self.stub.jwks_fetches, 1)


if __name__ == "__main__":
    unittest.main()
