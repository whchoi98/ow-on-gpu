# ADR-001: Narrow the Decider fallback so an uncertain model choice alone does not block web search

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

---

<a id="english"></a>

# English

## Status
Accepted (2026-11-17)

## Context
A request without a task type is routed by the Decider, which returns a model choice with a confidence, a personal data probability and a reasoning probability. When any confidence was below the threshold of 0.6, the BFF used the fallback: Gemma, thinking off, treated as sensitive. Web search is not attached to sensitive requests, because search queries leave the Seoul Region.

The route criteria given to the Decider cover support, translation and summarization (Gemma) and images, documents and code (Qwen). General questions match neither, so their model choice confidence was low: 0.539 in four chat requests from the check page, and 0.175 and 0.341 in two requests sent from inside the BFF pod. In all six the Decider judged that there was no personal data with a confidence of 0.859 to 0.88. As a result web search never ran in the chat view with the task type left on "Auto", and the session reused that decision for 30 minutes.

## Options Considered

### Option 1: Narrow the fallback
Treat a request as non-sensitive when only the model choice is below the threshold and the no-personal-data judgment meets it. The request still goes to Gemma with thinking off.
- **Pros**: Web search works for general questions. The personal data judgment is trusted at the same threshold as for requests the Decider routes itself. No new header value.
- **Cons**: The data policy gets an exception. Search queries of these requests leave the Region on the strength of a 2B model's judgment.

### Option 2: Extend the Decider route criteria
Add general questions to the Gemma criteria so that the model choice confidence rises.
- **Pros**: The data policy stays as it is.
- **Cons**: The effect is unknown until measured. The routing results recorded in step 5 would no longer match the conditions.

### Option 3: Add guidance on the page only
Tell the user to pick a task type when web search is on.
- **Pros**: No change to the BFF or the policy.
- **Cons**: Web search still does not run with "Auto".

### Option 4: Leave it as it is
- **Pros**: No change.
- **Cons**: The chat view defaults to "Auto", so web search looks broken there.

## Decision
Option 1. `routing.from_decider` returns the fallback with `sensitive=False` when the only low confidence is the model choice and the personal data probability is below 0.5. `x-bff-decision` stays `fallback`, `x-bff-sensitive` is `false`, and `x-bff-search` is `on` when the request asks for web search. A Decider that does not answer, a personal data judgment below the threshold and a judgment that personal data is present keep the previous handling.

## Consequences

### Positive
- Requests without a task type get web search. After deployment the two in-pod requests returned `x-bff-search: on`, one search and five sources each.
- The page explains the fallback according to `x-bff-sensitive`, so the text matches what the BFF did.

### Negative
- `x-bff-decision: fallback` no longer implies `x-bff-sensitive: true`. Clients that assumed so must read both headers.
- For these requests a wrong no-personal-data judgment by the Decider now lets a search query leave the Region. The deterministic rules for resident registration numbers and card numbers still run first, on the request and on the search query.

## References
- `docs/10-web-search.md`, section "업무 종류 없는 요청의 검색 (2026-11-17)"
- `results/2026-11-17-websearch-auto/`
- `AGENT.md`, data policy

---

<a id="korean"></a>

# 한국어

## 상태
승인됨 (2026-11-17)

## 배경
업무 종류가 없는 요청은 Decider가 경로를 판단합니다. Decider는 모델 선택과 그 신뢰도, 개인정보일 확률, 추론이 필요할 확률을 돌려줍니다. 신뢰도 가운데 하나라도 기준 0.6보다 낮으면 BFF는 기본값(Gemma, thinking 끔, 민감 정보 있음)을 썼습니다. 민감 정보 요청에는 웹 검색을 붙이지 않습니다. 검색어가 서울 리전 밖으로 나가기 때문입니다.

