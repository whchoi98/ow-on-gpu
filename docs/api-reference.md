# API 참조

BFF(`app/bff/bff.py`)가 제공하는 경로입니다. 동작의 배경과 확인 기록은 `docs/07-bff.md`와 `docs/10-web-search.md`에 있습니다.

## 기본 주소

```
https://<사이트 주소>/v1
```

CloudFront가 `/v1/*`만 내부 ALB를 거쳐 BFF 파드로 보냅니다. 그 밖의 경로는 S3의 정적 페이지입니다. 사이트 주소는 `terraform -chdir=infra/terraform output -raw app_url`로 확인합니다.

## 인증

`/healthz`를 뺀 모든 경로가 Cognito 사용자 풀이 발급한 액세스 토큰을 요구합니다.

```
Authorization: Bearer <액세스 토큰>
```

- ID 토큰은 받지 않습니다. 액세스 토큰의 `token_use`와 `client_id`를 확인합니다
- 서명 알고리즘은 RS256으로 고정합니다
- 토큰이 없거나 맞지 않으면 401과 `WWW-Authenticate: Bearer`를 돌려줍니다
- 사용자는 `app/bff/create-user.sh`로 만듭니다. 가입은 막혀 있습니다

## 경로

### 대화 요청

```
POST /v1/chat/completions
```

OpenAI 호환 형식입니다. BFF가 모델을 정하므로 본문의 `model`은 BFF가 정한 값으로 바뀝니다.

**요청 본문**

| 필드 | 형식 | 필수 | 설명 |
|---|---|---|---|
| `messages` | array | 예 | OpenAI 형식의 메시지 목록 |
| `stream` | boolean | 아니오 | `true`면 SSE로 응답 |
| `max_tokens` | integer | 아니오 | 최대 출력 토큰 수 |
| `chat_template_kwargs.enable_thinking` | boolean | 아니오 | 적지 않으면 BFF의 결정을 따름 |
| `tools` | array | 아니오 | 적으면 BFF는 자기 도구(주문 조회, 웹 검색)를 붙이지 않음 |

본문은 20MiB까지 받습니다.

**요청 헤더**

| 헤더 | 값 | 설명 |
|---|---|---|
| `x-session-id` | 문자열 | 같은 값이면 첫 요청의 결정을 재사용. 세션에 결정이 있어도 민감 정보 형식은 메시지마다 확인 |
| `x-task` | `support`, `translate`, `summarize`, `vision`, `ocr`, `coding` | 업무 종류. 있으면 Decider를 거치지 않고 업무 종류로 모델을 정함. `support`에는 주문 조회 도구가 붙음 |
| `x-priority` | `interactive`, `batch` | 우선순위. 없으면 업무 종류의 기본값 |
| `x-eval-model` | `gemma`, `qwen` | 성능 평가용. 그 모델로 보내고 thinking을 끄고 도구를 붙이지 않음. 민감 정보 규칙이 먼저 |
| `x-thinking-language` | `ko` | thinking이 켜진 요청에 한국어 추론 지시문을 넣음 |
| `x-web-search` | `on` | 웹 검색 도구와 지시문을 붙임 |
| `x-lang` | `en` | BFF가 만드는 문구를 영어로 씀. 없거나 다른 값이면 한국어 |
| `x-request-id` | 문자열 | 없으면 BFF가 만듦 |

**응답 헤더**

| 헤더 | 값 | 설명 |
|---|---|---|
| `x-request-id` | 문자열 | 요청 식별자 |
| `x-bff-model` | `gemma-4-31b`, `qwen38-27b` | 요청을 보낸 모델 |
| `x-bff-decision` | `rule`, `task`, `attachment`, `decider`, `fallback`, `eval` | 무엇으로 정했는지. 민감 정보 규칙, 업무 종류, 첨부 이미지, Decider, 기본값, 성능 평가 |
| `x-bff-sensitive` | `true`, `false` | 민감 정보 요청으로 다뤘는지 |
| `x-bff-thinking` | `true`, `false` | thinking을 켰는지 |
| `x-bff-search` | `on`, `off`, `sensitive`, `fallback`, `disabled` | 웹 검색 도구를 붙였는지. 붙이지 않았으면 그 이유 |
| `x-bff-reason` | JSON | 결정의 근거. 적용한 규칙, 업무 종류, Decider의 선택과 신뢰도 |
| `x-bff-timing` | JSON | BFF 안의 구간 시간. `decide_ms`, `wake_ms`, `upstream_ms`, `woke`, `tools` |

`x-bff-search`의 값:

