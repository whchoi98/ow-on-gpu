#!/usr/bin/env python3
"""우선순위 효과. 배치 부하를 걸어 둔 채로 상담 요청의 TTFT를 잰다. 클러스터 안의 측정 파드에서 실행한다.

네 가지 경우를 차례로 돌린다.
  none     게이트웨이와 엔진 모두 우선순위를 쓰지 않는다(대조군)
  gateway  게이트웨이만: x-llm-d-inference-objective 헤더로 상담은 priority 10, 배치는 -1
  engine   엔진만: 본문 priority로 상담은 0, 배치는 10 (vLLM은 값이 작을수록 먼저 처리한다)
  both     둘 다

요청은 모두 게이트웨이를 거친다. 배치 요청은 긴 입력(문서 요약)이고 KV 캐시가 차서 대기열이 생길 만큼 보낸다.
게이트웨이가 429로 거절한 배치 요청은 세고 잠깐 쉰 뒤 다시 보낸다.

출력은 경우마다 JSON 한 줄이다. RESULTS_DIR이 있으면 priority.jsonl에도 쓴다.
"""
import asyncio
import json
import os
import random
import statistics
import time

import aiohttp

GATEWAY = os.environ.get("GATEWAY_URL", "http://inference-gateway.inference.svc")
MODEL = os.environ.get("MODEL_NAME", "gemma-4-31b")
POOL = os.environ.get("POOL", "gemma")
METRICS_URL = os.environ.get("METRICS_URL", "http://vllm-gemma.inference.svc:8000/metrics")
VARIANTS = os.environ.get("VARIANTS", "none gateway engine both").split()
BATCH_WORKERS = int(os.environ.get("BATCH_WORKERS", "32"))
WARMUP = float(os.environ.get("WARMUP_SECONDS", "20"))
DURATION = float(os.environ.get("DURATION_SECONDS", "90"))
PROBE_INTERVAL = float(os.environ.get("PROBE_INTERVAL_SECONDS", "1.5"))
BATCH_SENTENCES = int(os.environ.get("BATCH_SENTENCES", "60"))
RESULTS_DIR = os.environ.get("RESULTS_DIR")

SENTENCES = [
    "배송은 예상보다 하루 빨리 도착했고 포장 상태도 깔끔했습니다.",
    "색상이 화면에서 본 것보다 조금 어두웠지만 마감은 만족스럽습니다.",
    "설명서가 영어로만 되어 있어서 조립하는 데 시간이 오래 걸렸습니다.",
    "가격에 비해 소재가 얇은 편이라 겨울에 입기에는 아쉬움이 있습니다.",
    "고객센터에 문의했더니 당일에 답변을 받아서 문제를 바로 해결했습니다.",
    "배터리가 하루를 넘기지 못해서 충전기를 항상 들고 다녀야 합니다.",
    "사이즈가 표기보다 작게 나와서 한 치수 크게 주문하는 편이 좋겠습니다.",
    "소음이 거의 없어서 밤에도 부담 없이 사용할 수 있었습니다.",
    "두 번째 구매인데 지난번과 품질이 같아서 믿고 주문했습니다.",
    "반품 절차가 복잡해서 접수하는 데만 이십 분이 넘게 걸렸습니다.",
    "선물용으로 샀는데 받는 사람이 무척 마음에 들어 했습니다.",
    "앱과 연결할 때 자주 끊겨서 펌웨어 업데이트가 필요해 보입니다.",
]
QUESTIONS = ["교환 신청은 어디서 하나요?", "배송지를 바꿀 수 있나요?", "적립금은 언제 들어오나요?",
             "영수증을 다시 받을 수 있나요?", "주문을 취소하고 싶습니다. 어떻게 하나요?", "품절 상품의 재입고 알림을 받을 수 있나요?"]


def batch_prompt(rng):
    # 요청마다 문장 순서와 주문 번호가 달라 앞부분이 겹치지 않는다. prefix 캐시로 입력이 줄어들지 않게 하기 위해서다.
    lines = [f"[리뷰 {rng.randint(100000, 999999)}] {rng.choice(SENTENCES)}" for _ in range(BATCH_SENTENCES)]
    return "다음 상품 리뷰들을 읽고 장점과 단점을 항목별로 요약해 주세요.\n\n" + "\n".join(lines)


def payload(prompt, max_tokens, priority):
    return {"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": True, "max_tokens": max_tokens,
            "priority": priority, "chat_template_kwargs": {"enable_thinking": False},
            "stream_options": {"include_usage": True}}


async def stream(http, body, headers):
    """(상태 코드, 첫 내용까지의 초, 전체 초, usage)를 돌려준다."""
    started = time.monotonic()
    first, usage = None, None
    async with http.post(GATEWAY + "/v1/chat/completions", json=body, headers=headers) as response:
        if response.status != 200:
            await response.read()
            return response.status, None, time.monotonic() - started, None
        async for raw in response.content:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            event = json.loads(line[6:])
            usage = event.get("usage") or usage
            choices = event.get("choices") or []
            if first is None and choices and choices[0].get("delta", {}).get("content"):
                first = time.monotonic() - started
    return 200, first, time.monotonic() - started, usage


def metric(text, name):
    return sum(float(line.rsplit(" ", 1)[1]) for line in text.splitlines()
               if line.startswith(name) and line[len(name)] in "{ ")


