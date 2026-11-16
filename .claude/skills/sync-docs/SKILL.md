---
name: sync-docs
description: 이 저장소의 문서(AGENT.md, 루트와 모듈의 CLAUDE.md, docs/architecture.md, docs/reference/, 단계 문서, README)를 지금 코드와 맞추고 CLAUDE.md의 품질을 점수로 냅니다. 코드를 크게 바꾼 뒤나 문서를 맞춰 달라는 요청에 씁니다.
---

# 문서 동기화

문서를 지금 코드와 맞춥니다. 규칙과 확정된 결정의 원본은 `AGENT.md`입니다. 같은 내용을 다른 문서에 옮겨 적지 않고 가리키기만 합니다.

## 할 일

### 1. CLAUDE.md 품질 평가
루트와 모듈의 CLAUDE.md를 각각 0에서 100으로 평가합니다.
- 명령과 작업 흐름 (20점)
- 구조 설명의 정확성 (20점)
- 모호하지 않은 규칙 (20점)
- 관례와 주의할 점 (20점)
- 지금 코드와 맞는지 (20점)

### 2. 루트 CLAUDE.md
- `@AGENT.md` 줄이 그대로 있는지 확인합니다. 지우면 규칙이 세션에 실리지 않습니다
- Tech Stack, Key Commands가 지금 코드와 맞는지 봅니다(버전의 원본은 `docs/00-versions.md`)
- `<!-- AUTO-MANAGED:references -->` 구역이 `docs/reference/`의 파일 목록과 같은지 봅니다

### 3. AGENT.md
- "디렉터리 구조"가 실제 디렉터리와 맞는지 봅니다
- "확정된 결정"이 매니페스트와 Terraform의 지금 값과 맞는지 봅니다. 다르면 고치기 전에 사용자에게 어느 쪽이 맞는지 묻습니다

### 4. docs/architecture.md
- 구성 요소, Mermaid 그림, Infrastructure 표가 `k8s/`, `infra/terraform/*.tf`, `infra/cdk-vpc`와 맞는지 봅니다
- English와 한국어 구역의 구조, 표, 그림이 같은지 봅니다

### 5. docs/reference/
- 층마다 "Code Pointers"의 경로가 실제로 있는지 봅니다(`bash tests/run-all.sh structure`가 검사합니다)
- 새 층이 생겼으면 `/add-reference-doc <layer>`로 더하고 `INDEX.md`를 고칩니다

### 6. 모듈 CLAUDE.md
- `app`, `bench`, `infra`, `jobs`, `k8s`, `tests`에 CLAUDE.md가 있는지, Key Files가 실제 파일과 맞는지 봅니다
- 새 최상위 소스 디렉터리가 생겼으면 CLAUDE.md를 만들고 `.claude/hooks/check-doc-sync.sh`의 `SOURCE_ROOTS`에 넣습니다

### 7. 단계 문서와 README
- `docs/NN-*.md`의 수치를 고칠 때는 `results/`의 원시 자료로 다시 확인합니다. 측정하지 않은 값은 적지 않습니다
- README의 두 언어 구역이 같은 구조인지 봅니다

### 8. 보고
```
## 문서 동기화 보고

### 품질 점수
| 파일 | 점수 | 메모 |
|---|---|---|

### 고친 것
- <파일>: <무엇을>

### 사용자 확인이 필요한 것
- <코드와 문서가 다른데 어느 쪽이 맞는지 알 수 없는 항목>
```

## 주의
- 문서의 한국어는 합니다체로 씁니다
- 계정 ID는 `<account-id>`로 가리고, 블로그와 그림에는 버킷 이름, 이메일, CloudFront 도메인을 넣지 않습니다
