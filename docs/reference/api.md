# API / API 구성 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The BFF exposes an OpenAI-compatible chat completions endpoint behind CloudFront and an internal ALB. It verifies the Cognito access token, picks the model, wakes Qwen when needed, runs tool calls and relays the SSE stream unchanged. Behind it, the inference gateway routes by the `model` field of the request body.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| BFF app | `app/bff/bff.py` | Routes, decision flow, tool loop, response headers |
| Routing rules | `app/bff/routing.py` | Sensitive-data patterns, task table, Decider answer handling, fallback |
| Token verification | `app/bff/auth.py` | Cognito access token check with a cached JWKS |
| Texts | `app/bff/texts.py` | Korean and English pairs of every text the BFF produces |
| Web search tool | `app/bff/websearch.py` | Tool definition and the call to AgentCore Web Search |
| Gateway routes | `k8s/gemma/routes.yaml` | HTTPRoute and InferenceObjective per model; `k8s/qwen/routes.yaml` and `k8s/decider/route.yaml` follow the same shape |
| Wake API | `k8s/sleep-controller/wake-api.py` | Wakes a sleeping Qwen before the request is forwarded |

### 3. Key Decisions
- Every path except `/healthz` requires a Cognito access token.
- Deterministic rules run first; the Decider is asked once per session and only when no rule applies.
- When the Decider is silent or below the confidence threshold the request goes to Gemma with thinking off and is handled as sensitive.
- The SSE stream is relayed chunk by chunk; buffering would break streaming.
- Response headers (`x-bff-*`) carry the decision, its reason and timings so the page can explain each request.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `app/bff/bff.py`: `create_app` lists the routes; `chat` builds the response headers
- `app/bff/routing.py`: `decide_without_decider`, `from_decider`, `FALLBACK`
- `app/bff/test_bff.py`: Behaviour of every route and header, run inside the image
- `docs/api-reference.md`: Endpoints, request headers, response headers, error bodies

### 5. Cross-references
- Related modules: `app/CLAUDE.md`
- Related documents: `docs/07-bff.md`, `docs/10-web-search.md`, `docs/api-reference.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
BFF는 CloudFront와 내부 ALB 뒤에서 OpenAI 호환 chat completions 경로를 제공합니다. Cognito 액세스 토큰을 검증하고, 모델을 정하고, 필요하면 Qwen을 깨우고, 도구 호출을 실행하고, SSE 스트림을 그대로 전달합니다. 그 뒤의 추론 게이트웨이는 요청 본문의 `model` 값으로 경로를 고릅니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| BFF app | `app/bff/bff.py` | 경로, 결정 흐름, 도구 호출 반복, 응답 헤더 |
| Routing rules | `app/bff/routing.py` | 민감 정보 형식, 업무 종류 표, Decider 답의 해석, 기본값 |
| Token verification | `app/bff/auth.py` | JWKS를 캐시해 두고 하는 Cognito 액세스 토큰 검증 |
| Texts | `app/bff/texts.py` | BFF가 만드는 모든 문구의 한국어와 영어 쌍 |
| Web search tool | `app/bff/websearch.py` | 도구 정의와 AgentCore Web Search 호출 |
| Gateway routes | `k8s/gemma/routes.yaml` | 모델별 HTTPRoute와 InferenceObjective. `k8s/qwen/routes.yaml`, `k8s/decider/route.yaml`도 같은 모양 |
| Wake API | `k8s/sleep-controller/wake-api.py` | 요청을 보내기 전에 잠든 Qwen을 깨움 |

### 3. 주요 결정
- `/healthz`를 뺀 모든 경로가 Cognito 액세스 토큰을 요구합니다.
- 결정적 규칙이 먼저입니다. Decider에는 규칙이 없을 때만, 세션마다 한 번 묻습니다.
- Decider가 답하지 않거나 신뢰도가 기준보다 낮으면 Gemma, thinking 끔, 민감 정보 있음으로 처리합니다.
- SSE는 청크 단위로 그대로 전달합니다. 모아서 내보내면 스트리밍이 깨집니다.
- 응답 헤더(`x-bff-*`)에 결정, 근거, 구간 시간을 실어 화면이 요청마다 설명할 수 있게 합니다.

ADR은 아직 없습니다. 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `app/bff/bff.py`: `create_app`에 경로 목록, `chat`에 응답 헤더
- `app/bff/routing.py`: `decide_without_decider`, `from_decider`, `FALLBACK`
- `app/bff/test_bff.py`: 모든 경로와 헤더의 동작. 이미지 안에서 실행
- `docs/api-reference.md`: 경로, 요청 헤더, 응답 헤더, 오류 본문

### 5. 상호 참조
- 관련 모듈: `app/CLAUDE.md`
- 관련 문서: `docs/07-bff.md`, `docs/10-web-search.md`, `docs/api-reference.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
