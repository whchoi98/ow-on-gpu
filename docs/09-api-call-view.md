# API 호출 보기와 인포그래픽

LLM API 호출 한 건이 거치는 여덟 단계를 한 장의 인포그래픽으로 그리고, 웹 앱의 "API 호출" 보기에서 단계마다 이 환경의 어느 구성 요소가 그 일을 하는지 지도에 표시합니다. 웹 검색(Amazon Bedrock AgentCore Web Search)은 그림에 따로 떼어 낸 경로로, 화면에는 6단계의 구성 요소와 실제 요청의 검색 기록, 출처로 넣었습니다. 2026-11-15에 만들었고 배포는 하지 않았습니다.

## 만든 것

| 파일 | 내용 |
|---|---|
| `docs/infographic/apicall.py` | 인포그래픽 본문과 측정값. `landscape()`가 그림을, `web_module()`이 웹 화면이 쓰는 값을 만듭니다 |
| `docs/infographic/build/09-llm-api-call_16x9_{dark,light}.{svg,png}` | 16:9 그림. 검사 이슈는 0건입니다 |
| `app/web/src/ApiCall.jsx`, `apicall.js`, `apicall.css` | "API 호출" 보기. 계산은 `apicall.js`의 순수 함수에 있습니다 |
| `app/web/src/apicall-data.js` | 단계 카드의 위치와 측정값. `apicall.py`가 만들며 직접 고치지 않습니다 |
| `app/web/src/assets/llm-api-call.png` | 보기 아래쪽에 넣는 그림(라이트) |
| `app/web/apicall.test.mjs` | `node apicall.test.mjs`로 실행하는 계산 시험 |

그림과 값은 `docs/infographic/build.sh`의 마지막 부분이 다시 만듭니다. 측정값을 바꿀 때는 `apicall.py`의 `M`만 고칩니다. 그림과 화면이 같은 값을 씁니다.

## 여덟 단계와 이 환경의 구성 요소

단계 구성은 `reference/L300-01-api-journey_16x9_light.png`를 따랐습니다. 내용은 저장소에서 확인한 사실로 다시 썼습니다.

| 단계 | 이 환경에서 그 일을 하는 것 | 지도에서 켜지는 노드 |
|---|---|---|
| 1 API Gateway | CloudFront, AWS WAF, Cognito, BFF의 토큰과 본문 검증 | CloudFront, Cognito, BFF |
| 2 Load Balancer | 내부 ALB(쿠키 고정 30분), agentgateway. 2026-11-15부터 BFF는 게이트웨이의 Service를 직접 불러 NLB를 거치지 않음 | 내부 ALB, 게이트웨이 |
| 3 Tokenization | vLLM API 서버(chat template, tokenizer), `--max-model-len` | 고른 모델 |
| 4 Model Router | BFF의 결정 순서, Decider 2B, InferencePool과 EPP, 깨우기 API, vLLM priority 스케줄러 | BFF, 게이트웨이, Decider, 깨우기 API(Qwen만) |
| 5 Inference Engine | vLLM v0.33.0의 Prefill과 Decode, L40S 48GB | 고른 모델 |
| 6 Post-processing | vLLM의 detokenize, reasoning parser, tool-call parser, BFF의 도구 실행, AgentCore Web Search | 고른 모델, BFF, Web Search(웹 검색을 켰을 때) |
| 7 Response & Billing | BFF가 그대로 흘려보내는 SSE, usage, 응답 헤더. 비용은 GPU 노드 시간 | 브라우저, 돌아오는 선 |
| 8 Logging & Observability | Prometheus agent와 AMP, BFF 로그, ALB 접근 로그, Server-Timing | CloudFront, 내부 ALB, BFF, 게이트웨이, 고른 모델, AMP |

이 환경에서는 4단계가 3단계보다 먼저입니다. BFF와 게이트웨이는 토큰화하지 않고 헤더와 원문 텍스트로 모델을 정하고, 토큰화는 모델 파드 안의 vLLM이 합니다. 그림과 화면에 이 점을 적었습니다.

## 웹 검색

웹 검색은 여덟 단계 가운데 하나가 아니고, 요청이 켰을 때만 6단계에서 5단계로 되돌아가는 경로입니다. 사실 관계는 `docs/10-web-search.md`와 `app/bff/websearch.py`, `app/bff/bff.py`를 따랐습니다.