Decider에 주는 선택 기준은 상담, 번역, 요약(Gemma)과 이미지, 문서, 코드(Qwen)입니다. 일반 질문은 어느 쪽에도 들지 않아 모델 선택의 신뢰도가 낮았습니다. 확인용 페이지의 대화 요청 4건에서 0.539, BFF 파드 안에서 보낸 요청 2건에서 0.175와 0.341이었습니다. 여섯 건 모두 Decider는 개인정보가 없다고 판단했고 그 신뢰도는 0.859에서 0.88이었습니다. 그 결과 대화 보기에서 업무 종류를 "자동"으로 두면 웹 검색이 한 번도 실행되지 않았고, 세션은 그 결정을 30분 동안 다시 썼습니다.

## 검토한 옵션

### 옵션 1: 기본값 처리 좁히기
모델 선택의 신뢰도만 기준보다 낮고 개인정보가 없다는 판단이 기준 이상이면 민감 정보 요청으로 다루지 않습니다. 요청은 그대로 Gemma, thinking 끔으로 보냅니다.
- **장점**: 일반 질문에 웹 검색이 됩니다. 개인정보 판단을 믿는 기준은 Decider가 직접 경로를 정한 요청과 같습니다. 새 헤더 값이 없습니다.
- **단점**: 데이터 정책에 예외가 생깁니다. 이 요청들의 검색어는 2B 모델의 판단을 근거로 리전 밖으로 나갑니다.

### 옵션 2: Decider 선택 기준 보강
Gemma의 선택 기준에 일반 질문을 더해 모델 선택의 신뢰도를 올립니다.
- **장점**: 데이터 정책이 그대로입니다.
- **단점**: 효과는 측정해 봐야 압니다. 5단계에 기록한 경로 판단 결과와 조건이 달라집니다.

### 옵션 3: 화면 안내만 추가
웹 검색을 켰을 때 업무 종류를 고르라고 안내합니다.
- **장점**: BFF와 정책을 바꾸지 않습니다.
- **단점**: "자동"에서는 계속 웹 검색이 되지 않습니다.

### 옵션 4: 그대로 둠
- **장점**: 바꾸는 것이 없습니다.
- **단점**: 대화 보기의 기본값이 "자동"이라 웹 검색이 고장 난 것처럼 보입니다.

## 결정
옵션 1입니다. `routing.from_decider`는 낮은 신뢰도가 모델 선택뿐이고 개인정보일 확률이 0.5 미만이면 기본값을 `sensitive=False`로 돌려줍니다. `x-bff-decision`은 그대로 `fallback`이고 `x-bff-sensitive`는 `false`이며, 요청이 웹 검색을 켰으면 `x-bff-search`는 `on`입니다. Decider가 답하지 않은 경우, 개인정보 판단의 신뢰도가 기준보다 낮은 경우, 개인정보가 있다고 판단한 경우는 이전 처리를 유지합니다.

## 영향

### 긍정적
- 업무 종류가 없는 요청에 웹 검색이 붙습니다. 배포 뒤 파드 안에서 보낸 요청 2건은 각각 `x-bff-search: on`, 검색 1회, 출처 5개였습니다.
- 화면이 기본값 처리를 `x-bff-sensitive`에 따라 설명하므로 문구가 BFF의 처리와 맞습니다.

### 부정적
- `x-bff-decision: fallback`이 더는 `x-bff-sensitive: true`를 뜻하지 않습니다. 그렇게 가정한 클라이언트는 두 헤더를 함께 읽어야 합니다.
- 이 요청들에서는 Decider가 개인정보가 없다고 잘못 판단하면 검색어가 리전 밖으로 나갑니다. 주민등록번호와 카드번호의 결정적 규칙은 전과 같이 요청과 검색어에 먼저 적용됩니다.

## 참고 자료
- `docs/10-web-search.md`의 "업무 종류 없는 요청의 검색 (2026-11-17)"
- `results/2026-11-17-websearch-auto/`
- `AGENT.md`의 데이터 정책
