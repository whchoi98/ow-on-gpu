# Project Context

## Overview

ow-on-gpu는 Amazon EKS에서 vLLM으로 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙하고 측정하는 환경입니다. 블로그 시리즈 "EKS 기반 vLLM 서빙 최적화" 3부의 측정에 씁니다.

목적, 아키텍처, 확정된 결정, 업무와 모델 배정, vLLM 시작 설정, 작업 규칙, 디렉터리 구조, 알려진 함정의 원본은 `AGENT.md`입니다. 아래 줄이 그 파일을 세션에 불러옵니다. 같은 내용을 이 파일에 옮겨 적지 않습니다. 고칠 때는 `AGENT.md`를 고칩니다.

@AGENT.md

## Tech Stack

구성 요소의 버전 조합은 `docs/00-versions.md`가 원본입니다. 아래는 코드에 고정된 값입니다.

- **BFF** (`app/bff`): Python 3.13, aiohttp 3.14.5, PyJWT 2.15.1, boto3 1.44.3. arm64 이미지로 EKS 파드에서 실행
- **확인용 페이지** (`app/web`): React 19.3.1, Vite 8.3.8, react-markdown 10.1.0, remark-gfm 4.0.1
- **인프라** (`infra/terraform`): Terraform 1.14 이상, AWS 프로바이더 6.73대, Helm 프로바이더 3.3대. 상태는 로컬 파일
- **VPC** (`infra/cdk-vpc`): AWS CDK(TypeScript), aws-cdk-lib 2.277.0. 스택 이름은 EksVpcStack
- **클러스터** (`k8s`): Kubernetes 매니페스트와 kustomize. EKS 1.37, Karpenter 1.15, Gateway API Inference Extension, agentgateway
- **서빙**: vLLM v0.33.0(이미지 `vllm/vllm-openai:v0.33.0`), Strands Decider 12B(v2, strands-decider 0.4.0)
- **측정** (`bench`): Python 스크립트. 클러스터 안에서 도는 측정은 `bench/job.py`가 Job으로 실행
- **인포그래픽** (`docs/infographic`): aws-infographic 스킬의 infokit으로 그리는 Python 스크립트

## Project Structure

소스 디렉터리의 설명은 `AGENT.md`의 "디렉터리 구조"에 있습니다. 아래는 그 목록에 없는, 작업 도구용 디렉터리입니다.

```
CLAUDE.md               이 파일. AGENT.md를 불러오고 작업 도구의 쓰임을 적음
.claude/                Claude Code 설정(settings.json), 훅, 스킬, 명령, 에이전트
scripts/                작업 환경 준비(setup.sh), git 훅 설치(install-hooks.sh), 환경 식별 값 가리기(mask-identifiers.py)
tests/                  하네스 시험(훅, 설정, 구조, 문서의 포인터). bash tests/run-all.sh
tools/prompts/          프롬프트를 둘 자리(지금은 비어 있음. 단계별 프롬프트는 루트의 prompts.md)
docs/architecture.md    전체 구조와 Mermaid 그림(영어와 한국어)
docs/reference/         층별 구현 참조(infrastructure, api, iac, frontend, ui, security, agent-llm)
docs/decisions/         ADR. ADR-001(Decider 기본값 처리의 범위), ADR-002(Decider v2 12B와 g6e.xlarge, 직접 빌드한 이미지)
docs/runbooks/          런북. 지금은 템플릿만 있음
docs/onboarding.md      처음 작업하는 사람을 위한 안내
docs/api-reference.md   BFF의 경로, 요청 헤더, 응답 헤더
```

모듈마다 `CLAUDE.md`가 있습니다: `app`, `bench`, `infra`, `jobs`, `k8s`, `tests`.

## Conventions

`AGENT.md`의 "작업 규칙"이 먼저입니다. 아래는 코드에서 지키고 있는 관례입니다.

