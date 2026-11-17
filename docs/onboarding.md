# 작업 시작 안내

이 저장소에서 처음 작업하는 사람을 위한 안내입니다. 규칙과 확정된 결정의 원본은 루트의 `AGENT.md`입니다.

## 빠른 시작

### 1. 사전 요구 사항

- [ ] AWS CLI와 대상 계정의 자격 증명. 리전은 ap-northeast-2
- [ ] kubectl, Terraform 1.14 이상, Docker(arm64 이미지를 만들 수 있는 장비)
- [ ] Node.js와 npm(확인용 페이지의 시험과 빌드)
- [ ] jq, python3, Bash 4 이상(훅과 하네스 시험)
- [ ] 인포그래픽을 다시 만들려면 Pillow와 Playwright가 있는 Python, 나눔스퀘어OTF와 D2Coding 폰트, aws-diagram 스킬의 아이콘 묶음(`.env.example`)

### 2. 준비

```bash
# 도구 확인, 훅 실행 권한, 화면 의존성
bash scripts/setup.sh

# 프로젝트 전용 kubeconfig를 만듭니다. 공유 장비의 기본 컨텍스트를 바꾸지 않습니다
terraform -chdir=infra/terraform output -raw update_kubeconfig
export KUBECONFIG=$PWD/infra/terraform/.kubeconfig
```

두 번째 명령은 실행할 명령을 출력합니다. 출력된 명령을 확인한 뒤 실행합니다.

환경마다 다른 값이 든 파일 다섯 개는 저장소에 없고 자리 표시만 든 `*.example`이 있습니다. `scripts/setup.sh`가 예시를 복사해 두므로 자리 표시를 실제 값으로 바꿉니다.

| 파일 | 채울 값 |
|---|---|
| `k8s/base/params.yaml`, `jobs/model-sync/params.env`, `bench/coldstart/k8s/storage-s3.yaml` | 모델 버킷 이름. `terraform -chdir=infra/terraform output -raw model_bucket` |
| `k8s/observability/prometheus.yml` | Prometheus 작업 공간 ID. `terraform -chdir=infra/terraform output -raw amp_workspace_id` |
| `infra/terraform/terraform.tfvars` | EKS API에 접근을 허용할 작업 장비의 공인 IP |

### 3. 확인

```bash
bash tests/run-all.sh             # 하네스 시험
npm test --prefix app/web         # 화면 시험
kubectl get nodes                 # 클러스터에 닿는지
```

BFF 시험은 이미지 안에서 돌립니다(`app/CLAUDE.md`).

## 프로젝트 개요

- `AGENT.md`: 목적, 아키텍처, 확정된 결정, 작업 규칙, 디렉터리 구조, 알려진 함정
- `CLAUDE.md`: `AGENT.md`를 불러오고 작업 도구의 쓰임을 적은 파일
- `docs/architecture.md`: 전체 구조와 그림
- `docs/00-versions.md`: 구성 요소의 버전 조합
- `docs/03-vllm.md`에서 `docs/08-results.md`: 단계별 기록과 측정 결과
- `docs/api-reference.md`: BFF의 경로와 헤더
- `docs/reference/`: 층별로 코드를 가리키는 참조

## 작업 흐름

- AWS 리소스를 만들거나 바꾸거나 지우기 전에 `terraform plan` 또는 `kubectl diff` 결과를 보여 주고 승인을 받은 뒤 실행합니다. GPU 노드가 뜨는 작업은 실행 전에 따로 알립니다
- `kubectl diff`에 내가 쓰지 않은 줄이 있으면 적용하지 않고 무엇이 더하는지 먼저 확인합니다
- 측정한 값만 문서에 적습니다. 원시 자료는 `results/<날짜>-<항목>/`에 남깁니다
- 계정 ID, ARN, CloudFront 주소 같은 환경 식별 값은 저장소에 올리지 않습니다. 결과 파일은 커밋 전에 `python3 scripts/mask-identifiers.py <경로>`로 가립니다. 가리지 않으면 커밋 전 검사가 막습니다
- BFF와 화면의 배포는 `/deploy` 명령의 절차를 따릅니다(`.claude/commands/deploy.md`)
- 각 단계가 끝나면 만든 파일, 실행한 명령, 확인 결과, 남은 TODO를 짧게 보고하고 멈춥니다
- 커밋은 Conventional Commits 형식으로 씁니다(`feat:`, `fix:`, `docs:`). git 훅이 `Co-Authored-By` 줄을 지우고 스테이징한 파일의 비밀 값을 검사합니다

## 알아 둘 개념

| 개념 | 설명 |
|---|---|
| BFF | 게이트웨이 앞의 앱. 토큰 검증, 모델 결정, Qwen 깨우기, 도구 호출 실행, SSE 전달 |
| Decider | 규칙으로 모델이 정해지지 않을 때 경로를 판단하는 작은 모델(Strands Decider 2B). 세션마다 한 번 물음 |
| 기본값(fallback) | Decider가 답하지 않거나 신뢰도가 기준보다 낮을 때의 처리. Gemma, thinking 끔, 민감 정보 있음. 모델 선택의 신뢰도만 낮으면 민감 정보 요청으로 다루지 않음 |
| EPP | 엔드포인트 선택기. 게이트웨이가 요청을 보낼 vLLM 파드를 고름 |
| sleep mode | Qwen이 GPU 메모리를 비우고 잠드는 기능. 평일 19:00에 잠들고 08:30에 깨어남(Asia/Seoul) |
| 콜드 스타트 | 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화의 네 구간으로 나눠 잼 |
| TTFT, ITL | 첫 토큰까지의 시간, 토큰 사이의 간격. SLO는 TTFT p99 500ms와 ITL p99 50ms |

## 문제 해결

| 증상 | 원인과 조치 |
|---|---|
| `terraform plan`이 `helm_release.karpenter`에서 실패 | 레지스트리 로그인 문제입니다. 변경 범위를 `-target`으로 좁힙니다 |
| `kubectl diff`에 `instrumentation.opentelemetry.io/inject-*`가 보임 | 클러스터의 `amazon-cloudwatch-observability` 애드온이 붙이는 줄입니다. `docs/07-bff.md`를 보고 결정한 뒤 적용합니다 |
| Qwen 요청이 저녁에 느리거나 상태 보기에서 응답 없음 | 잠든 시간대입니다. BFF가 깨우면 몇 초 뒤 응답합니다 |
| CloudFront 주소의 요청이 모두 403 | WAF 속도 제한을 넘겼습니다. 한동안 기다리거나 `waf_rate_limit`을 올립니다 |
| 화면 시험이 한영 전환에서 실패 | 새 문구를 `tr(한국어, 영어)` 쌍으로 넣었는지 봅니다 |
| BFF 시험을 장비의 Python으로 돌릴 수 없음 | 고정한 의존성을 설치할 수 없습니다. 이미지 안에서 돌립니다 |

## 참고 자료

- `prompts.md`: 구축 0단계에서 9단계까지의 프롬프트
- `blog/`: 블로그 원고 3부작의 작업 폴더
- `docs/infographic/`: 그림의 소스. `docs/infographic/build.sh`로 다시 만듭니다
