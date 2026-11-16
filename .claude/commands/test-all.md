---
description: 이 저장소의 시험(하네스, 화면, BFF)을 모두 돌리고 결과를 보고합니다
allowed-tools: Read, Glob, Bash(bash tests/run-all.sh:*), Bash(npm test --prefix app/web:*), Bash(docker images:*), Bash(docker run --rm:*)
---

# 전체 시험

이 저장소의 시험을 모두 돌립니다. 여기 있는 명령은 AWS 리소스를 만들거나 바꾸지 않고 모델을 부르지 않습니다.

## 1단계: 환경 확인

- `app/web/node_modules`가 있는지 봅니다. 없으면 `app/web/build.sh`가 `npm ci`부터 실행합니다
- BFF 이미지가 로컬에 있는지 봅니다: `docker images | grep ow-on-gpu/bff`. 없으면 BFF 시험은 건너뛰었다고 보고합니다(이미지는 `app/bff/build.sh`가 만들고 ECR에 올리므로 시험만을 위해 실행하지 않습니다)

## 2단계: 시험 실행

하나가 실패해도 나머지를 계속 돌려 전체 결과를 보고합니다.

```bash
# 하네스 (훅, 설정, 구조, 문서의 포인터)
bash tests/run-all.sh

# 화면 (Markdown 렌더링, 흐름 그림, API 호출 보기, 한영 전환)
npm test --prefix app/web

# BFF (이미지 안에서 실행. 장비의 Python으로는 고정한 의존성을 설치할 수 없습니다)
docker run --rm -v "$PWD/app/bff":/app:ro -w /app <BFF 이미지> python -m unittest test_bff
```

$ARGUMENTS가 있으면 그 묶음만 돌립니다(`harness`, `web`, `bff`). 하네스는 `bash tests/run-all.sh hooks`처럼 이름으로 고를 수 있습니다.

## 3단계: 보고

- 묶음마다 실행, 통과, 실패, 건너뜀 수
- 실패한 시험의 파일 경로와 오류
- 원인이 분명하면 고칠 방법

## 막혔을 때

### 하네스 시험이 "카운터가 맞지 않거나 실행한 시험이 없습니다"로 끝날 때
시험 파일이 실행기의 변수(`TOTAL`, `PASSED` 등)를 덮어쓴 것입니다. 시험 파일의 변수 이름에 접두어를 붙입니다.

### 화면 시험이 한영 전환에서 실패할 때
영어 쪽에 한글이 남았거나 두 언어의 자료 모양이 다릅니다. 새 문구를 `tr(한국어, 영어)` 쌍으로 넣었는지 봅니다.

### BFF 시험을 돌릴 이미지가 없을 때
건너뛴 사실과 이유를 보고합니다. 통과한 것으로 적지 않습니다.
