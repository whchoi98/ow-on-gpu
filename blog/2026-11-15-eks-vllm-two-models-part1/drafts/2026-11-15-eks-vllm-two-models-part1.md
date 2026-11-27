---
title: "OpenWeight on AWS GPU 1부: Amazon EKS와 vLLM의 LLM API 호출 8개 단계"
date: 2026-11-15
author: "Woohyung Choi"
status: draft
---

# OpenWeight on AWS GPU 1부: Amazon EKS와 vLLM의 LLM API 호출 8개 단계

by WOO HYUNG CHOI on 15 11월 2026 in [Advanced (300)](https://aws.amazon.com/ko/blogs/tech/category/learning-levels/advanced-300/), [Amazon Elastic Kubernetes Service](https://aws.amazon.com/ko/blogs/tech/category/compute/amazon-kubernetes-service/), [Generative AI](https://aws.amazon.com/ko/blogs/tech/category/artificial-intelligence/generative-ai/)

관리형 LLM API를 호출하면 요청 한 건과 응답 한 건만 보입니다. 오픈 웨이트 모델(가중치가 공개되어 내려받아 직접 실행할 수 있는 모델)을 GPU 인스턴스에서 직접 서빙하면 그 사이의 모든 단계가 내 환경 안에 놓입니다. 인증, 모델 선택, 토큰화, 추론, 응답 전달, 관측을 직접 구성해야 하고 응답이 느리거나 실패하면 어느 단계의 문제인지도 직접 찾아야 합니다. 이 글은 LLM API 호출 한 건을 8개 단계로 나누고 단계마다 어떤 구성 요소가 그 일을 하는지, 시간이 얼마나 걸리는지 설명합니다. 예제 환경에서 사용자가 첫 내용을 받기까지의 시간은 Gemma 4 31B가 81.9ms, Qwen3.8-27B가 177.5ms였고 그 가운데 77%와 83%를 추론 엔진이 사용했습니다.

이 글은 OpenWeight on AWS GPU(OW on GPU) 시리즈의 1부입니다. 이 시리즈는 오픈 웨이트 모델 서빙을 처음 시작하는 분을 위한 안내서입니다. 예제 환경은 Amazon Elastic Kubernetes Service(Amazon EKS)에서 vLLM으로 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙합니다. 코드는 [ow-on-gpu 저장소](https://github.com/whchoi98/ow-on-gpu)에 있습니다. 2부(TODO: Part 2 링크)는 두 모델을 서빙하는 구조와 Amazon EKS 최적화를, 3부(TODO: Part 3 링크)는 이 환경을 10개 단계로 만드는 구축 과정을 다룹니다. 이 글은 Kubernetes와 AWS의 기본 개념을 알고 LLM 서빙은 처음인 플랫폼 엔지니어와 개발자를 대상으로 하며 OpenAI 호환 API를 호출해 본 경험이 있다면 무리 없이 읽을 수 있습니다. 본문의 값은 2026년 11월 14일부터 24일 사이에 서울 리전(ap-northeast-2)에서 측정했고 날짜와 횟수는 표와 문장마다 적었습니다.

![LLM API 호출 한 건이 지나는 8개 단계를 한 장에 모은 인포그래픽. API Gateway, Load Balancer, Tokenization, Model Router, Inference Engine, Post-processing, Response and Billing, Logging and Observability의 순서로 단계마다 이 환경의 구성 요소와 측정값을 적었고 첫 내용까지의 시간은 Gemma 4 31B 81.9ms와 Qwen3.8-27B 177.5ms이며 그 가운데 77%에서 83%를 vLLM이 사용했음을 오른쪽 위의 막대로 보여 준다](images/2026-11-15-eks-vllm-two-models-part1-fig01-llm-api-call.png)

*그림 1. LLM API 호출 한 건이 지나는 8개 단계. 단계마다 이 환경에서 그 일을 하는 구성 요소와 측정값을 적었습니다. 왼쪽 아래의 Web Search 도구는 요청이 켰을 때만 지나는 선택 경로입니다.*

## 1. 요청 한 건과 응답 한 건

이 환경의 API는 OpenAI 호환 형식의 `POST /v1/chat/completions` 하나입니다. 요청을 받는 곳은 BFF(Backend for Frontend)입니다. BFF는 화면과 모델 사이에서 인증, 모델 결정, 도구 실행을 맡는 서비스이고 이 환경에서는 Amazon EKS의 파드로 실행합니다. 아래 요청을 그대로 보내면 응답 헤더와 스트리밍 응답이 함께 출력됩니다.

```bash
# APP_URL: terraform -chdir=infra/terraform output -raw app_url 의 출력
# ACCESS_TOKEN: Amazon Cognito 사용자 풀이 발급한 액세스 토큰
curl -sN -D - "$APP_URL/v1/chat/completions" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -H "x-session-id: guide-001" \
  -H "x-task: support" \
  -d '{
    "messages": [{"role": "user", "content": "반품은 며칠 안에 신청해야 하나요?"}],
    "stream": true,
    "stream_options": {"include_usage": true},
    "max_tokens": 128
  }'
```

액세스 토큰은 Cognito의 `InitiateAuth`(`USER_PASSWORD_AUTH` 흐름)로 받습니다. 저장소의 `bench/bff/stream_check.py`는 로그인부터 스트리밍 확인까지 한 번에 실행합니다. 본문에는 `model`을 적지 않습니다. 어느 모델로 보낼지는 BFF가 정하고 요청은 헤더로 힌트만 줍니다.

| 요청 헤더 | 값 | 뜻 |
|---|---|---|
| `x-session-id` | 문자열 | 같은 값이면 첫 요청에서 정한 모델을 30분 동안 다시 사용 |
| `x-task` | `support`, `translate`, `summarize`, `vision`, `ocr`, `coding` | 업무 종류. 있으면 Decider 12B를 거치지 않고 배정표로 모델을 정함 |
| `x-priority` | `interactive`, `batch` | 우선순위. 없으면 업무 종류의 기본값 |
| `x-web-search` | `on` | 웹 검색 도구를 추가 |

*표 1. 모델 결정과 도구에 영향을 주는 요청 헤더. 전체 목록은 저장소의 `docs/api-reference.md`에 있습니다.*

응답은 헤더와 SSE(Server-Sent Events, 서버가 한 연결로 이벤트를 차례로 보내는 방식) 본문으로 옵니다.

```text
# 응답 헤더 (일부, 숫자 자리는 요청마다 다른 값)
x-request-id: <요청 ID>
x-bff-model: gemma-4-31b
x-bff-decision: task
x-bff-sensitive: false
x-bff-thinking: false
x-bff-search: off
x-bff-reason: {"task":"support","cached":false}
x-bff-timing: {"decide_ms":<ms>,"wake_ms":<ms>,"upstream_ms":<ms>,"woke":false,"tools":true}

# 응답 본문 (SSE)
data: {"choices":[{"delta":{"content":"..."}}]}
data: {"choices":[{"delta":{"content":"..."}}]}
data: {"choices":[],"usage":{"prompt_tokens":<입력>,"completion_tokens":<출력>}}
data: [DONE]
```

`x-bff-`로 시작하는 헤더는 이 요청이 어느 경로를 지났는지를 알려 줍니다. 이 글을 다 읽으면 표 2의 값을 보고 요청이 지난 경로와 시간이 쓰인 곳을 읽을 수 있습니다.

| 응답 헤더 | 값 | 알려 주는 것 |
|---|---|---|
| `x-bff-model` | `gemma-4-31b`, `qwen38-27b` | 요청을 받은 모델 |
| `x-bff-decision` | `rule`, `task`, `attachment`, `decider`, `fallback`, `eval` | 무엇으로 모델을 정했는지 |
| `x-bff-sensitive`, `x-bff-thinking` | `true`, `false` | 민감 정보 요청으로 다뤘는지, thinking을 켰는지 |
| `x-bff-search` | `on`, `off`, `sensitive`, `fallback`, `disabled` | 웹 검색 도구를 넣었는지, 넣지 않았다면 그 이유 |
| `x-bff-reason` | JSON | 결정의 근거. 적용한 규칙, Decider 12B의 선택과 신뢰도 |
| `x-bff-timing` | JSON | BFF 안의 구간 시간. 판단(`decide_ms`), 깨우기(`wake_ms`), 게이트웨이의 응답 헤더까지(`upstream_ms`) |

*표 2. BFF가 응답에 넣는 헤더*

## 2. 8개 단계와 단계별 구성 요소

LLM API 호출은 어느 환경에서나 비슷한 단계를 지납니다. 이 글은 그 단계를 8개로 나누고 이 환경에서 각 단계를 맡는 구성 요소를 표 3과 같이 대응시켰습니다.

| 단계 | 하는 일 | 이 환경의 구성 요소 |
|---|---|---|
| 1 API Gateway (요청 진입) | 암호화된 연결 수신, 호출 횟수 제한, 인증, 본문 검증 | Amazon CloudFront, AWS WAF, Amazon Cognito, BFF |
| 2 Load Balancer (부하 분산) | 요청을 받을 대상에게 나눠 보냄 | 내부 Application Load Balancer(ALB), 게이트웨이(agentgateway) |
| 3 Tokenization (토큰화) | 문장을 토큰 ID로 바꾸고 길이를 확인 | vLLM API 서버 |
| 4 Model Router (모델 결정) | 어느 모델의 어느 파드가 처리할지 결정 | BFF, Strands Decider 12B, InferencePool과 EPP, 깨우기 API |
| 5 Inference Engine (추론) | 토큰 생성 | vLLM v0.33.0, 모델마다 NVIDIA L40S 1장 |
| 6 Post-processing (후처리) | 토큰을 텍스트로 복원, 추론 과정과 도구 호출 분리, 도구 실행 | vLLM의 parser, BFF, Amazon Bedrock AgentCore Web Search |
| 7 Response & Billing (응답과 비용) | 응답 전달, 사용량 집계 | BFF의 SSE 전달, `usage`, 응답 헤더 |
| 8 Logging & Observability (기록과 관측) | 구간별 기록과 지표 수집 | Prometheus agent, Amazon Managed Service for Prometheus, BFF 로그, ALB 접근 로그 |

*표 3. LLM API 호출의 8개 단계와 이 환경의 구성 요소*

이 환경에서는 4단계가 3단계보다 먼저 실행됩니다. BFF와 게이트웨이는 토큰화하지 않고 헤더와 원문 텍스트만 보고 모델을 정합니다. 토큰화는 모델마다 다른 토크나이저로 하는 일이어서 모델이 정해진 뒤 그 모델의 vLLM 파드 안에서 일어납니다.

요청이 지나는 순서는 CloudFront, 내부 ALB, BFF, 게이트웨이, vLLM입니다. 인터넷에 열린 곳은 CloudFront 하나이고 그 뒤의 구성 요소는 모두 VPC 안에 있습니다. 각 구성 요소를 어디에 어떻게 배치했는지는 2부(TODO: Part 2 링크)에서 다룹니다.

## 3. 요청 진입과 부하 분산 (1, 2단계)

1단계는 요청을 받아도 되는지 확인하는 단계입니다. 확인은 CloudFront, AWS WAF, Cognito, BFF가 나눠 합니다.

- CloudFront는 HTTPS 요청을 받아 `/v1/*` 경로만 VPC origin을 거쳐 내부 ALB로 보냅니다. 나머지 경로는 Amazon S3의 정적 페이지입니다.
- AWS WAF는 IP 하나의 요청이 5분에 300회를 넘으면 403으로 차단합니다.
- Cognito는 로그인한 사용자에게 액세스 토큰을 발급합니다. 유효 시간은 60분이고 사용자 풀의 가입은 막아 두었습니다.
- BFF는 사용자 풀의 공개 키로 토큰의 RS256 서명을 확인하고 발급자, 만료 시각, `token_use`, 앱 클라이언트 ID를 확인합니다.

인증은 BFF가 맡으므로 로그인하지 않은 요청도 CloudFront와 ALB를 지나 BFF까지 도달한 뒤 401을 받습니다. 그 앞에서 막는 장치는 AWS WAF의 속도 기반 규칙 하나입니다. 이 규칙은 한도를 넘는 순간에 바로 작동하지 않습니다. 2026년 11월 14일에 정적 페이지로 0.5초 동안 400번을 요청했을 때 400번이 모두 200이었습니다. 첫 403은 요청을 시작하고 25.6초 뒤에 나왔고 차단은 그로부터 300.4초 뒤에 풀렸습니다. [AWS WAF 문서](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)도 속도 기반 규칙이 정밀한 요청 수 제한용이 아니라고 설명합니다.

오류 코드를 보면 요청이 어디까지 갔는지 알 수 있습니다.

| 코드 | 돌려주는 곳 | 상황 |
|---|---|---|
| 403 | AWS WAF | 그 IP가 속도 제한에 걸림. BFF에 닿지 않음 |
| 401 | BFF | 토큰이 없거나 서명, 발급자, 만료 시각 확인에 실패. ID 토큰은 받지 않음 |
| 400 | BFF | 본문이 JSON이 아니거나 `messages`가 없음 |
| 422 | BFF | 민감 정보가 있는 요청에 이미지가 있음 |
| 502 | BFF | 잠든 Qwen3.8-27B를 깨우지 못함 |
| 429 | 게이트웨이 | 모델의 풀이 포화된 동안 들어온 배치 요청 |

*표 4. 오류 코드와 그 코드를 돌려주는 위치*

2단계는 요청을 받을 대상에게 나눠 보내는 단계이고 두 번 일어납니다. 내부 ALB는 요청을 BFF 파드 2개에 나눕니다. BFF는 세션의 결정을 파드의 메모리에 보관하므로 같은 브라우저의 요청이 같은 파드로 가도록 ALB에 쿠키 고정(1,800초)을 설정했습니다. BFF는 게이트웨이를 클러스터 안의 Service로 직접 호출하고 게이트웨이 파드 2개가 요청을 모델별 풀로 보냅니다. GPU 부하를 보고 파드를 고르는 일은 4단계에서 설명할 EPP가 합니다.

두 단계가 사용한 시간은 짧습니다. 2026년 11월 15일의 측정에서 중앙값은 사용자와 엣지 사이 1.8ms, CloudFront 5.0ms, ALB 1.6ms였습니다.

## 4. 모델 결정 (4단계)

모델이 두 개이므로 요청마다 어느 모델이 처리할지 정해야 합니다. 이 환경에서는 BFF가 요청의 내용과 정책을 보고 모델을 정하고 게이트웨이는 BFF가 적은 값만 보고 모델의 풀을 고릅니다.

![요청 하나의 모델이 정해지는 순서를 3개 부분으로 나눠 그린 인포그래픽. BFF는 민감 정보 규칙, 업무 종류, 이미지 첨부, Decider 12B의 판단, 기본값의 순서로 먼저 맞는 규칙을 적용하고 Decider 12B는 모델 선택과 개인정보 여부와 추론 필요 여부를 신뢰도와 함께 돌려주며 결정된 값은 본문의 model과 priority, 헤더로 게이트웨이에 전달되어 InferencePool과 EPP를 거쳐 vLLM 파드에 도착한다](images/2026-11-15-eks-vllm-two-models-part1-fig02-model-decision.png)

*그림 2. 모델 결정 순서. BFF의 결정 순서, Decider 12B의 판단과 기준값, 결정이 게이트웨이와 엔진으로 전달되는 경로를 나눠 그렸습니다.*

### 4.1 BFF의 결정 순서

BFF는 비용이 거의 없는 규칙을 먼저 적용하고 규칙으로 정해지지 않는 요청만 판단 모델에 묻습니다. 표 5의 순서로 먼저 맞는 규칙 하나를 적용합니다.

| 순서 | 조건 | 결정 | `x-bff-decision` |
|---|---|---|---|
| 1 | 주민등록번호나 카드번호 형식이 있음 | Gemma 4 31B, 민감 정보 요청으로 표시 | `rule` |
| 2 | 업무 종류(`x-task`)가 있음 | 상담, 번역, 요약은 Gemma 4 31B, 이미지 이해, OCR, 코딩은 Qwen3.8-27B | `task` |
| 3 | 이미지가 첨부됨 | Qwen3.8-27B | `attachment` |
| 4 | Decider 12B의 판단이 기준 이상 | Decider 12B가 고른 모델 | `decider` |
| 5 | 그 밖의 경우 | Gemma 4 31B, thinking 끔 | `fallback` |

*표 5. BFF의 모델 결정 순서와 응답 헤더의 값*

첫 번째 규칙이 맨 앞에 있는 이유는 이 환경의 데이터 정책 때문입니다. 민감 정보가 든 요청은 Gemma 4 31B로만 보내도록 정했고 형식이 정해진 민감 정보는 판단 모델에 맡기지 않고 정규식과 Luhn 검사로 찾습니다. Gemma 4 31B는 이 구성에서 이미지를 받지 않으므로 민감 정보와 이미지가 함께 온 요청은 422로 거절합니다.

한 번 정한 결과는 세션(`x-session-id`)에 30분 동안 저장해 다시 사용합니다. 대화의 두 번째 메시지부터는 판단 시간이 더해지지 않습니다. 민감 정보 형식만은 세션에 결정이 있어도 메시지마다 다시 확인하고 대화 도중에 나오면 그 뒤로는 Gemma 4 31B로만 보냅니다.

### 4.2 Decider 12B의 판단

[Strands Decider](https://github.com/strands-labs/strands-decider) 12B는 요청을 읽고 어느 모델이 맡을지를 판단하는 모델입니다. 글을 생성하지 않고 선택지 가운데 하나와 신뢰도, 또는 예일 확률을 돌려줍니다. 2026년 11월 23일에 발표된 [Strands Decider v2](https://strandsagents.com/blog/introducing-strands-decider-v2/)의 체크포인트 5개 가운데 하나이고 이 환경에서는 g6e.xlarge(NVIDIA L40S) 노드 한 대에서 실행합니다. 이 환경은 2026년 11월 24일에 v1의 2B 모델에서 이 모델로 바꿨고 아래의 답과 시간은 바꾼 뒤에 측정한 값입니다. BFF는 규칙으로 정해지지 않은 요청에만 질문 3개를 한 번에 보냅니다.

```python
# app/bff/bff.py에서 발췌
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
```

BFF는 답을 기준값 0.6과 비교합니다. `route`는 선택의 신뢰도를 그대로 보고 `policy`는 확률이 0.5에서 떨어진 정도를 신뢰도로 봅니다.

| Decider 12B의 답 | BFF의 처리 | 응답 헤더 |
|---|---|---|
| 모델 선택과 개인정보 판단의 신뢰도가 모두 0.6 이상 | Decider 12B가 고른 모델. 개인정보가 있다고 보면 Gemma 4 31B와 민감 표시. thinking은 확률 0.5 이상이면 켬 | `decider` |
| 모델 선택의 신뢰도만 0.6 미만이고 개인정보가 없다는 판단은 0.6 이상 | Gemma 4 31B, thinking 끔. 민감 정보 요청으로 다루지 않음 | `fallback`, `x-bff-sensitive: false` |
| 응답 없음, 2초 초과, 개인정보 판단의 신뢰도가 0.6 미만, 개인정보가 있다는 판단 | Gemma 4 31B, thinking 끔, 민감 정보 요청으로 다룸 | `fallback`, `x-bff-sensitive: true` |

*표 6. Decider 12B의 답에 따른 BFF의 처리(2026년 11월 17일부터의 동작)*

기본값이 둘로 나뉜 이유는 일반 질문에 있습니다. 상담도 코딩도 아닌 일반 질문은 두 선택지 어디에도 뚜렷이 들지 않아 모델 선택의 신뢰도가 낮게 나옵니다. 그 이유만으로 민감 정보 요청이 되면 뒤에서 설명할 웹 검색 도구가 빠지므로 개인정보가 없다는 판단을 얻은 요청은 민감 정보 요청으로 다루지 않게 했습니다.

| 요청 | 모델 선택 (신뢰도) | 개인정보일 확률 | 추론이 필요할 확률 |
|---|---|---:|---:|
| 주문한 운동화 배송 문의 | gemma (1.00) | 0.04 | 0.42 |
| 파이썬 함수 수정 | qwen (0.97) | 0.00 | 0.76 |
| 이름, 연락처, 주소가 든 배송지 변경 | gemma (0.99) | 1.00 | 0.11 |
| 요금제 비교 계산 | gemma (0.40) | 0.00 | 0.84 |

*표 7. Decider 12B에 직접 보낸 예시 요청의 답(2026년 11월 24일, 요청마다 한 번). 정확도를 평가한 값은 아닙니다.*

표 7의 네 번째 요청은 모델 선택의 신뢰도가 0.40이어서 기본값으로 처리되고, 개인정보가 없다는 판단은 기준을 넘으므로 민감 정보 요청으로 다뤄지지 않습니다. 세 번째 요청은 개인정보가 있다는 판단에 따라 Gemma 4 31B로 가고 민감 정보 요청으로 표시됩니다.

판단에 걸리는 시간은 질문 하나에 약 89ms입니다. 게이트웨이를 거쳐 질문을 하나씩 50회 보낸 중앙값은 89.7ms에서 90.6ms였습니다(2026년 11월 24일). BFF 파드에서 질문 3개를 한 요청에 담아 보낸 왕복은 143.8ms에서 159.9ms였습니다(2026년 11월 24일, 20건). 세션의 첫 요청에서 한 번만 묻기 때문에 이 시간은 메시지마다 더해지지 않습니다. 업무 종류를 헤더로 보낸 요청의 판단 시간은 중앙값 0.1ms였습니다(2026년 11월 15일, 모델마다 20건).

### 4.3 게이트웨이의 풀 선택과 Qwen3.8-27B 깨우기

결정이 나면 BFF는 그 결과를 요청에 적어 게이트웨이로 보냅니다. 본문의 `model`과 `priority`, `chat_template_kwargs.enable_thinking`, 그리고 헤더 `x-llm-d-inference-objective`입니다.

```text
# BFF가 게이트웨이로 보내는 요청 (발췌)
x-llm-d-inference-objective: gemma-interactive

{"model": "gemma-4-31b", "priority": 0, "chat_template_kwargs": {"enable_thinking": false}, "messages": [...], "stream": true}
```

게이트웨이 계층은 [Gateway API Inference Extension](https://gateway-api-inference-extension.sigs.k8s.io/)(GAIE)으로 구성했습니다. GAIE는 Kubernetes Gateway API에 추론용 리소스를 더하는 프로젝트입니다. InferencePool은 모델 서버 파드의 묶음이고 EPP(Endpoint Picker)는 풀 안에서 요청을 받을 파드를 고릅니다. OpenAI 호환 API에서 모델 이름은 URL이 아닌 본문에 있으므로 게이트웨이 구현체인 agentgateway가 본문의 `model` 값을 헤더로 옮깁니다. HTTPRoute는 그 헤더로 모델의 InferencePool을 고릅니다. 등록하지 않은 `model` 값은 404입니다. 모델의 풀로 가는 경로는 `/v1/chat/completions`와 `/v1/models`뿐이어서 `/sleep` 같은 관리 경로는 게이트웨이로 노출되지 않습니다. EPP의 스케줄링 시간은 요청당 0.03ms였습니다(2026년 11월 14일).

우선순위는 두 곳에 전달됩니다. 헤더의 objective 이름은 게이트웨이가 풀이 포화됐을 때 배치 요청을 거절하는 데 사용하고 본문의 `priority`는 vLLM이 대기열에서 먼저 처리할 요청을 고르는 데 사용합니다. 배치 부하가 걸린 상태에서 상담 요청의 TTFT 중앙값은 30.9초였고 엔진 우선순위를 켜자 0.19초가 됐습니다(2026년 11월 14일, Gemma 4 31B). 구성과 측정은 2부(TODO: Part 2 링크)에서 설명합니다.

Qwen3.8-27B로 가는 요청에는 한 가지 일이 더 있습니다. 내부 업무용인 Qwen3.8-27B는 업무 시간 밖에는 vLLM의 sleep mode로 재우도록 구성했습니다. 그래서 BFF는 Qwen 요청마다 깨우기 API를 먼저 호출합니다. 깨어 있을 때는 확인만 하고 중앙값 12.8ms가 걸렸습니다(2026년 11월 15일, 20건). 잠들어 있을 때는 깨우기에 3,662ms가 걸렸고 그 요청의 첫 내용은 4.06초에 도착했습니다(같은 날, 1건). 응답 헤더 `x-bff-timing`의 `woke`와 `wake_ms`가 이 값입니다.

## 5. 토큰화와 추론 (3, 5단계)

모델이 정해지면 요청은 그 모델의 vLLM 파드에 도착합니다. 3단계에서 vLLM의 API 서버는 메시지 목록에 chat template을 적용해 하나의 문자열로 만들고 그 모델의 토크나이저로 토큰 ID로 바꿉니다. 입력과 출력을 합친 길이의 한도는 `--max-model-len`이고 Gemma 4 31B는 16,384토큰, Qwen3.8-27B는 32,768토큰으로 설정했습니다. 토큰화에 걸린 시간은 따로 측정하지 않았습니다.

5단계의 추론은 2개 구간으로 나뉩니다.

- Prefill: 입력 토큰 전체를 한 번에 계산하고 결과를 KV 캐시에 기록합니다. KV 캐시는 이미 계산한 토큰의 중간 결과를 GPU 메모리에 보관해 다음 토큰을 만들 때 다시 계산하지 않게 하는 저장 공간입니다.
- Decode: KV 캐시를 다시 사용하면서 토큰을 하나씩 만듭니다. 만든 토큰은 바로 Chunk로 나갑니다.

2개 구간은 각각 다른 지표로 드러납니다. TTFT(Time To First Token)는 첫 토큰까지의 시간이고 대부분 Prefill입니다. ITL(Inter-Token Latency)은 스트리밍 Chunk 사이의 간격이고 Decode의 속도입니다. TPOT(Time Per Output Token)은 출력 토큰 하나당 시간입니다.

| 지표 | Gemma 4 31B | Qwen3.8-27B |
|---|---:|---:|
| TTFT 중앙값 (p99) | 81.3ms (86.6ms) | 167.6ms (210.4ms) |
| ITL 중앙값 (p99) | 54.0ms (57.7ms) | 69.8ms (74.3ms) |
| TPOT 중앙값 | 53.9ms | 26.6ms |
| 생성 속도 | 초당 18.5토큰 | 초당 32.5토큰 |
| 128토큰 응답의 전체 시간 | 6,927.8ms | 3,554.7ms |

*표 8. 요청 하나의 추론 시간(2026년 11월 14일, 입력 256토큰과 출력 128토큰, 동시성 1, vLLM의 Service를 직접 호출한 요청 16건을 한 번 실행한 값)*

응답 하나의 전체 시간은 두 지표로 계산됩니다. Gemma 4 31B의 값을 넣으면 측정한 6,927.8ms와 맞습니다.

```text
전체 시간 ≒ TTFT + (출력 토큰 수 - 1) × TPOT
          = 81.3ms + 127 × 53.91ms ≒ 6,928ms
```

출력이 길수록 전체 시간은 Decode가 정합니다. 입력이 길면 TTFT가 늘어납니다. Gemma 4 31B의 TTFT p99는 입력 256토큰에서 86.6ms, 4,096토큰에서 1,093ms였습니다.

Qwen3.8-27B는 ITL이 더 긴데도 생성 속도가 빠릅니다. Qwen3.8-27B는 다음 토큰 여러 개를 미리 추측하는 MTP(Multi-Token Prediction)를 켜 두어 Chunk 하나에 여러 토큰이 담겨 옵니다. 그래서 Chunk 간격은 69.8ms이고 토큰 하나당 시간은 26.6ms입니다.

한 GPU가 동시에 실행하는 요청 수는 KV 캐시 크기에 묶입니다. L40S의 GPU 메모리에서 가중치를 올리고 남은 공간이 KV 캐시가 됩니다. 표 8과 같은 워크로드로 동시성을 올렸을 때 Gemma 4 31B는 45건, Qwen3.8-27B는 3건까지 동시에 실행했습니다. 이 한도의 원인과 조정 방법은 2부(TODO: Part 2 링크)에서 다룹니다.

## 6. 후처리와 Web Search (6단계)

### 6.1 텍스트 복원과 parser

vLLM은 생성한 토큰 ID를 텍스트로 되돌리고(Detokenize) 두 가지를 답변에서 분리합니다. Reasoning parser는 추론 과정을 `reasoning_content`로 분리하고 Tool-call parser는 도구 호출을 `tool_calls`로 추출합니다. Gemma 4 31B는 `gemma4`, Qwen3.8-27B는 `qwen3`과 `qwen3_coder` parser를 사용합니다. 스트리밍 중에는 이 처리가 Chunk마다 함께 진행됩니다. 응답의 `finish_reason`이 `tool_calls`이면 모델이 답변 대신 도구 실행을 요청했다는 뜻입니다. 출력 안전 필터는 이 환경에 두지 않았습니다.

### 6.2 Web Search 도구의 흐름

웹 검색은 8개 단계 가운데 하나가 아닙니다. 요청이 켰을 때만 6단계에서 5단계로 다시 가는 선택 경로입니다. 추론은 그대로 Gemma 4 31B와 Qwen3.8-27B가 하고 검색만 [Amazon Bedrock AgentCore Web Search](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)가 맡습니다.

![웹 검색 도구가 실행되는 순서를 브라우저, BFF, 모델, AgentCore Web Search의 4개 줄로 그린 인포그래픽. 요청이 x-web-search: on을 보내면 BFF가 도구 정의와 지시문을 넣고 모델이 web_search를 호출하면 BFF가 us-east-1의 InvokeWebSearch를 실행해 결과 5건에 출처 번호를 매겨 돌려주며 모델이 번호를 넣어 답하면 화면이 출처 목록을 함께 표시한다. 도구를 넣는 조건과 검색 시간, 입력 토큰, 요금을 함께 적었다](images/2026-11-15-eks-vllm-two-models-part1-fig03-web-search-flow.png)

*그림 3. Web Search 도구의 흐름. 왼쪽은 도구를 넣는 조건과 측정값이고 오른쪽은 한 요청 안에서 일어나는 순서입니다.*

1. 요청이 `x-web-search: on` 헤더를 보내면 BFF가 모델 요청에 `web_search` 도구 정의와 지시문(오늘 날짜, 출처 번호 규칙)을 넣습니다.
2. 검색할지와 무엇을 검색할지는 모델이 정합니다. 모델이 `web_search(query)`를 호출하면 그 응답은 `finish_reason: tool_calls`로 끝납니다.
3. BFF가 `InvokeWebSearch` API를 호출합니다. 검색어에 주민등록번호나 카드번호 형식이 있으면 그 검색은 보내지 않습니다.
4. BFF가 결과 5건에 출처 번호를 매기고 본문을 1,200자까지 잘라 모델에 돌려줍니다. 주소가 없는 결과는 버립니다.
5. 모델이 결과를 읽고 `[1]`, `[2]` 같은 번호를 넣어 답합니다. 엔진은 결과가 더해진 요청을 Prefill부터 다시 처리합니다.
6. 모델이 도구를 호출할 수 있는 차례는 3번입니다. 세 번째 뒤에는 BFF가 `tool_choice: none`으로 보내 그때까지의 결과로 답하게 합니다.

BFF는 검색할 때마다 SSE 주석 줄로 검색어와 출처 목록을 알립니다. OpenAI 형식의 클라이언트는 주석 줄을 무시하고 확인용 페이지는 이 목록을 답변 아래에 링크로 표시합니다. 이용 조건이 검색 결과를 사용한 출력에 출처와 링크를 표시하도록 요구하므로 모델이 번호를 빠뜨려도 목록은 항상 보이게 했습니다.

```text
: bff {"event":"tool_call","name":"web_search","ms":<ms>,"query":"...","search_ms":<ms>,"sources":[{"n":1,"title":"...","url":"https://...","published_at":"..."}]}
```

도구를 넣을지는 표 9의 조건으로 정하고 결과는 응답 헤더 `x-bff-search`에 담깁니다.

| `x-bff-search` | 뜻 |
|---|---|
| `on` | 모델 요청에 웹 검색 도구를 넣음 |
| `off` | 요청이 켜지 않았거나, 성능 평가 요청이거나, 요청이 자기 `tools`를 가져옴 |
| `sensitive` | 민감 정보 요청이라 넣지 않음 |
| `fallback` | 기본값으로 보낸 요청 가운데 개인정보가 없다는 판단을 얻지 못해 넣지 않음 |
| `disabled` | 이 환경에 웹 검색이 설정되지 않음 |

*표 9. 응답 헤더 `x-bff-search`의 값*

민감 정보 요청에 도구를 넣지 않는 이유는 리전에 있습니다. 이 API는 서울 리전에서 제공되지 않아 BFF가 us-east-1의 API를 호출하고 검색어는 서울 리전 밖으로 나갑니다. 호출 권한은 BFF 파드에 EKS Pod Identity로 연결한 IAM 역할에 `bedrock-agentcore:InvokeWebSearch` 하나만 주었고 자격 증명은 코드에 없습니다.

| 항목 | 값 | 조건 |
|---|---|---|
| 검색 1회의 시간 (작업 장비에서 호출) | 481ms에서 1,065ms | 서울의 작업 장비에서 us-east-1을 6회 호출 |
| 검색 1회의 시간 (BFF 파드에서 호출) | 547.9ms, 594.9ms | 2026년 11월 17일, 요청 2건 |
| 검색 결과가 더해진 입력 | Gemma 4 31B 2,606토큰, Qwen3.8-27B 4,328토큰 | 각각 검색 1회와 2회, 결과 5건씩 |
| 요금과 기본 할당량 | 쿼리 1,000건당 7.00 USD, 초당 10건 | 계정과 리전 기준 |

*표 10. 웹 검색의 측정값과 한도. 요금은 2026년 11월 15일에 확인한 공개 단가입니다.*

검색을 사용한 요청은 첫 내용이 늦게 도착합니다. 모델이 도구 호출을 생성하는 시간, 검색, 결과를 넣은 두 번째 추론의 Prefill이 모두 첫 내용 앞에 놓이기 때문입니다. 같은 흐름을 Qwen3.8-27B로 직접 실행했을 때 첫 차례는 2.6초, 결과 10건을 읽고 답한 두 번째 차례는 12.1초였습니다.

## 7. 응답과 비용 (7단계)

BFF는 게이트웨이에서 받은 SSE Chunk를 모으지 않고 받은 그대로 전달합니다. 중간에서 응답이 모이면 글자가 한꺼번에 나타나 스트리밍의 의미가 사라집니다. 그래서 CloudFront의 `/v1/*` 동작은 캐시와 압축을 껐습니다. 2026년 11월 15일에 상담 요청 하나를 CloudFront 주소로 보냈을 때 내용이 담긴 이벤트 53개가 간격 중앙값 53.5ms로 하나씩 도착했습니다. 1ms 안에 연달아 온 이벤트는 없었습니다. 이 간격은 표 8의 Gemma 4 31B ITL과 같은 수준입니다.

스트리밍 응답은 첫 토큰 전에 수 초 동안 아무것도 흐르지 않을 수 있고 그 뒤로는 수십 ms 간격으로 Chunk가 이어집니다. 경로의 타임아웃은 이 2개 구간에 맞춰야 합니다.

| 설정 | 값 | 근거 |
|---|---|---|
| CloudFront 오리진 응답 타임아웃 | 60초 (기본 30초) | 첫 바이트까지, 그리고 패킷 사이에 기다리는 시간 |
| ALB 유휴 제한 시간 | 120초 (기본 60초) | CloudFront가 먼저 끊도록 그보다 길게 설정 |
| HTTPRoute의 요청 타임아웃 | 300초 | 4,096토큰 출력이 이 안에 끝남(Gemma 4 31B는 약 3분) |
| Decider 12B 호출 | 2초 | 넘으면 기본값으로 처리 |
| 깨우기 API 호출 | 60초 | 측정한 복귀 시간은 3.66초 |

*표 11. 스트리밍 경로의 타임아웃 설정*

사용량은 응답에 함께 옵니다. 요청에 `stream_options.include_usage`를 넣으면 마지막 Chunk의 `usage`에 입력과 출력 토큰 수가 담깁니다. 다만 이 환경에는 토큰 단가가 없습니다. 비용은 GPU 노드가 떠 있는 시간에 발생하고 이 환경의 고정 비용은 시간당 약 11.35 USD로 추정됩니다. 출력이 길어져도 요금은 늘지 않지만 그 요청이 GPU를 점유하는 시간이 늘어납니다.

## 8. 기록과 관측 (8단계)

요청이 지난 구간마다 기록이 남습니다. 표 12의 기록을 요청 ID(`x-request-id`)와 `X-Amzn-Trace-Id`로 이으면 요청 하나의 구간별 시간을 얻습니다.

| 구간 | 기록 | 확인 방법 |
|---|---|---|
| CloudFront | 응답 헤더 `Server-Timing` | 응답 헤더에서 엣지와 오리진의 시간 확인 |
| 내부 ALB | 접근 로그 | Amazon S3 버킷의 로그 파일 |
| BFF | 파드의 표준 출력 (`chat`, `chat_end` 이벤트) | `kubectl -n app logs -l app.kubernetes.io/name=bff` |
| 게이트웨이, EPP | Prometheus 지표 | Amazon Managed Service for Prometheus |
| vLLM | Prometheus 지표 | `vllm:time_to_first_token_seconds`, `vllm:inter_token_latency_seconds`, `vllm:num_requests_waiting`, `vllm:kv_cache_usage_perc` |

*표 12. 구간별 기록과 확인 방법*

지표는 Prometheus v3.16.0을 agent 모드로 하나 실행해 모읍니다. vLLM 파드 2개는 5초, EPP 파드 4개와 게이트웨이 파드 2개는 15초 주기로 수집해 Amazon Managed Service for Prometheus로 보냅니다.

브라우저나 클라이언트에서 알 수 있는 것과 없는 것은 나뉩니다. 응답 헤더가 도착한 시간, `x-bff-timing`, `Server-Timing`, 첫 Chunk까지의 시간, Chunk 간격, 전체 시간, `usage`는 클라이언트가 직접 봅니다. 대기열, Prefill, 후처리의 시간은 클라이언트에 보이지 않으므로 vLLM 지표로 확인해야 합니다.

## 9. 첫 내용까지의 시간이 쓰이는 곳

8개 단계를 모두 지난 요청에서 구간마다 시간이 얼마나 쓰였는지 측정했습니다. 서울 리전의 Amazon EC2 인스턴스에서 CloudFront 주소로 요청을 하나씩 보냈고 모델마다 20건입니다. Gemma 4 31B에는 상담 업무의 짧은 질문을, Qwen3.8-27B에는 코딩 업무의 짧은 질문을 보냈습니다.

| 구간 | Gemma 4 31B 중앙값 | Gemma 4 31B 최대 | Qwen3.8-27B 중앙값 | Qwen3.8-27B 최대 |
|---|---:|---:|---:|---:|
| 사용자와 엣지 사이 | 1.8ms | 3.2ms | 1.9ms | 5.0ms |
| CloudFront | 5.0ms | 79.0ms | 5.0ms | 9.0ms |
| ALB | 1.6ms | 4.2ms | 1.6ms | 12.7ms |
| BFF | 0.1ms | 0.1ms | 12.8ms | 21.9ms |
| 게이트웨이 (agentgateway, EPP) | 9.7ms | 16.4ms | 8.4ms | 78.0ms |
| vLLM | 63.2ms | 66.6ms | 147.6ms | 160.0ms |
| 사용자가 본 첫 내용 | 81.9ms | 153.6ms | 177.5ms | 253.1ms |

*표 13. 구간별 첫 내용까지의 시간(2026년 11월 15일, 요청을 하나씩, 모델마다 20건, 최대 출력 32토큰). 구간별 중앙값이므로 합이 마지막 행과 정확히 일치하지 않습니다.*

첫 내용까지의 시간은 대부분 vLLM이 사용합니다. Gemma 4 31B는 81.9ms 중 63.2ms(77%), Qwen3.8-27B는 177.5ms 중 147.6ms(83%)입니다. 그 시간은 거의 다 Prefill입니다. 요청을 하나씩 보냈으므로 대기열 시간은 0ms였고 Prefill이 각각 58.8ms와 144.4ms였습니다.

vLLM 앞의 구간을 중앙값으로 더하면 Gemma 4 31B 18.2ms, Qwen3.8-27B 29.7ms입니다. Qwen 쪽이 긴 것은 BFF가 요청마다 깨우기 API를 호출하기 때문입니다. 인증, 모델 결정, 라우팅을 직접 구성한 계층이 더한 시간은 두 모델 모두 30ms 안쪽이었습니다.

이 표는 3가지 조건에서 측정한 값입니다. 측정 장비가 같은 리전의 인스턴스여서 사용자와 엣지 사이의 시간이 짧습니다. 이미 열린 연결로 보낸 요청이며 TLS 연결을 새로 여는 데는 14.5ms와 14.2ms가 걸렸습니다. 요청을 하나씩 보냈으므로 부하가 걸렸을 때 더해지는 대기 시간은 들어 있지 않습니다.

## 10. 증상별로 먼저 볼 단계

응답이 예상과 다를 때는 응답 헤더를 정해진 순서로 읽으면 살펴볼 단계가 좁혀집니다.

1. 오류 코드가 있으면 표 4에서 요청이 어디까지 갔는지 확인합니다.
2. `x-bff-model`과 `x-bff-decision`으로 어느 모델을 무엇으로 정했는지 확인합니다. `fallback`이면 `x-bff-reason`에 적힌 신뢰도를 봅니다.
3. 웹 검색을 켠 요청이면 `x-bff-search`가 `on`인지 확인합니다.
4. 느린 요청이면 `x-bff-timing`에서 판단, 깨우기, 게이트웨이의 응답 헤더까지의 시간을 나눠 봅니다. 3개 값이 모두 짧다면 남은 시간은 vLLM의 대기열과 Prefill입니다.

증상별로 먼저 볼 곳은 표 14에 모았습니다.

| 증상 | 먼저 볼 곳 | 본문의 근거 |
|---|---|---|
| 한동안 모든 요청이 403 | 1단계의 AWS WAF | IP당 5분 300회. 첫 403까지 25.6초, 해제까지 300.4초 |
| 401 | 1단계의 BFF | 액세스 토큰의 유효 시간 60분. ID 토큰은 받지 않음 |
| 예상과 다른 모델이 응답 | `x-bff-decision`, `x-bff-reason` | 민감 정보 규칙이 업무 종류보다 먼저. 세션의 결정은 30분 동안 재사용 |
| 웹 검색을 켰는데 검색하지 않음 | `x-bff-search` | `sensitive`, `fallback`, `off`의 조건 |
| Qwen3.8-27B의 첫 내용이 수 초 늦음 | `x-bff-timing`의 `woke`, `wake_ms` | 잠든 상태에서 깨우기 3,662ms, 첫 내용 4.06초 |
| 부하가 걸리면 첫 내용이 늦음 | 8단계의 `vllm:num_requests_waiting`, `vllm:kv_cache_usage_perc` | 동시에 실행하는 요청 수는 KV 캐시에 묶임 |
| 글자가 한꺼번에 나타남 | 7단계의 경로 설정 | 캐시와 압축을 끈 경로에서 이벤트 간격 53.5ms |
| 긴 응답이 중간에 끊김 | 7단계의 타임아웃 | CloudFront 60초, ALB 120초, HTTPRoute 300초 |
| 배치 요청이 429 | 4단계의 게이트웨이 | 풀이 포화되면 우선순위가 낮은 요청을 거절 |

*표 14. 증상별로 먼저 볼 단계와 근거*

## 11. 마치며

요청 한 건이 응답으로 돌아오기까지 8개 단계를 지났습니다. 진입과 부하 분산은 CloudFront, AWS WAF, Cognito, 내부 ALB가 맡았습니다. 모델 결정은 BFF의 규칙과 Decider 12B가, 풀과 파드 선택은 게이트웨이와 EPP가 맡았습니다. 토큰화와 추론, 후처리는 vLLM 안에서 일어났고 웹 검색은 BFF가 도구로 실행했습니다. 예제 환경에서 첫 내용까지의 시간은 Gemma 4 31B 81.9ms, Qwen3.8-27B 177.5ms였고 그 가운데 77%와 83%가 추론 엔진의 시간이었습니다.

확인하지 못한 것도 있습니다. 토큰화와 후처리의 시간은 따로 측정하지 않았습니다. 쿠키 고정으로 세션의 결정이 같은 파드에서 다시 사용되는 동작은 설정만 적었고 따로 확인하지 않았습니다. 응답이 60초 넘게 한 글자도 나오지 않는 경우의 동작도 재현하지 않았습니다. 본문의 값은 대부분 한 번씩 측정한 것이어서 반복했을 때의 편차는 담겨 있지 않습니다.

2부(TODO: Part 2 링크)에서는 이 단계들을 맡은 구성 요소가 어떤 구조로 놓여 있는지, Amazon EKS에서 시작 시간과 동시 처리량을 어떻게 조정했는지 살펴봅니다. 이 글의 단계 구분과 표가 여러분의 LLM 서빙 환경에서 요청 경로를 점검하는 데 실질적인 참고가 되기를 바랍니다.

## 참고 자료

- [ow-on-gpu – 예제 환경의 GitHub 저장소](https://github.com/whchoi98/ow-on-gpu)
- [Metrics – vLLM 문서](https://docs.vllm.ai/en/latest/design/metrics/)
- [vllm.config.scheduler – vLLM API 문서](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)
- [Sleep Mode – vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)
- [Introduction – Gateway API Inference Extension 문서](https://gateway-api-inference-extension.sigs.k8s.io/)
- [InferencePool – Gateway API Inference Extension API 문서](https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/)
- [Flow Control – llm-d v1.0.0 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md)
- [Multiple inference pools – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)
- [strands-decider – GitHub 저장소](https://github.com/strands-labs/strands-decider)
- [Search the web using Amazon Bedrock AgentCore Web Search – Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)
- [Introducing the Web Search API on Amazon Bedrock AgentCore – AWS Machine Learning Blog (2026년 11월 11일)](https://aws.amazon.com/ko/blogs/machine-learning/introducing-the-web-search-api-on-amazon-bedrock-agentcore/)
- [Amazon Bedrock AgentCore 요금 – 요금 페이지](https://aws.amazon.com/ko/bedrock/agentcore/pricing/)
- [Restrict access with VPC origins – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Origin settings – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html)
- [Understand response headers policies – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-response-headers-policies.html)
- [Rate-based rule caveats in AWS WAF – AWS WAF Developer Guide](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)
- [Verifying JSON web tokens – Amazon Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
- [Authentication flows – Amazon Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html)
- [Edit target group attributes for your Application Load Balancer – Elastic Load Balancing User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-target-group-attributes.html)
- [Learn how EKS Pod Identity grants pods access to AWS services – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)

*본문의 측정값은 2026년 11월 14일부터 17일 사이에 서울 리전(ap-northeast-2)의 한 환경에서 측정한 값이며 날짜와 횟수는 표와 문장마다 적었습니다. 금액은 2026년 11월 15일에 확인한 공개 단가를 바탕으로 한 세전 USD 추정치이고 최종 금액은 사용량과 요금 변경에 따라 달라질 수 있습니다.*

## 저자 소개

**최우형 (Woohyung Choi)** 님은 AWS Korea의 Principal Solutions Architect로, 국내 주요 엔터프라이즈 및 디지털 기업의 클라우드 전환과 아키텍처 현대화를 지원하고 있습니다. 특히 클라우드 네이티브 아키텍처와 Agentic AI 분야에 전문성을 가지고 있으며, 고객이 Amazon Bedrock을 비롯한 AWS의 생성형 AI 및 Agentic AI 기술을 안정적이고 비용 효율적으로 도입하고 확장할 수 있도록 아키텍처 설계와 기술 자문을 제공하고 있습니다.

컨테이너, 네트워킹, 비용 최적화를 비롯한 클라우드 핵심 기술부터 Agentic AI를 활용한 업무 혁신과 지능형 시스템 구축까지 폭넓은 영역에서 AWS 아키텍처 모범 사례를 제시하고 있습니다. 이를 통해 고객의 복잡한 기술적 과제를 해결하고, AI와 클라우드를 기반으로 지속 가능한 기술 전략을 수립하고 실행할 수 있도록 기술 리더십을 발휘하고 있습니다.
