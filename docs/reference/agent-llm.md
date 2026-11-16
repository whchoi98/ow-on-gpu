# Agent · LLM / Agent · LLM 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
Two language models are served by vLLM v0.33.0: Gemma 4 31B for customer-facing work and Qwen3.8-27B for internal work. A small model, Strands Decider 2B, answers routing questions when no rule applies. The BFF runs the tools the models call: an order lookup and a web search through Amazon Bedrock AgentCore Web Search.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| Gemma server | `k8s/gemma/deployment.yaml` | vLLM flags, tool-call and reasoning parsers for Gemma |
| Qwen server | `k8s/qwen/deployment.yaml` | vLLM flags, sleep mode, MTP speculative decoding |
| Decider | `k8s/decider/deployment.yaml` | Strands Decider 2B served behind the gateway at `/decide` |
| Decision flow | `app/bff/bff.py` | Decider questions, session cache, tool loop of at most three rounds |
| Routing rules | `app/bff/routing.py` | Turns rules and Decider answers into a model, priority and thinking flag |
| Web search | `app/bff/websearch.py` | Tool definition, instruction, source numbering |
| Model texts | `app/bff/texts.py` | Tool descriptions and instructions in Korean and English |
| Stage prompts | `prompts.md` | Prompts for build stages 0 to 9 |

### 3. Key Decisions
- Requests with personal data go only to Gemma; fixed-format data is caught by rules before the Decider is asked.
- The Decider is asked once at the start of a session and its answer is reused.
- Decider questions and the Korean-thinking instruction exist in Korean only, so decisions do not depend on the page language.
- Reasoning stays with Gemma and Qwen; web search runs in us-east-1 because the API is not offered in Seoul.
- Qwen uses MTP with three speculative tokens; Gemma runs without speculative decoding.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `app/bff/bff.py`: `DECIDER_QUESTIONS`, `ask_decider`, `relay_with_tools`
- `app/bff/websearch.py`: `tool`, `instruction`, `run`
- `k8s/qwen/deployment.yaml`: `--speculative-config` and `--enable-sleep-mode`
- `bench/bff/lang_check_in_pod.py`: Sends real requests to the models from inside a BFF pod
- `bench/decider/bench.py`: Decider latency

### 5. Cross-references
- Related modules: `app/CLAUDE.md`, `k8s/CLAUDE.md`, `bench/CLAUDE.md`
- Related documents: `docs/03-vllm.md`, `docs/05-decider.md`, `docs/08-results.md`, `docs/10-web-search.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
vLLM v0.33.0이 언어 모델 둘을 서빙합니다. Gemma 4 31B는 고객 경로, Qwen3.8-27B는 내부 업무입니다. 규칙으로 정해지지 않는 요청은 작은 모델 Strands Decider 2B가 경로를 판단합니다. 모델이 부르는 도구(주문 조회, Amazon Bedrock AgentCore Web Search를 통한 웹 검색)는 BFF가 실행합니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| Gemma server | `k8s/gemma/deployment.yaml` | Gemma의 vLLM 플래그, 도구 호출과 추론 파서 |
| Qwen server | `k8s/qwen/deployment.yaml` | Qwen의 vLLM 플래그, sleep mode, MTP 추측 디코딩 |
| Decider | `k8s/decider/deployment.yaml` | 게이트웨이의 `/decide` 뒤에서 서빙하는 Strands Decider 2B |
| Decision flow | `app/bff/bff.py` | Decider 질문, 세션 캐시, 최대 세 차례의 도구 호출 반복 |
| Routing rules | `app/bff/routing.py` | 규칙과 Decider 답을 모델, 우선순위, thinking 여부로 바꿈 |
| Web search | `app/bff/websearch.py` | 도구 정의, 지시문, 출처 번호 관리 |
| Model texts | `app/bff/texts.py` | 도구 설명과 지시문의 한국어와 영어 |
| Stage prompts | `prompts.md` | 구축 0단계에서 9단계까지의 프롬프트 |

### 3. 주요 결정
- 개인정보가 든 요청은 Gemma로만 보냅니다. 형식이 정해진 정보는 Decider에 묻기 전에 규칙으로 거릅니다.
- Decider에는 세션을 시작할 때 한 번 묻고 답을 재사용합니다.
- Decider 질문과 한국어 추론 지시문은 한국어 한 벌만 둡니다. 화면 언어에 따라 판단이 달라지지 않습니다.
- 추론은 Gemma와 Qwen이 합니다. 웹 검색은 서울에 API가 없어 us-east-1에서 실행합니다.
- Qwen은 추측 토큰 3개의 MTP를 씁니다. Gemma는 추측 디코딩 없이 실행합니다.

ADR은 아직 없습니다. 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `app/bff/bff.py`: `DECIDER_QUESTIONS`, `ask_decider`, `relay_with_tools`
- `app/bff/websearch.py`: `tool`, `instruction`, `run`
- `k8s/qwen/deployment.yaml`: `--speculative-config`, `--enable-sleep-mode`
- `bench/bff/lang_check_in_pod.py`: BFF 파드 안에서 실제 모델까지 요청을 보냄
- `bench/decider/bench.py`: Decider의 판단 시간

### 5. 상호 참조
- 관련 모듈: `app/CLAUDE.md`, `k8s/CLAUDE.md`, `bench/CLAUDE.md`
- 관련 문서: `docs/03-vllm.md`, `docs/05-decider.md`, `docs/08-results.md`, `docs/10-web-search.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