| 값 | 뜻 |
|---|---|
| `on` | 모델 요청에 웹 검색 도구를 붙임 |
| `off` | 요청이 켜지 않았거나, 성능 평가 요청이거나, 요청이 자기 `tools`를 가져옴 |
| `sensitive` | 민감 정보 요청이라 붙이지 않음 |
| `fallback` | 모델을 정하지 못해 기본값으로 보낸 요청이라 붙이지 않음 |
| `disabled` | 이 환경에 웹 검색이 설정되지 않음 |

**응답 본문**

- `stream: true`: 게이트웨이의 SSE를 그대로 전달합니다. 모델이 BFF의 도구를 부르면 SSE 주석 줄로 알립니다. OpenAI 형식의 클라이언트는 주석 줄을 무시합니다

```
: bff {"event": "tool_call", "name": "web_search", "ms": 1563.3, "query": "...", "search_ms": 484.9, "sources": [{"n": "1", "title": "...", "url": "...", "published_at": "..."}]}
```

- `stream: false`: OpenAI 형식의 JSON입니다. 웹 검색을 썼으면 `bff_sources`에 출처 목록이 있습니다
- 도구 호출은 요청 하나에 최대 세 차례까지 반복합니다

### 경로 판단만 받기

```
POST /v1/route
```

모델을 부르지 않고 결정과 근거만 돌려줍니다. 세션에 저장하지 않습니다.

| 필드 | 형식 | 필수 | 설명 |
|---|---|---|---|
| `messages` | array | 예 | 판단할 메시지 목록 |

요청 헤더 `x-task`를 대화 요청과 같은 뜻으로 받습니다.

**응답** `200 OK`

| 필드 | 설명 |
|---|---|
| `model` | 보낼 모델 |
| `decision` | 무엇으로 정했는지(`x-bff-decision`과 같은 값) |
| `reason` | 결정의 근거 |
| `sensitive` | 민감 정보 요청으로 다루는지 |
| `thinking` | thinking을 켜는지 |
| `objective` | 게이트웨이에 넘기는 우선순위 대상 이름 |
| `rejected` | 대화 요청이었다면 422로 거절됐을지(민감 정보와 이미지가 함께 있는 경우) |
| `decide_ms` | 판단에 걸린 시간 |

### 상태 확인

```
GET /v1/status
```

게이트웨이를 거쳐 두 모델과 Decider가 응답하는지 봅니다. Qwen을 깨우지 않으므로 잠든 Qwen은 응답하지 않는 것으로 나옵니다.

**응답** `200 OK`

| 필드 | 설명 |
|---|---|
| `components.gemma`, `components.qwen` | `ok`, `status`, `ms`, `model`, `max_model_len` |
| `components.decider` | `ok`, `status`, `ms` |
| `checked_at` | 확인한 시각(밀리초) |

### 주문 조회 (고정 데이터)

```
GET /mock/orders/{order_id}
```

상담 업무의 도구 호출을 보여 주려고 둔 고정 데이터입니다. `A-1024`와 `A-1025`가 있고 그 밖의 번호는 찾을 수 없다는 상태를 돌려줍니다. `x-lang: en`이면 상태와 택배사 이름이 영어입니다.

### 상태 점검 (ALB용)

```
GET /healthz
```

토큰 없이 `{"status": "ok"}`를 돌려줍니다. ALB의 대상 상태 확인이 씁니다.

## 오류

오류 본문의 형식은 하나입니다. 문구는 `x-lang`을 따릅니다.

```json
{"error": {"message": "<문구>"}}
```

| 코드 | 상황 |
|---|---|
| 400 | 본문에 `messages`가 없거나 JSON이 아님. `x-eval-model`이 `gemma`, `qwen`이 아님 |
| 401 | 토큰이 없거나, 형식이 틀리거나, 서명 키를 모르거나, 이 서비스의 액세스 토큰이 아님 |
| 403 | AWS WAF가 속도 제한으로 막음(BFF에 닿지 않음) |
| 422 | 민감 정보가 있는 요청에 이미지가 있음. 민감 정보 요청은 Gemma로만 보내는데 Gemma는 이미지를 받지 않음 |
| 502 | 잠든 Qwen을 깨우지 못함 |

## 속도 제한과 타임아웃

- AWS WAF가 IP 하나의 요청을 5분에 300건으로 제한합니다(Terraform 변수 `waf_rate_limit`). 넘으면 그 IP의 요청이 한동안 403입니다
- CloudFront 오리진 응답 타임아웃은 60초, ALB idle timeout은 120초입니다. 근거는 `docs/07-bff.md`의 "타임아웃"에 있습니다
- 배치 작업은 이 경로를 쓰지 않고 게이트웨이의 내부 NLB를 직접 부릅니다