async def vllm_metrics(http):
    async with http.get(METRICS_URL) as response:
        text = await response.text()
    return {"waiting": metric(text, "vllm:num_requests_waiting"), "running": metric(text, "vllm:num_requests_running"),
            "kv": metric(text, "vllm:kv_cache_usage_perc"), "preemptions": metric(text, "vllm:num_preemptions_total")}


def percentile(values, q):
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * q))]


async def run_variant(http, variant):
    use_gateway, use_engine = variant in ("gateway", "both"), variant in ("engine", "both")
    interactive_headers = {"x-llm-d-inference-objective": f"{POOL}-interactive"} if use_gateway else {}
    batch_headers = {"x-llm-d-inference-objective": f"{POOL}-batch"} if use_gateway else {}
    batch_priority = 10 if use_engine else 0
    stop = asyncio.Event()
    batch = {"completed": 0, "rejected_429": 0, "other_status": {}, "prompt_tokens": 0, "completion_tokens": 0, "errors": 0}
    probes, samples = [], []

    async def batch_worker(seed):
        rng = random.Random(seed)
        while not stop.is_set():
            try:
                status, _, _, usage = await stream(http, payload(batch_prompt(rng), 256, batch_priority), batch_headers)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                batch["errors"] += 1
                await asyncio.sleep(0.5)
                continue
            if status == 200:
                batch["completed"] += 1
                batch["prompt_tokens"] += (usage or {}).get("prompt_tokens", 0)
                batch["completion_tokens"] += (usage or {}).get("completion_tokens", 0)
            elif status == 429:
                batch["rejected_429"] += 1
                await asyncio.sleep(0.5)
            else:
                batch["other_status"][str(status)] = batch["other_status"].get(str(status), 0) + 1
                await asyncio.sleep(0.5)

    async def probe(index):
        question = QUESTIONS[index % len(QUESTIONS)] + f" (문의 번호 {random.randint(1000, 9999)})"
        try:
            status, first, total, _ = await stream(http, payload(question, 48, 0), interactive_headers)
        except (aiohttp.ClientError, asyncio.TimeoutError) as error:
            probes.append({"status": type(error).__name__, "ttft_ms": None})
            return
        probes.append({"status": status, "ttft_ms": None if first is None else round(first * 1000, 1),
                       "total_ms": round(total * 1000, 1)})

    async def sampler():
        while not stop.is_set():
            try:
                samples.append(await vllm_metrics(http))
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(2)

    before = await vllm_metrics(http)
    workers = [asyncio.create_task(batch_worker(seed)) for seed in range(BATCH_WORKERS)]
    watcher = asyncio.create_task(sampler())
    await asyncio.sleep(WARMUP)
    counted_from = dict(batch)
    measure_started = time.monotonic()
    tasks = []
    index = 0
    while time.monotonic() - measure_started < DURATION:
        tasks.append(asyncio.create_task(probe(index)))
        index += 1
        await asyncio.sleep(PROBE_INTERVAL)
    measured = time.monotonic() - measure_started
    during = {key: batch[key] - counted_from[key] for key in ("completed", "rejected_429", "prompt_tokens", "completion_tokens")}
    await asyncio.wait(tasks, timeout=120)
    stop.set()
    for worker in workers:
        worker.cancel()
    await asyncio.gather(*workers, watcher, return_exceptions=True)

    # 다음 경우에 영향을 주지 않게 엔진이 빌 때까지 기다린다.
    for _ in range(90):
        now = await vllm_metrics(http)
        if now["waiting"] == 0 and now["running"] == 0:
            break
        await asyncio.sleep(2)
    after = await vllm_metrics(http)

    ok = [p["ttft_ms"] for p in probes if p["status"] == 200 and p["ttft_ms"] is not None]
    statuses = {}
    for p in probes:
        statuses[str(p["status"])] = statuses.get(str(p["status"]), 0) + 1
    return {
        "variant": variant, "model": MODEL, "batch_workers": BATCH_WORKERS, "duration_s": round(measured, 1),
        "interactive": {
            "sent": len(probes), "status": statuses,
            "ttft_ms": {"p50": percentile(ok, 0.5), "p90": percentile(ok, 0.9), "p99": percentile(ok, 0.99),
                        "max": max(ok), "mean": round(statistics.mean(ok), 1)} if ok else None,
        },
        "batch": {**during, "output_tok_s": round(during["completion_tokens"] / measured, 1),
                  "avg_prompt_tokens": round(during["prompt_tokens"] / during["completed"]) if during["completed"] else None,
                  "other_status": batch["other_status"], "errors": batch["errors"]},
        "vllm": {
            "waiting_max": max((s["waiting"] for s in samples), default=None),
            "waiting_mean": round(statistics.mean(s["waiting"] for s in samples), 1) if samples else None,
            "running_max": max((s["running"] for s in samples), default=None),
            "kv_usage_max": max((s["kv"] for s in samples), default=None),
            "preemptions": after["preemptions"] - before["preemptions"],
        },
        "probes": probes,
    }


async def main():
    timeout = aiohttp.ClientTimeout(total=600, sock_connect=10)
    connector = aiohttp.TCPConnector(limit=0)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as http:
        for variant in VARIANTS:
            result = await run_variant(http, variant)
            line = json.dumps(result, ensure_ascii=False)
            print(line, flush=True)
            if RESULTS_DIR:
                os.makedirs(RESULTS_DIR, exist_ok=True)
                with open(os.path.join(RESULTS_DIR, "priority.jsonl"), "a") as out:
                    out.write(line + "\n")


if __name__ == "__main__":
    asyncio.run(main())
