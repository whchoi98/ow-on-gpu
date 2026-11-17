#!/usr/bin/env python3
"""구간별 TTFT. CloudFront 주소로 요청을 하나씩 보내고, 각 구간이 남긴 기록을 요청 ID로 이어
사용자가 본 첫 토큰까지의 시간을 구간별로 나눈다. 작업 장비에서 실행한다. 표준 라이브러리만 쓴다.

  USER_PASSWORD=... python3 segments.py --url https://dxxxx.cloudfront.net --email demo@example.com \
      --client-id <앱 클라이언트 ID> --alb-log-bucket <버킷> --out results/2026-11-14-ttft-segments

구간과 근거
  사용자와 엣지 사이   클라이언트가 잰 응답 헤더 도착 시간 - CloudFront의 cdn-downstream-fbl
  CloudFront          cdn-downstream-fbl - ALB가 요청을 받아 응답 헤더를 내보내기까지의 시간
                      (엣지 처리와 VPC origin 구간. Server-Timing 헤더와 ALB 접근 로그)
  ALB                 ALB의 request_processing_time + target_processing_time - BFF가 응답 헤더를 내보내기까지의 시간
                      (ALB 처리와 ALB에서 BFF까지. ALB 접근 로그와 BFF 로그를 X-Amzn-Trace-Id로 이음)
  BFF                 판단 시간 + 깨우기 API 호출 시간 (BFF 로그)
  게이트웨이           BFF가 게이트웨이에 요청을 보낸 뒤 내용이 담긴 첫 Chunk를 받기까지의 시간 - vLLM의 TTFT
                      (agentgateway, EPP. BFF 로그와 vLLM 지표. 2026-11-15부터 BFF는 EKS 파드이고 게이트웨이의
                      Service를 직접 부른다. 그전의 측정에는 게이트웨이 NLB가 이 구간에 들어 있었다)
  vLLM                vllm:time_to_first_token_seconds의 합계가 요청 전후로 늘어난 값
                      (요청을 하나씩 보내므로 늘어난 횟수가 1일 때만 그 요청의 값으로 쓴다)
  나머지               사용자가 본 첫 내용까지의 시간에서 위 여섯 구간을 뺀 값

vLLM과 EPP의 지표는 kubectl port-forward로, BFF 로그는 파드의 표준 출력(kubectl logs)에서 읽는다.
ALB 접근 로그는 5분마다 S3에 올라오므로 요청을 다 보낸 뒤 로그가 올 때까지 기다린다.
"""
import argparse
import gzip
import http.client
import json
import os
import shlex
import socket
import statistics
import subprocess
import sys
import time
import urllib.parse
import urllib.request

NAMESPACE = "inference"
BFF_NAMESPACE = "app"
REGION = "ap-northeast-2"
CASES = {
    "gemma": {"task": "support", "pod_selector": "app.kubernetes.io/name=vllm-gemma", "epp": "gemma-epp",
              # 주문 조회 도구를 부르지 않는 질문이어야 게이트웨이 호출이 한 번이다.
              "prompts": ["반품은 며칠 안에 신청해야 하나요?", "교환할 때 배송비는 누가 내나요?", "포인트는 언제 적립되나요?",
                          "선물 포장이 되나요?", "해외로도 배송하나요?", "영수증은 어디서 받나요?",
                          "회원 등급은 어떻게 올라가나요?", "결제 수단을 바꿀 수 있나요?", "품절 상품은 언제 다시 들어오나요?",
                          "쿠폰은 중복으로 쓸 수 있나요?"]},
    "qwen": {"task": "coding", "pod_selector": "app.kubernetes.io/name=vllm-qwen", "epp": "qwen-epp",
             "prompts": ["파이썬에서 리스트를 뒤집는 방법을 한 줄로 알려 주세요.", "파이썬에서 딕셔너리를 값으로 정렬하는 한 줄 코드를 알려 주세요.",
                         "자바스크립트에서 배열의 합을 구하는 한 줄 코드를 알려 주세요.", "Go에서 문자열을 정수로 바꾸는 함수를 알려 주세요.",
                         "SQL에서 중복 행을 세는 쿼리를 알려 주세요.", "bash에서 파일의 줄 수를 세는 명령을 알려 주세요.",
                         "파이썬에서 현재 시각을 ISO 형식으로 출력하는 코드를 알려 주세요.", "자바에서 문자열이 비었는지 확인하는 코드를 알려 주세요.",
                         "파이썬에서 두 리스트의 교집합을 구하는 한 줄 코드를 알려 주세요.", "Rust에서 벡터의 최댓값을 구하는 코드를 알려 주세요."]},
}


def run(*command):
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