- 코드 주석, 문서, 훅의 메시지는 한국어로 씁니다. 문서는 합니다체입니다. 식별자, 명령, 경로, 표준 용어는 원문대로 둡니다
- 화면의 새 문구는 `tr(한국어, 영어)` 쌍으로 넣습니다(`app/web/src/i18n.js`). 영어 쪽에 한글이 남으면 `npm test`가 실패합니다
- BFF가 만드는 문구는 `app/bff/texts.py`에 한국어와 영어 쌍으로 둡니다. Decider에 보내는 질문과 한국어 추론 지시문은 한 벌만 둡니다
- 측정 결과는 `results/<날짜>-<항목>/`에 원시 자료로 남기고, 문서에는 그 자료로 확인한 값만 적습니다
- 계정 ID, ARN, CloudFront 주소 같은 환경 식별 값은 저장소에 올리지 않습니다(`AGENT.md` 작업 규칙). 출력과 문서에서는 `<account-id>` 같은 자리 표시로 가리고, 결과 파일은 커밋 전에 `python3 scripts/mask-identifiers.py <경로>`로 가립니다. 커밋 전 검사가 같은 값을 막습니다
- 환경별 값(모델 버킷 이름, Prometheus 작업 공간 주소, 공인 IP)이 든 파일 다섯 개는 추적하지 않고 `*.example`만 추적합니다. 실제 파일을 고치면 `python3 scripts/mask-identifiers.py --stdout <파일> > <파일>.example`로 예시를 함께 고칩니다
- 블로그와 그림에는 계정 ID, 버킷 이름, 이메일, CloudFront 도메인을 넣지 않습니다. 화면을 찍은 그림에는 로그인한 계정이 보이지 않게 합니다
- 데모 계정 비밀번호는 코드, Terraform state, 문서, 결과 파일, `.env`에 남기지 않습니다. 필요한 명령에 환경 변수 `USER_PASSWORD`로만 넘깁니다
- kubectl은 `KUBECONFIG=infra/terraform/.kubeconfig`으로 씁니다. 공유 장비의 기본 컨텍스트를 바꾸지 않습니다

## Key Commands

```bash
# 작업 환경 준비 (도구 확인, 훅 실행 권한, 화면 의존성)
bash scripts/setup.sh

# 하네스 시험. 이름으로 고를 수 있음: hooks, structure
bash tests/run-all.sh

# 화면 시험과 빌드
npm test --prefix app/web
app/web/build.sh                  # npm ci, npm test, npm run build

# BFF 시험 (이미지 안에서 실행. 장비의 Python으로는 고정한 의존성을 설치할 수 없음)
docker run --rm -v "$PWD/app/bff":/app:ro -w /app <BFF 이미지> python -m unittest test_bff

# BFF 배포: 이미지 빌드, 차이 보기, 승인 뒤 적용
app/bff/build.sh
k8s/bff/install.sh diff
k8s/bff/install.sh apply

# Decider 배포: 이미지 빌드(버전을 올릴 때만), 차이 보기, 승인 뒤 적용
k8s/decider/install.sh build
k8s/decider/install.sh diff
k8s/decider/install.sh apply

# 화면 배포: 승인 뒤 적용
terraform -chdir=infra/terraform plan -target=aws_s3_object.web -out=<계획 파일>
terraform -chdir=infra/terraform apply <계획 파일>

# 인포그래픽 (INFOKIT_FONTS, AWS_ICON_BUNDLE, PYTHON 환경 변수가 필요. .env.example 참고)
docs/infographic/build.sh

# 결과 파일의 환경 식별 값 가리기 (커밋 전). --check는 가릴 것이 있는지만 봄
python3 scripts/mask-identifiers.py results/<날짜>-<항목>

# 배포 뒤 확인 (비밀번호 없이)
python bench/bff/lang_check_live.py <사이트 주소>
kubectl -n app exec -i <BFF 파드> -- python - < bench/bff/lang_check_in_pod.py
```