- **그림**: 왼쪽 아래에 "Web Search 도구"를 점선 테두리의 세로 칸으로 두었습니다. 6번 카드에서 화살표가 들어와 아래에서 위로 도구 실행(BFF), AgentCore Web Search(`InvokeWebSearch`, us-east-1, BFF 파드에 Pod Identity로 연결한 역할의 IAM 권한), 결과 정리(5건에 출처 번호, 본문 1,200자까지), 다시 추론(상한 3회, 끝은 `tool_choice: none`) 순서로 올라가 5번 카드로 나갑니다. 칸의 머리에 "x-web-search: on 요청에만 추가, 민감 요청과 성능 평가 요청은 제외"를 적었고, 7번 카드에 "웹 검색 답변: [1], [2] 번호와 출처 목록"을 넣었습니다. 이 칸을 넣으려고 5번에서 8번 카드의 폭을 줄였습니다.
- **화면의 설명**: 4단계에 도구를 붙이는 조건, 5단계에 다시 추론, 6단계에 BFF의 도구 실행과 AgentCore Web Search, 7단계에 출처 표시를 넣었습니다.
- **화면의 지도**: "웹 검색 사용"을 켜면(기본값) 6단계에서 `n-search`가 주황으로, `e-bff-search`가 켜지고 7단계부터는 지나온 곳으로 남습니다. 끄면 4단계부터 Web Search를 흐리게 합니다.
- **실제 요청**: "웹 검색 사용"을 켠 채 보내면 `x-web-search: on`으로 요청 보기의 웹 검색 예시와 같은 질문을 보냅니다(Gemma는 제공 리전 확인, Qwen은 Kubernetes 릴리스 변경점, 최대 출력 512토큰). 도구 호출 알림(`onNote`)에서 검색 횟수, 결과 수, 검색 시간을 모아 6단계에, 출처 수를 7단계에, 도구를 붙였는지(`x-bff-search`)를 4단계에 보입니다.
- **답변과 출처**: 요청을 보내면 여덟 단계의 설명과 시간 띠 아래에 질문, 검색 기록, 답변, 출처 목록이 나옵니다. 답변의 `[n]`은 출처 링크로 바뀝니다. 대화 보기와 같은 `Sources.jsx`, `citations.js`를 가져다 썼습니다. 검색 결과를 쓴 답변에는 출처와 링크를 함께 보여야 한다는 이용 조건 때문에 답변을 보이는 곳에는 출처 목록을 항상 함께 둡니다.
- 그림의 Web Search 칸을 누르면 웹 검색이 켜지고 6단계가 골라집니다.

웹 검색에서 쓴 값은 다음뿐입니다. 8단계 측정이 아니라서 화면에서 "작업 장비와 BFF에서 잰 값"으로 따로 묶었습니다.

| 값 | 내용 |
|---|---|
| 결과 5건, 본문 1,200자까지 | BFF의 설정(`WEB_SEARCH_MAX_RESULTS`, `WEB_SEARCH_TEXT_CHARS`) |
| 검색 1회 481~1,065ms | 작업 장비(서울)에서 us-east-1을 부른 시간 |
| Gemma 검색 1회에 입력 2,606토큰 | 실제 모델로 같은 흐름을 손으로 돌린 값 |
| Qwen 검색 2회에 입력 4,328토큰, 첫 차례 2.6초, 두 번째 차례 12.1초 | 같음. Qwen은 한 차례에 검색 두 번을 함께 불렀습니다 |
| 1,000건에 7달러, 초당 10건 | 요금과 기본 할당량 |

| BFF에서 잰 검색 시간 485~662ms, 중앙값 568ms | 배포 뒤 CloudFront 경로로 보낸 요청 8건(`results/2026-11-15-websearch/bff-search-ms.json`). 화면에만 쓰고 그림에는 넣지 않았습니다 |


## 화면의 동작

- 단계 띠에서 단계를 고르면 지도에서 그 단계의 일을 하는 구성 요소가 주황으로, 요청이 그때까지 지나온 구성 요소가 초록으로 켜집니다. 쓰지 않는 모델은 흐려집니다. 좌우 화살표 키로 옮길 수 있습니다.
- "재생"은 1단계부터 차례로 넘어갑니다. 단계마다 2.8초, 5단계는 4.2초 머뭅니다.
- "실제 요청 보내기"는 고른 모델로 요청 한 건을 보냅니다. "웹 검색 사용"을 끄면 8단계의 구간별 TTFT 측정과 같은 요청입니다(Gemma는 상담, Qwen은 코딩, 최대 출력 128토큰). 켜면 웹 검색 질문을 보냅니다(위 "웹 검색"). 요청이 진행되는 동안 지도가 그 요청의 상태를 따라가고, 끝나면 단계마다 그 요청의 값과 답변이 나옵니다.
- 지도 아래에는 여덟 단계의 설명 칸이 항상 모두 있습니다(2026-11-17 변경. 그전에는 지금 단계의 칸 하나만 그려서 재생이나 요청이 지나간 단계의 설명이 남지 않았습니다). 칸마다 그 단계의 설명, 이 환경의 구성 요소, 8단계 측정 중앙값, 웹 검색에서 잰 값(6, 7단계), 끝난 요청의 값이 들어갑니다. 칸의 위쪽 테두리와 번호는 단계 띠와 같은 값(`railStates`)으로 칠합니다. 지금 단계는 주황에 "지금 단계", 지나온 단계는 초록에 "지나온 단계"라고 적고, 아직 가지 않은 단계는 표시 없이 둡니다. 칸의 내용은 `apicall.js`의 `stageCards`가 만듭니다.
- 첫 내용까지의 시간 띠는 여덟 단계에 걸친 값이라 설명 칸 안에 두지 않고 단계 목록 아래에 한 번만 둡니다.
- 설명 칸의 변경은 2026-11-17에 배포했습니다. CloudFront 주소에서 가짜 세션으로 화면만 열어(실제 요청은 보내지 않음) 재생 전, 재생 중(3단계), 재생이 끝난 뒤, 처음부터 다시 재생했을 때 모두 칸이 8개이고, 영어 화면의 칸에 한글이 남지 않고, 폭 390px에서 가로 넘침이 없는 것을 확인했습니다. 실제 요청이 끝난 뒤 칸마다 그 요청의 값이 붙는 것은 로컬 빌드에서 BFF 응답을 흉내 내어 확인했습니다. 로그인한 브라우저로 실제 요청을 보내는 확인은 하지 않았습니다.
- 아래쪽 그림의 단계 카드를 누르면 같은 단계가 골라지고 지도로 올라갑니다.
- 지도는 요청 보기와 같은 `flow-map.svg`를 씁니다. 지도에 없는 노드 이름은 건너뜁니다.