def sign_in(client_id, email, password):
    request = urllib.request.Request(
        f"https://cognito-idp.{REGION}.amazonaws.com/",
        data=json.dumps({"AuthFlow": "USER_PASSWORD_AUTH", "ClientId": client_id,
                         "AuthParameters": {"USERNAME": email, "PASSWORD": password}}).encode(),
        headers={"Content-Type": "application/x-amz-json-1.1",
                 "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)["AuthenticationResult"]["AccessToken"]


class Forward:
    """kubectl port-forward. 파드의 /metrics를 작업 장비에서 읽는다."""

    def __init__(self, pod, local, remote):
        self.port = local
        self.process = subprocess.Popen(["kubectl", "-n", NAMESPACE, "port-forward", "pod/" + pod, f"{local}:{remote}"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                socket.create_connection(("127.0.0.1", local), timeout=0.2).close()
                return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError(f"port-forward가 열리지 않습니다: {pod}")

    def scrape(self, token=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}/metrics",
                                         headers={"Authorization": f"Bearer {token}"} if token else {})
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.read().decode()

    def close(self):
        self.process.terminate()


def metric(text, name):
    """이름이 같은 시계열의 값을 모두 더한다."""
    total = 0.0
    for line in text.splitlines():
        if line.startswith(name) and line[len(name)] in "{ ":
            total += float(line.rsplit(" ", 1)[1])
    return total


VLLM_METRICS = {
    "ttft": "vllm:time_to_first_token_seconds",
    "queue": "vllm:request_queue_time_seconds",
    "prefill": "vllm:request_prefill_time_seconds",
}


def vllm_snapshot(text):
    return {key: (metric(text, name + "_sum"), metric(text, name + "_count")) for key, name in VLLM_METRICS.items()}


def delta_ms(before, after, key):
    """요청 하나의 값(ms). 그 사이에 관측이 정확히 하나 늘었을 때만 돌려준다."""
    if round(after[key][1] - before[key][1]) != 1:
        return None
    return round((after[key][0] - before[key][0]) * 1000, 1)


def server_timing(header):
    values = {}
    for part in (header or "").split(","):
        name, _, rest = part.strip().partition(";")
        if rest.startswith("dur="):
            values[name] = float(rest[4:])
        elif rest.startswith("desc="):
            values[name] = rest[5:].strip('"')
    return values


def send(connection, token, task, prompt, max_tokens):
    body = json.dumps({"messages": [{"role": "user", "content": prompt}], "stream": True, "max_tokens": max_tokens})
    headers = {"Content-Type": "application/json", "Authorization": "Bearer " + token, "x-task": task,
               "x-session-id": f"ttft-{time.time_ns()}"}
    sent_at = time.time()
    started = time.monotonic()
    connection.request("POST", "/v1/chat/completions", body=body.encode(), headers=headers)
    response = connection.getresponse()
    headers_ms = (time.monotonic() - started) * 1000
    first = None
    chunks = 0
    while True:
        line = response.readline()
        if not line:
            break
        text = line.decode("utf-8", "replace").strip()
        if not text.startswith("data: ") or text == "data: [DONE]":
            continue
        delta = (json.loads(text[6:]).get("choices") or [{}])[0].get("delta", {})
        if delta.get("content"):
            chunks += 1
            if first is None:
                first = (time.monotonic() - started) * 1000
    return {
        "sent_at": sent_at,
        "status": response.status,
        "request_id": response.getheader("x-request-id"),
        "model": response.getheader("x-bff-model"),
        "decision": response.getheader("x-bff-decision"),
        "cf_pop": response.getheader("x-amz-cf-pop"),
        "user_headers_ms": round(headers_ms, 1),
        "user_first_content_ms": None if first is None else round(first, 1),
        "user_total_ms": round((time.monotonic() - started) * 1000, 1),
        "content_chunks": chunks,
        "server_timing": server_timing(response.getheader("server-timing")),
    }


def trace_root(value):
    """X-Amzn-Trace-Id에서 Root 부분만 뽑는다. ALB 로그와 BFF가 받은 헤더의 나머지 부분이 달라도 잇기 위해서다."""
    for part in (value or "").split(";"):
        if part.strip().startswith("Root="):
            return part.strip()
    return value or ""


def bff_logs(since, request_ids):
    """요청 ID별로 BFF의 chat, chat_end 로그를 모은다. BFF 파드 전체의 표준 출력에서 since(epoch 초) 뒤의 줄을 읽는다."""
    found = {request_id: {} for request_id in request_ids}
    since_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(since))
    output = run("kubectl", "-n", BFF_NAMESPACE, "logs", "-l", "app.kubernetes.io/name=bff", "--since-time", since_time,
                 "--tail=-1", "--max-log-requests", "10")
    for line in output.splitlines():
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if record.get("request_id") in found and record.get("event") in ("chat", "chat_end"):
            found[record["request_id"]][record["event"]] = record
    return found


def alb_logs(bucket, since, trace_ids, wait_seconds):
    """ALB 접근 로그에서 trace ID가 맞는 줄을 찾는다. 로그는 5분마다 올라오므로 다 찾을 때까지 기다린다."""
    account = json.loads(run("aws", "sts", "get-caller-identity", "--output", "json"))["Account"]
    day = time.strftime("%Y/%m/%d", time.gmtime(since))
    prefix = f"bff/AWSLogs/{account}/elasticloadbalancing/{REGION}/{day}/"
    found, seen = {}, set()
    deadline = time.monotonic() + wait_seconds
    while True:
        listing = json.loads(run("aws", "s3api", "list-objects-v2", "--bucket", bucket, "--prefix", prefix,
                                 "--output", "json") or "{}")
        for item in listing.get("Contents", []):
            if item["Key"] in seen:
                continue
            seen.add(item["Key"])
            data = subprocess.run(["aws", "s3", "cp", f"s3://{bucket}/{item['Key']}", "-"], capture_output=True, check=True).stdout
            for line in gzip.decompress(data).decode().splitlines():
                fields = shlex.split(line)
                # 0 type, 1 time, 5 request_processing_time, 6 target_processing_time, 7 response_processing_time, 17 trace_id
                if len(fields) > 17 and trace_root(fields[17]) in trace_ids:
                    found[trace_root(fields[17])] = {"time": fields[1], "request_processing_ms": float(fields[5]) * 1000,
                                         "target_processing_ms": float(fields[6]) * 1000,
                                         "response_processing_ms": float(fields[7]) * 1000,
                                         "elb_status": fields[8], "raw": line}
        if len(found) == len(trace_ids) or time.monotonic() > deadline:
            return found
        print(f"ALB 접근 로그를 기다립니다: {len(found)}/{len(trace_ids)}", flush=True)
        time.sleep(30)


def summarize(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    ordered = sorted(values)
    return {"n": len(values), "median": round(statistics.median(values), 1), "min": round(ordered[0], 1),
            "p95": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))], 1), "max": round(ordered[-1], 1)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--alb-log-bucket", required=True)
    parser.add_argument("--models", default="gemma,qwen")
    parser.add_argument("--requests", type=int, default=20, help="모델마다 보낼 요청 수")
    parser.add_argument("--max-tokens", type=int, default=32)
    parser.add_argument("--alb-wait", type=int, default=660, help="ALB 접근 로그를 기다리는 최대 시간(초)")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)

    token = sign_in(args.client_id, args.email, os.environ["USER_PASSWORD"])
    admin = json.loads(run("aws", "eks", "get-token", "--cluster-name", "ow-on-gpu", "--region", REGION,
                           "--output", "json"))["status"]["token"]
    host = urllib.parse.urlparse(args.url).netloc
    started_at = time.time()
    records = []
    forwards = []
    try:
        for index, name in enumerate(args.models.split(",")):
            case = CASES[name]
            pod = run("kubectl", "-n", NAMESPACE, "get", "pod", "-l", case["pod_selector"],
                      "-o", "jsonpath={.items[0].metadata.name}")
            epp_pods = json.loads(run("kubectl", "-n", NAMESPACE, "get", "pod", "-l", f"llm-d-router-gateway={case['epp']}",
                                      "-o", "json"))["items"]
            # 리더만 Ready다. 요청을 처리하는 쪽의 지표를 읽는다.
            leader = next(p["metadata"]["name"] for p in epp_pods if p["status"]["containerStatuses"][0]["ready"])
            vllm = Forward(pod, 18100 + index, 8000)
            epp = Forward(leader, 18200 + index, 9090)
            forwards += [vllm, epp]

            connection = http.client.HTTPSConnection(host, timeout=120)
            connect_started = time.monotonic()
            connection.connect()
            connect_ms = round((time.monotonic() - connect_started) * 1000, 1)
            for i in range(args.requests + 1):
                before, epp_before = vllm_snapshot(vllm.scrape()), epp.scrape(admin)
                record = send(connection, token, case["task"], case["prompts"][i % len(case["prompts"])], args.max_tokens)
                time.sleep(0.3)  # vLLM이 요청을 마치고 지표를 올릴 시간을 둔다
                after, epp_after = vllm_snapshot(vllm.scrape()), epp.scrape(admin)
                scheduler = "llm_d_epp_scheduler_e2e_duration_seconds"
                attempts = round(metric(epp_after, scheduler + "_count") - metric(epp_before, scheduler + "_count"))
                record.update({
                    "case": name, "index": i, "warmup": i == 0, "tls_connect_ms": connect_ms if i == 0 else None,
                    "vllm_ttft_ms": delta_ms(before, after, "ttft"),
                    "vllm_queue_ms": delta_ms(before, after, "queue"),
                    "vllm_prefill_ms": delta_ms(before, after, "prefill"),
                    "vllm_requests_between_scrapes": round(after["ttft"][1] - before["ttft"][1]),
                    "epp_scheduler_ms": round((metric(epp_after, scheduler + "_sum") - metric(epp_before, scheduler + "_sum"))
                                              * 1000, 2) if attempts == 1 else None,
                })
                records.append(record)
                print(json.dumps({k: record[k] for k in ("case", "index", "status", "model", "user_headers_ms",
                                                         "user_first_content_ms", "vllm_ttft_ms")}), flush=True)
                time.sleep(1)
            connection.close()
    finally:
        for forward in forwards:
            forward.close()

    logs = bff_logs(started_at - 5, [r["request_id"] for r in records])
    for record in records:
        entry = logs.get(record["request_id"], {})
        record["bff"] = {**{k: entry.get("chat", {}).get(k) for k in ("trace_id", "decide_ms", "wake_ms", "upstream_headers_ms",
                                                                      "objective", "source")},
                         **{k: entry.get("chat_end", {}).get(k) for k in ("first_chunk_ms", "first_content_ms", "total_ms")}}
    traces = {trace_root(r["bff"]["trace_id"]) for r in records if r["bff"].get("trace_id")}
    alb = alb_logs(args.alb_log_bucket, started_at, traces, args.alb_wait)
    with open(os.path.join(args.out, "alb-log-lines.txt"), "w") as out:
        out.write("\n".join(item["raw"] for item in alb.values()) + "\n")

    for record in records:
        bff, timing = record["bff"], record["server_timing"]
        entry = alb.get(trace_root(bff.get("trace_id")))
        record["alb"] = {k: v for k, v in entry.items() if k != "raw"} if entry else None
        segments = {}
        try:
            alb_total = entry["request_processing_ms"] + entry["target_processing_ms"]
            bff_headers = bff["decide_ms"] + bff["wake_ms"] + bff["upstream_headers_ms"]
            segments["user_to_edge"] = record["user_headers_ms"] - timing["cdn-downstream-fbl"]
            segments["cloudfront"] = timing["cdn-downstream-fbl"] - alb_total
            segments["alb"] = alb_total - bff_headers
            segments["bff"] = bff["decide_ms"] + bff["wake_ms"]
            segments["gateway"] = bff["first_content_ms"] - segments["bff"] - record["vllm_ttft_ms"]
            segments["vllm"] = record["vllm_ttft_ms"]
            segments["remainder"] = record["user_first_content_ms"] - sum(segments.values())
            segments = {k: round(v, 1) for k, v in segments.items()}
        except (KeyError, TypeError):
            segments = None  # 어느 한 구간의 기록이 없으면 나누지 않는다
        record["segments_ms"] = segments

    with open(os.path.join(args.out, "requests.jsonl"), "w") as out:
        for record in records:
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

    summary = {"url": args.url, "requests_per_model": args.requests, "max_tokens": args.max_tokens, "models": {}}
    for name in args.models.split(","):
        rows = [r for r in records if r["case"] == name and not r["warmup"] and r["status"] == 200]
        complete = [r for r in rows if r["segments_ms"]]
        summary["models"][name] = {
            "requests": len(rows),
            "requests_with_all_segments": len(complete),
            "user_first_content_ms": summarize([r["user_first_content_ms"] for r in rows]),
            "user_headers_ms": summarize([r["user_headers_ms"] for r in rows]),
            "segments_ms": {key: summarize([r["segments_ms"][key] for r in complete])
                            for key in ("user_to_edge", "cloudfront", "alb", "bff", "gateway", "vllm", "remainder")},
            "detail_ms": {
                "cdn_upstream_fbl": summarize([r["server_timing"].get("cdn-upstream-fbl") for r in rows]),
                "cdn_downstream_fbl": summarize([r["server_timing"].get("cdn-downstream-fbl") for r in rows]),
                "alb_request_processing": summarize([r["alb"]["request_processing_ms"] for r in rows if r["alb"]]),
                "alb_target_processing": summarize([r["alb"]["target_processing_ms"] for r in rows if r["alb"]]),
                "bff_decide": summarize([r["bff"].get("decide_ms") for r in rows]),
                "bff_wake": summarize([r["bff"].get("wake_ms") for r in rows]),
                "bff_upstream_headers": summarize([r["bff"].get("upstream_headers_ms") for r in rows]),
                "bff_first_content": summarize([r["bff"].get("first_content_ms") for r in rows]),
                "vllm_queue": summarize([r["vllm_queue_ms"] for r in rows]),
                "vllm_prefill": summarize([r["vllm_prefill_ms"] for r in rows]),
                "epp_scheduler": summarize([r["epp_scheduler_ms"] for r in rows]),
            },
        }
    with open(os.path.join(args.out, "summary.json"), "w") as out:
        json.dump(summary, out, ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