알아 둘 점:

- `terraform plan`을 `-target` 없이 실행하면 `helm_release.karpenter`의 레지스트리 로그인에서 실패합니다. 앱 변경은 `-target`으로 좁힙니다
- `kubectl diff`는 서버 dry-run이라 클러스터의 웹훅이 더하는 줄까지 보여 줍니다. 내가 쓰지 않은 줄이 있으면 적용하기 전에 무엇이 더하는지 확인합니다(`docs/07-bff.md`)
- `k8s/bff/install.sh`와 `k8s/decider/install.sh`는 자기 디렉터리로 옮겨 가 실행하므로 `KUBECONFIG`를 절대 경로로 줍니다(`export KUBECONFIG="$PWD/infra/terraform/.kubeconfig"`). 상대 경로면 kubectl이 `localhost:8080`에 붙으려다 실패합니다
- `/deploy`, `/test-all`, `/review` 명령과 `project-review`, `sync-docs`, `refactor`, `release` 스킬이 위 절차를 담고 있습니다

---

## Auto-Sync Rules

Plan 모드를 나온 뒤와 코드를 크게 바꾼 뒤에 아래 규칙을 따릅니다.

### Post-Plan Mode Actions

Plan 모드(`/plan`)를 나와 구현을 시작하기 전에:

1. **아키텍처가 바뀌는 결정**을 했으면 `docs/architecture.md`를 고칩니다
2. **확정된 결정이 바뀌면** `AGENT.md`의 "확정된 결정" 표를 고칩니다. 대안을 견줘 내린 결정이면 `docs/decisions/ADR-NNN-title.md`도 만듭니다
3. **새 최상위 소스 디렉터리**를 만들면 그 디렉터리에 `CLAUDE.md`를 만들고 `.claude/hooks/check-doc-sync.sh`의 `SOURCE_ROOTS`에 넣습니다
4. **운영 절차를 정했으면** `docs/runbooks/`에 런북을 만듭니다
5. **이 파일에 적은 명령이나 관례가 바뀌면** 위 구역을 고칩니다

### Code Change Sync Rules

| 바꾼 것 | 함께 고칠 문서 |
|---|---|
| BFF의 경로, 요청 헤더, 응답 헤더 | `docs/07-bff.md`, `docs/api-reference.md`, `docs/reference/api.md` |
| 매니페스트(`k8s/`) | `AGENT.md`의 "확정된 결정", 해당 단계 문서(`docs/03-vllm.md`에서 `docs/07-bff.md`), `docs/architecture.md` |
| Terraform 또는 CDK | `docs/architecture.md`의 Infrastructure 표, `docs/reference/iac.md` |
| 측정 스크립트(`bench/`), 새 측정 | `results/<날짜>-<항목>/`, `docs/08-results.md` |
| 화면(`app/web/src`) | `docs/07-bff.md`의 화면 설명. 그림이 바뀌면 `docs/infographic/build.sh`와 `app/web/build.sh`를 다시 실행 |
| 디렉터리 추가나 이름 변경 | `AGENT.md`의 "디렉터리 구조" |

### ADR Numbering

`docs/decisions/ADR-*.md`에서 가장 큰 번호에 1을 더합니다. 형식은 `ADR-NNN-concise-title.md`입니다.

## Implementation References

<!-- AUTO-MANAGED:references -->
층별 구현 참조는 `docs/reference/`에 있습니다. 색인은 [INDEX](docs/reference/INDEX.md)입니다.
- [Infrastructure](docs/reference/infrastructure.md)
- [API](docs/reference/api.md)
- [IaC](docs/reference/iac.md)
- [Frontend](docs/reference/frontend.md)
- [UI](docs/reference/ui.md)
- [Security](docs/reference/security.md)
- [Agent · LLM](docs/reference/agent-llm.md)
<!-- /AUTO-MANAGED -->