## 값의 출처

| 값 | 출처 |
|---|---|
| 구간별 시간(사용자와 엣지 사이, CloudFront, ALB, BFF, 게이트웨이, vLLM, Prefill, 대기열, 응답 헤더, 첫 내용) | `docs/08-results.md` 2절의 "2026-11-15 재측정"(BFF를 EKS 파드로 옮긴 뒤). CloudFront를 거쳐 모델마다 20건을 하나씩 보낸 중앙값 |
| TTFT, Chunk 간격, 토큰당 시간, 전체 시간, 초당 토큰, 동시에 실행한 요청 수 | `docs/08-results.md` 3절의 S1(입력 256, 출력 128, 동시성 1)과 `results/2026-11-14-slo/<모델>/S1_chat_c1.json` |
| 가중치와 KV 캐시 크기, 사용 가능한 GPU 메모리 | `docs/03-vllm.md`의 기동 로그 |
| Decider 판단 시간(BFF가 잰 왕복 4건의 범위, 2026-11-15), 고정 비용 | `docs/07-bff.md` |
| 우선순위별 상담 TTFT | `docs/08-results.md` 4절 |
| 지표 수집 대상, 대시보드 | `docs/08-results.md` 관측 |
| 웹 검색의 결과 수, 본문 길이, 검색 시간, 입력 토큰, 요금, 할당량 | `docs/10-web-search.md` |

전체 시간의 식(TTFT + (출력 토큰 수 - 1) × TPOT)은 S1의 원시 결과로 다시 계산해 맞는 것을 확인했습니다(81.3ms + 127 × 53.91ms, 측정 6,927.8ms). TTFT, ITL, TPOT, 대기열, Prefill의 정의는 [vLLM 문서](https://docs.vllm.ai/en/latest/design/metrics.html)에서, L40S의 메모리(48GB GDDR6)는 [NVIDIA 제품 페이지](https://www.nvidia.com/en-us/data-center/l40s/)에서 확인했습니다.

## 실제 요청에서 알 수 있는 것과 없는 것

브라우저는 응답 헤더와 Chunk의 도착 시각만 봅니다.

- 알 수 있는 것: 응답 헤더 도착 시간, BFF의 판단과 깨우기 시간(`x-bff-timing`), CloudFront의 `Server-Timing`, 첫 Chunk까지의 시간, Chunk 간격, 전체 시간, usage의 토큰 수, 요청 ID.
- 알 수 없는 것: 토큰화, 대기열, Prefill, 후처리의 시간. 이 단계에는 8단계의 측정 중앙값만 표시하고 그렇다고 화면에 적었습니다.
- "브라우저와 BFF 사이"는 응답 헤더 도착 시간에서 BFF 안에서 쓴 시간(판단, 깨우기, 게이트웨이의 응답 헤더까지)을 뺀 값입니다. 8단계의 "진입"(엣지, CloudFront, ALB의 중앙값 합)과 재는 방법이 다릅니다.
- 웹 검색을 부른 요청은 첫 Chunk 전에 검색과 다시 추론이 끼어들 수 있습니다. 브라우저는 그 시간을 가르지 못해서 시간 띠의 마지막 구간을 "게이트웨이, vLLM, 웹 검색"으로 묶어 표시합니다. 검색 자체의 시간은 BFF가 알림으로 보낸 `search_ms`를 6단계에 따로 적습니다.

## 확인하지 못한 것

- 그림의 검색 시간(481~1,065ms)은 작업 장비에서 잰 값입니다. BFF가 잰 값은 화면의 6단계와 `docs/10-web-search.md`에 있습니다.
- 3단계의 "길이 확인". `--max-model-len` 값은 매니페스트에서 확인했지만, 한도를 넘는 요청을 vLLM이 거절하는 것은 이 환경에서 시험하지 않았습니다.
- 토큰화와 후처리에 걸리는 시간. 8단계에서 따로 재지 않았습니다.
