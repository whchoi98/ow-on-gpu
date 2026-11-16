---
description: 지금 변경을 AGENT.md의 규칙에 비춰 검토하고 확신도 75 이상인 문제만 보고합니다
allowed-tools: Read, Glob, Grep, Bash(git diff:*), Bash(git log:*), Bash(git status:*)
---

# 변경 검토

지금 변경을 확신도 점수로 검토합니다.

## 1단계: 변경 찾기

- $ARGUMENTS에 파일이 있으면 그 파일을 봅니다
- 없으면 스테이징하지 않은 변경을 봅니다: `git diff`
- 그것도 없으면 스테이징한 변경을 봅니다: `git diff --cached`

## 2단계: 검토

바뀐 파일마다 `.claude/skills/project-review/SKILL.md`의 기준을 적용합니다.
- AGENT.md의 작업 규칙(자격 증명, 확인한 플래그, 측정값, S3에서만 읽기, 범위)
- 파일 사이의 일관성: BFF의 헤더와 경로를 바꿨으면 `docs/07-bff.md`, `docs/api-reference.md`, `app/web/src`. 화면 문구는 `tr()` 쌍, BFF 문구는 `app/bff/texts.py`
- 버그(스트리밍, 타임아웃, 인증 없이 열리는 경로, 민감 정보 요청의 경로)
- 품질(중복, 복잡도, 빠진 시험)

## 3단계: 점수와 거르기

문제마다 0에서 100으로 점수를 매기고 75 이상만 보고합니다.

## 4단계: 출력

파일 경로, 줄 번호, 고칠 방법을 적습니다. 75 이상인 문제가 없으면 무엇을 확인했는지 짧게 적습니다.

## 막혔을 때

### 변경이 없을 때 (1단계)
- git 저장소가 아니면 `git diff`를 쓸 수 없습니다. 검토할 파일을 직접 지정해 달라고 합니다: `/review path/to/file`
- 이미 커밋했는지 봅니다: `git log -1 --oneline`

### AGENT.md나 CLAUDE.md를 읽을 수 없을 때 (2단계)
규칙 없이 검토하면 근거가 없습니다. 파일이 있는지 확인하고, 없으면 버그와 품질만 검토했다고 밝힙니다.

### 변경이 클 때
파일이 많으면 `k8s`, `infra`, `app/bff`처럼 동작에 영향이 큰 디렉터리부터 보고, 나머지는 범위에서 뺐다고 적습니다.
