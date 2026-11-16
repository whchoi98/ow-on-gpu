# Frontend / Frontend 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The check page is a React and Vite single-page app served from S3 through CloudFront. It signs in with Cognito, calls the BFF under `/v1/*`, records the moment each token arrives and explains how each request was routed. Eight views share one top bar, and the language switches between Korean and English without a reload.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| App shell | `app/web/src/App.jsx` | View switching and sign-in state |
| Sign-in | `app/web/src/SignIn.jsx` | Cognito sign-in screen; token handling is in `auth.js` |
| Request view | `app/web/src/Console.jsx` | Sends one request and shows its record and path |
| Chat view | `app/web/src/Chat.jsx` | Multi-turn conversation in one session |
| Benchmark view | `app/web/src/Compare.jsx` | Sends the same prompt to both models and compares timings |
| Routing view | `app/web/src/Route.jsx` | Asks the BFF for the decision only |
| Status view | `app/web/src/Status.jsx` | Shows whether the two models and the Decider respond |
| API call view | `app/web/src/ApiCall.jsx` | Walks through the stages of one LLM API call |
| BFF client | `app/web/src/stream.js` | Streaming call, request headers, response header parsing; `api.js` for non-streaming calls |
| Language | `app/web/src/i18n.js` | `tr(ko, en)`, `useLang()`, `localized()` |

### 3. Key Decisions
- Every UI text is a `tr(ko, en)` pair; a test fails when English output contains Hangul.
- The page sends `x-lang` on every BFF call so texts made by the BFF follow the page language.
- Recorded responses and measurement prompts stay Korean; the English page adds a gloss instead of translating them.
- Model output is rendered with react-markdown and remark-gfm.
- A new header value is deployed to the page before the BFF starts sending it.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `app/web/src/App.jsx`: List of views
- `app/web/src/stream.js`: Headers sent to and read from the BFF
- `app/web/src/format.js`: Decision reasons and the reasons web search was not used
- `app/web/i18n.test.mjs`: Both languages have the same shape and English has no Hangul
- `app/web/build.sh`: `npm ci`, `npm test`, `npm run build`

### 5. Cross-references
- Related modules: `app/CLAUDE.md`
- Related documents: `docs/07-bff.md`, `docs/09-api-call-view.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
확인용 페이지는 React와 Vite로 만든 단일 페이지 앱이고 S3에 올려 CloudFront로 제공합니다. Cognito로 로그인하고, `/v1/*`의 BFF를 부르고, 토큰이 도착하는 순간을 기록하고, 요청이 어떻게 보내졌는지 설명합니다. 보기 여덟 개가 상단 바 하나를 함께 쓰고, 새로 고침 없이 한국어와 영어를 전환합니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| App shell | `app/web/src/App.jsx` | 보기 전환과 로그인 상태 |
| Sign-in | `app/web/src/SignIn.jsx` | Cognito 로그인 화면. 토큰 처리는 `auth.js` |
| Request view | `app/web/src/Console.jsx` | 요청 하나를 보내고 기록과 경로를 보여 줌 |
| Chat view | `app/web/src/Chat.jsx` | 한 세션의 여러 차례 대화 |
| Benchmark view | `app/web/src/Compare.jsx` | 두 모델에 같은 질문을 보내 시간을 견줌 |
| Routing view | `app/web/src/Route.jsx` | BFF에 결정만 물음 |
| Status view | `app/web/src/Status.jsx` | 두 모델과 Decider의 응답 여부 |
| API call view | `app/web/src/ApiCall.jsx` | LLM API 호출 한 번의 단계를 따라감 |
| BFF client | `app/web/src/stream.js` | 스트리밍 호출, 요청 헤더, 응답 헤더 읽기. 스트리밍이 아닌 호출은 `api.js` |
| Language | `app/web/src/i18n.js` | `tr(ko, en)`, `useLang()`, `localized()` |

### 3. 주요 결정
- 화면의 모든 문구는 `tr(ko, en)` 쌍입니다. 영어 출력에 한글이 있으면 시험이 실패합니다.
- 화면이 BFF를 부를 때마다 `x-lang`을 보내 BFF가 만드는 문구가 화면 언어를 따르게 합니다.
- 기록한 응답과 측정용 질문은 한국어로 둡니다. 영어 화면은 번역하지 않고 풀이를 덧붙입니다.
- 모델 응답은 react-markdown과 remark-gfm으로 렌더링합니다.
- 새 헤더 값은 BFF가 보내기 전에 화면부터 배포합니다.

ADR은 아직 없습니다. 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `app/web/src/App.jsx`: 보기 목록
- `app/web/src/stream.js`: BFF에 보내고 받는 헤더
- `app/web/src/format.js`: 결정 이유, 웹 검색을 쓰지 않은 이유
- `app/web/i18n.test.mjs`: 두 언어의 모양이 같고 영어에 한글이 없는지
- `app/web/build.sh`: `npm ci`, `npm test`, `npm run build`

### 5. 상호 참조
- 관련 모듈: `app/CLAUDE.md`
- 관련 문서: `docs/07-bff.md`, `docs/09-api-call-view.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
