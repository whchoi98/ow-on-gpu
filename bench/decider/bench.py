#!/usr/bin/env python3
"""Strands Decider의 판단 1회 지연을 잰다. 표준 라이브러리만 쓴다.

판단 종류는 셋이다.
  route     선택지 2개(gemma, qwen) 중 하나를 고른다 (choice)
  policy    개인정보가 들어 있는지 판단한다 (noul)
  thinking  단계적 추론이 필요한지 판단한다 (noul)

요청 하나에 질문 하나만 넣어 판단 1회의 지연을 잰다. 요청은 차례로 보낸다.
출력은 한 줄에 JSON 하나다. request 줄이 원시 측정값이고 summary 줄이 판단별 중앙값과 p95다.

  python3 bench.py --url http://decider.inference.svc:8080/v1/systemone --label warm --n 50
"""
import argparse
import json
import statistics
import sys
import time
import urllib.request

QUESTIONS = {
    "route": {
        "type": "choice",
        "instructions": "이 요청을 처리할 모델을 고르세요.",
        "criteria": {
            "gemma": "고객 상담, 주문 조회, 번역, 요약처럼 텍스트만 다루는 요청",
            "qwen": "이미지나 문서를 읽어야 하거나 코드를 작성하고 고치는 요청",
        },
    },
    "policy": {
        "type": "noul",
        "instructions": "이 요청에 이름, 연락처, 주소, 계좌 같은 개인정보가 들어 있습니까?",
    },
    "thinking": {
        "type": "noul",
        "instructions": "이 요청에 답하려면 여러 단계를 거친 추론이 필요합니까?",
    },
}

STATES = [
    "지난주에 주문한 운동화가 아직 안 왔어요. 주문 번호는 A-1024입니다. 언제 도착하나요?",
    "이 상품 설명을 영어와 일본어로 번역해 주세요. 가볍고 통기성이 좋은 여름용 러닝화입니다.",
    "첨부한 영수증 사진에서 결제 금액과 결제일을 뽑아 주세요.",
    "주문 내역을 조회하는 파이썬 함수에서 날짜 필터가 동작하지 않습니다. 코드를 고쳐 주세요.",
    "홍길동입니다. 연락처는 010-1234-5678이고 배송지를 서울시 강남구 테헤란로 1로 바꿔 주세요.",
    "최근 한 달 리뷰 200건을 장점과 단점으로 나눠 세 줄로 요약해 주세요.",
    "환불 규정이 어떻게 되나요? 포장을 뜯은 상품도 반품이 되나요?",
    "세 가지 요금제 중 한 달에 15건을 주문하는 저에게 가장 싼 것은 무엇인지 계산해 주세요.",
    "상품 상세 이미지에서 색상, 소재, 사이즈 표를 표로 정리해 주세요.",
    "안녕하세요. 영업시간이 어떻게 되나요?",
]


def ask(url, state, name):
    body = json.dumps({"state": state, "questions": {name: QUESTIONS[name]}}).encode()
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    client_ms = (time.monotonic() - started) * 1000
    return client_ms, payload


def percentile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://decider.inference.svc:8080/v1/systemone")
    parser.add_argument("--label", required=True, help="결과에 붙일 이름. 예: no-warmup, warm, gateway")
    parser.add_argument("--n", type=int, default=50, help="판단 종류마다 보낼 요청 수")
    args = parser.parse_args()

    samples = {name: {"client_ms": [], "server_ms": []} for name in QUESTIONS}
    # 판단 종류를 번갈아 보낸다. 첫 요청이 종류별로 따로 기록되어 예열 전의 값을 볼 수 있다.
    for i in range(args.n):
        for name in QUESTIONS:
            client_ms, payload = ask(args.url, STATES[i % len(STATES)], name)
            samples[name]["client_ms"].append(client_ms)
            samples[name]["server_ms"].append(payload["latency_ms"])
            print(json.dumps({
                "event": "request", "label": args.label, "decision": name, "index": i,
                "client_ms": round(client_ms, 2), "server_ms": payload["latency_ms"],
                "answer": payload["answers"][name], "usage": payload.get("usage"),
            }, ensure_ascii=False), flush=True)

    for name, values in samples.items():
        summary = {"event": "summary", "label": args.label, "decision": name, "n": args.n, "url": args.url}
        for key in ("client_ms", "server_ms"):
            data = values[key]
            summary[key] = {
                "first": round(data[0], 2),
                "median": round(statistics.median(data), 2),
                "p95": round(percentile(data, 0.95), 2),
                "min": round(min(data), 2),
                "max": round(max(data), 2),
            }
        print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
