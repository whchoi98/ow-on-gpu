# app 모듈

## Role

사용자 요청이 게이트웨이에 닿기 전의 앱 계층입니다. 두 부분으로 나뉩니다.

- `bff/`: BFF. Cognito 액세스 토큰을 검증하고, 요청을 어느 모델로 보낼지 정하고, 잠든 Qwen을 깨우고, 모델의 도구 호출(주문 조회, 웹 검색)을 실행한 뒤 응답을 SSE 그대로 흘려보냅니다. EKS 파드로 실행합니다(`k8s/bff`)
- `web/`: 확인용 페이지(React, Vite). 요청, 대화, 성능 평가, 경로 판단, 상태, API 호출, 구조, 구축 과정 보기가 있고 한국어와 영어를 전환합니다. S3에 올려 CloudFront로 제공합니다

기록은 `docs/07-bff.md`, `docs/09-api-call-view.md`, `docs/10-web-search.md`에 있고, 경로와 헤더는 `docs/api-reference.md`에 정리했습니다.

## Key Files

| 파일 | 내용 |
|---|---|
| `bff/bff.py` | aiohttp 앱. `POST /v1/chat/completions`, `POST /v1/route`, `GET /v1/status`, `GET /mock/orders/{order_id}`, `GET /healthz` |
| `bff/routing.py` | 모델을 정하는 규칙. 민감 정보 형식 검사, 업무 종류, Decider 답의 해석, 기본값(`FALLBACK`) |
| `bff/auth.py` | Cognito 액세스 토큰 검증. 알고리즘은 RS256으로 고정 |
| `bff/texts.py` | BFF가 만드는 문구의 한국어와 영어 쌍 |
| `bff/websearch.py` | 웹 검색 도구. Amazon Bedrock AgentCore Web Search를 us-east-1로 부름 |
| `bff/test_bff.py` | BFF 시험. 이미지 안에서 실행 |
| `bff/build.sh` | arm64 이미지를 만들어 ECR에 올리고 태그를 `infra/terraform/bff.auto.tfvars`에 적음 |
| `bff/create-user.sh` | Cognito 사용자를 만듦. 비밀번호는 환경 변수로만 받음 |
| `web/src/App.jsx` | 보기 전환과 로그인 상태 |
| `web/src/stream.js`, `web/src/api.js` | BFF 호출. `x-lang`을 포함한 요청 헤더를 붙이고 응답 헤더를 읽음 |
| `web/src/format.js` | 결정 이유, 검색을 쓰지 않은 이유 같은 화면 문구와 계산 |
| `web/src/i18n.js` | `tr(한국어, 영어)`, `useLang()`, `localized()` |
| `web/src/apicall.js`, `web/src/flow.js` | API 호출 보기와 요청 경로 그림의 상태 계산 |
| `web/*.test.mjs` | 화면 시험. `npm test --prefix app/web` |
| `web/build.sh` | `npm ci`, `npm test`, `npm run build` |

## Rules

- BFF는 응답을 모으지 않습니다. 청크 단위로 그대로 흘려보내야 SSE가 깨지지 않습니다
- `/healthz`를 뺀 모든 경로는 토큰을 요구합니다. 인증 없이 열리는 경로를 두지 않습니다
- 민감 정보가 있는 요청과 모델을 정하지 못한 요청은 Gemma로만 보내고 웹 검색을 붙이지 않습니다
- 헤더 값이나 응답 형식을 늘릴 때는 화면을 먼저 배포합니다. 이전 화면은 모르는 값을 잘못 표시합니다
- 화면의 새 문구는 `tr()` 쌍으로, BFF의 새 문구는 `texts.py`의 쌍으로 넣습니다. 시험이 두 언어를 함께 검사합니다
- 측정에 쓴 기본 경로(헤더 없는 한국어 요청)의 문구를 바꾸면 기존 측정값과 조건이 달라집니다. 바꾸기 전에 알립니다
- BFF 시험은 이미지 안에서 돌립니다: `docker run --rm -v "$PWD/app/bff":/app:ro -w /app <BFF 이미지> python -m unittest test_bff`
- 배포는 `/deploy`의 절차를 따릅니다. 차이를 보여 주고 승인을 받은 뒤 적용합니다
