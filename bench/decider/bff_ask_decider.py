"""배포된 BFF의 ask_decider를 BFF 파드 안에서 직접 불러, 질문 세 개를 담은 요청 하나의 시간과 결정을 본다.

    kubectl -n app exec -i <bff 파드> -- python - < bench/decider/bff_ask_decider.py > bff-ask-decider.jsonl

요청은 게이트웨이의 /decide로 간다. 모델(Gemma, Qwen)은 부르지 않는다. 같은 요청 열 개를 두 번 돈다.
"""
import asyncio
import dataclasses
import json
import time

import aiohttp

import bff

STATES = ["지난주에 주문한 운동화가 아직 안 왔어요. 주문 번호는 A-1024입니다. 언제 도착하나요?", "이 상품 설명을 영어와 일본어로 번역해 주세요. 가볍고 통기성이 좋은 여름용 러닝화입니다.", "첨부한 영수증 사진에서 결제 금액과 결제일을 뽑아 주세요.", "주문 내역을 조회하는 파이썬 함수에서 날짜 필터가 동작하지 않습니다. 코드를 고쳐 주세요.", "홍길동입니다. 연락처는 010-1234-5678이고 배송지를 서울시 강남구 테헤란로 1로 바꿔 주세요.", "최근 한 달 리뷰 200건을 장점과 단점으로 나눠 세 줄로 요약해 주세요.", "환불 규정이 어떻게 되나요? 포장을 뜯은 상품도 반품이 되나요?", "세 가지 요금제 중 한 달에 15건을 주문하는 저에게 가장 싼 것은 무엇인지 계산해 주세요.", "상품 상세 이미지에서 색상, 소재, 사이즈 표를 표로 정리해 주세요.", "안녕하세요. 영업시간이 어떻게 되나요?"]


async def main():
    async with aiohttp.ClientSession() as http:
        for round_ in (1, 2):
            for index, state in enumerate(STATES):
                started = time.monotonic()
                decision = await bff.ask_decider(http, state)
                ms = (time.monotonic() - started) * 1000
                print(json.dumps({"round": round_, "index": index, "ms": round(ms, 1),
                                  "decision": dataclasses.asdict(decision)}, ensure_ascii=False), flush=True)


asyncio.run(main())
