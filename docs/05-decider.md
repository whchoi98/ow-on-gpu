# 5단계. Strands Decider

2026-11-24에 Decider를 v1(Strands Decider 2B, g6.xlarge)에서 v2(Strands Decider 12B, g6e.xlarge)로 바꾸고 판단 지연을 다시 측정했습니다. 원시 측정값과 로그는 `results/2026-11-24-decider-v2/`에 있습니다. 각 구성에서 한 번씩 실행한 결과입니다. v1의 구성과 측정값은 이 문서 끝의 "v1 기록"에 그대로 두었습니다.

## v2에서 달라진 점과 고른 모델

Strands Decider v2는 2026-11-23에 발표됐습니다([Introducing Strands Decider v2](https://strandsagents.com/blog/introducing-strands-decider-v2/)). 이 환경에 영향을 준 점은 네 가지입니다.

- v2에는 Qwen3.5 기반 2B 모델이 없습니다. 다섯 크기 모두 Gemma 4 기반입니다.
- v2 체크포인트는 LoRA 어댑터를 기반 모델에 병합한 전체 가중치(`model.safetensors`)와 `decision_config.json`을 담습니다. v1처럼 기반 모델을 따로 올리고 설정 파일의 `base_model`을 바꿀 필요가 없습니다.
- v2 체크포인트는 `strands-decider` 0.4.0 이상에서만 읽힙니다.
- 요청과 응답의 형식은 v1과 같습니다. `choice`에는 `choice`, `probabilities`, `confidence`가, `noul`에는 `noul`이 오고 응답에 `latency_ms`가 붙습니다. BFF와 `bench/decider/bench.py`는 고치지 않았습니다.

모델 크기는 strands-decider 저장소의 모델 문서(`docs/models.md`)가 권하는 GPU 메모리로 골랐습니다. 아래 표의 값은 그 문서에 적힌 것이고 이 환경에서 측정한 값이 아닙니다.

| v2 모델 | 가중치(bf16) | 문서가 권하는 GPU |
|---|---|---|
| E2B-gemma4-v2-2611 | 약 10GB | 24GB 한 장 |
| E4B-gemma4-v2-2611 | 약 16GB | 40GB 한 장 |
| 12B-gemma4-v2-2611 | 약 24GB | 48GB 한 장 |
| 26B-A4B-gemma4-v2-2611 | 약 52GB | 80GB 한 장 |
| 31B-gemma4-v2-2611 | 약 63GB | 80GB 한 장 |

GPU를 g6e 계열(L40S, 48GB)로 바꾸기로 하고 그 GPU 한 장에 맞는 12B를 골랐습니다. 노드는 L40S가 한 장인 g6e.xlarge(4 vCPU, 32GiB)입니다. 결정의 배경과 견준 대안은 `docs/decisions/ADR-002-decider-v2-12b-on-g6e.md`에 있습니다.

## 서빙 방식

| 항목 | 값 |
|---|---|
| 체크포인트 | `StrandsAgents/strands-decider-12B-gemma4-v2-2611`, 리비전 `41d5dc0d`. 객체 13개, 23.97GB |
| 노드 | NodePool `decider`의 g6e.xlarge On-Demand 1대(L40S 1장) |
| 이미지 | ECR `ow-on-gpu/decider:0.4.0`(압축 크기 3.72GB). strands-decider 저장소 v0.4.0 태그의 `deploy/sagemaker/Dockerfile`을 고치지 않고 빌드. strands-decider 0.4.0, torch 2.7.1+cu126, transformers 5.19.0 |
| 서버 | 이미지 안에서 `strands-decider serve <체크포인트> --host 0.0.0.0 --port 8080 --device cuda`가 실행됨 |
| 엔드포인트 | `POST /v1/systemone`, `GET /health` |
| 모델 배치 | `/opt/ml/model/strands-decider-12B-gemma4-v2-2611/`. initContainer가 S3의 `models/strands-decider-12B-gemma4-v2-2611/`에서 내려받음. 이미지가 `HF_HUB_OFFLINE=1`이라 Hugging Face에 접근하지 않음 |
| 동시 실행 | v2 체크포인트는 요청을 한 번에 하나씩 실행하는 것이 기본(`--max-concurrency` 기본 1). 이미지 안의 `serve --help`로 확인 |
| 게이트웨이 | v1과 같음. HTTPRoute `decider`가 `POST /decide`를 `/v1/systemone`으로 바꿔 Service로 보냄 |
| 적용 | `k8s/decider/install.sh build`, `diff`, `apply`. 이미지 주소에 계정 ID가 들어가서 매니페스트의 `${DECIDER_IMAGE}` 자리를 스크립트가 Terraform 출력으로 채움 |

- **공개 서빙 이미지를 쓰지 못한 이유.** v1에서 쓴 공개 이미지(`strands-decider:serve-sagemaker-cuda-v1`)는 2026-11-20 빌드(v1.0.2)에도 `strands-decider 0.3.1.dev1`(커밋 `9a7470e`)이 들어 있었습니다. 이미지의 패키지 레이어를 훑어 확인했고, v2를 읽는 모듈(`decision.py`, `backends/`, `core/`)이 없었습니다. 이 커밋은 v0.4.0보다 커밋 12개 뒤입니다. 저장소의 SageMaker 가이드는 이런 경우에 `Dockerfile`로 빌드하라고 안내합니다(`-c image=build`).
- **빌드.** 작업 장비가 arm64여서 amd64 에뮬레이션(`tonistiigi/binfmt`)을 등록한 뒤 `docker buildx build --platform linux/amd64`로 빌드했습니다. 8분 25초 걸렸습니다(06:24:09Z에서 06:32:34Z). ECR 저장소는 같은 태그를 덮어쓰지 못하게 했습니다(`image_tag_mutability = "IMMUTABLE"`).
- **자동 계측 거부.** 파드 템플릿을 바꾸면 `amazon-cloudwatch-observability` 웹훅이 자동 계측을 붙입니다(`docs/07-bff.md`). BFF와 같이 `instrumentation.opentelemetry.io/inject-*`를 `"false"`로 적었고, 새 파드에 계측 init 컨테이너가 없는 것을 확인했습니다.
- `/health` 응답은 `model`이 `strands-decider-12B-gemma4-v2-2611`, `base_model`이 `google/gemma-4-12B-it`, `backend`가 `transformers`, `device`가 `cuda:0`, `dtype`이 `bfloat16`, `max_length`가 32768, `temperature`가 1.5571, `max_concurrency`가 1입니다.

## 교체 절차와 기동 시간

NodePool `decider`의 GPU 한도가 1이어서, v1 파드를 먼저 내리고 노드를 바꾼 뒤 v2를 적용했습니다.

1. `kubectl -n inference scale deploy decider --replicas=0` (06:53:41Z)
2. `kubectl apply -k k8s/base`로 NodePool의 인스턴스를 g6e.xlarge로 변경
3. 기존 NodeClaim(g6.xlarge) 삭제 요청
4. `k8s/decider/install.sh apply` (06:53:48Z)

| 구간 | 시간 |
|---|---|
| 노드 프로비저닝 (NodeClaim 생성부터 Initialized) | 83초 (06:53:50Z에서 06:55:13Z) |
| initContainer 이미지 pull (aws-cli) | 10.3초 |
| 모델 받기 (S3에서 23.97GB) | 101초 (06:55:26Z에서 06:57:07Z) |
| 이미지 pull (3.72GB) | 90.5초 |
| 컨테이너 시작부터 Ready | 43초 (06:58:38Z에서 06:59:21Z) |
| 적용부터 Ready까지 | 5분 33초 (06:53:48Z에서 06:59:21Z) |

- v1 파드를 내린 06:53:41Z부터 06:59:21Z까지 5분 40초 동안 Decider가 응답하지 않았습니다. 이 동안 BFF는 Decider 응답이 없는 경우의 기본 처리(Gemma, thinking off, 민감 정보 있음)를 씁니다.
- 새 NodeClaim은 기존 NodeClaim의 삭제를 요청한 4초 뒤에 만들어졌습니다. 삭제 중인 노드는 GPU 한도를 막지 않았습니다.
- 새 노드는 ap-northeast-2b에 떴습니다. g6e.xlarge는 서울 리전의 2a와 2b에서 제공됩니다.
- v2 서버는 예열 시간을 로그에 남기지 않습니다(v1은 `warmed up in 70.5 s`를 출력). 컨테이너 시작부터 Ready까지의 43초에 가중치 적재와 예열이 들어 있습니다.

## 판단별 지연

판단 세 종류를 요청 하나에 질문 하나씩 넣어 50회씩 차례로 보냈습니다(`bench/decider/bench.py`). 클라이언트는 BFF 파드입니다. 괄호 안은 서버가 응답에 넣어 준 값입니다.

| 경로 | 판단 | 중앙값 | p95 | 서버 중앙값 | 서버 p95 |
|---|---|---|---|---|---|
| Service 직접 | route (선택지 2개) | 88.7ms | 109.8ms | 82.2ms | 96.0ms |
| Service 직접 | policy (정책 판단) | 88.6ms | 99.4ms | 82.1ms | 92.9ms |
| Service 직접 | thinking (thinking 판단) | 88.5ms | 102.4ms | 81.8ms | 95.9ms |
| 게이트웨이 `/decide` | route | 90.6ms | 98.6ms | 82.8ms | 90.8ms |
| 게이트웨이 `/decide` | policy | 89.8ms | 102.2ms | 82.0ms | 94.3ms |
| 게이트웨이 `/decide` | thinking | 89.7ms | 99.6ms | 81.8ms | 91.8ms |

- 입력은 109에서 151 토큰이었습니다. v1은 같은 요청이 96에서 127 토큰이었습니다. 토크나이저와 프롬프트 형식이 다릅니다.
- v1(2B, L4)의 Service 직접 경로 중앙값은 약 70ms(서버 약 64ms)였습니다. v2(12B, L40S)는 약 18.5ms 늘었습니다. 모델, GPU, 클라이언트 파드가 모두 달라 같은 조건의 비교는 아닙니다.
- 게이트웨이를 거치면 중앙값이 1.2ms에서 1.9ms 늘어납니다.
- 요청을 하나씩 차례로 보낸 값입니다. 동시 요청에서의 지연은 측정하지 않았습니다.

### BFF가 보내는 요청 (질문 세 개)

BFF는 요청 하나에 질문 세 개(route, policy, thinking)를 담아 게이트웨이의 `/decide`로 보냅니다. 배포된 BFF의 `ask_decider`를 BFF 파드 안에서 직접 불러 예시 요청 10개를 두 번 보냈습니다(`bench/decider/bff_ask_decider.py`, 20건).

| 항목 | 값 |
|---|---|
| 요청 하나의 시간 | 143.8ms에서 159.9ms, 중앙값 146.4ms |
| BFF의 Decider 타임아웃 | 2초 |
| 결정 | 10건 중 9건은 Decider의 판단대로, 1건은 모델 선택의 신뢰도가 낮아 기본 처리 |

- v1에서 BFF가 실제 요청 4건으로 측정한 Decider 왕복은 139.4ms에서 150.0ms였습니다(2026-11-15, `docs/07-bff.md`). 그때는 화면에서 보낸 요청이었고 이번에는 함수를 직접 불렀습니다.
- BFF 코드와 이미지(`20261117-062048`)는 바꾸지 않았습니다.

## 예시 요청에 대한 판단

측정에 쓴 한국어 요청 10개에 대한 답입니다. route는 고른 선택지와 신뢰도, policy와 thinking은 "예"일 확률입니다. v1 값은 2026-11-14의 것입니다.

| 요청 | v1 route | v2 route | v1 policy | v2 policy | v1 thinking | v2 thinking |
|---|---|---|---|---|---|---|
| 주문한 운동화 배송 문의 | gemma (0.95) | gemma (1.00) | 0.06 | 0.04 | 0.34 | 0.42 |
| 상품 설명 번역 | gemma (0.88) | gemma (0.99) | 0.06 | 0.00 | 0.33 | 0.32 |
| 영수증 사진에서 금액 추출 | qwen (0.81) | qwen (1.00) | 0.06 | 0.05 | 0.37 | 0.22 |
| 파이썬 함수 수정 | qwen (0.85) | qwen (0.97) | 0.08 | 0.00 | 0.59 | 0.76 |
| 이름, 연락처, 주소가 든 배송지 변경 | gemma (0.57) | gemma (0.99) | 0.72 | 1.00 | 0.29 | 0.11 |
| 리뷰 200건 요약 | gemma (0.79) | gemma (0.94) | 0.05 | 0.00 | 0.45 | 0.82 |
| 환불 규정 문의 | gemma (0.78) | gemma (0.98) | 0.06 | 0.00 | 0.46 | 0.24 |
| 요금제 비교 계산 | gemma (0.30) | gemma (0.40) | 0.05 | 0.00 | 0.54 | 0.84 |
| 상품 이미지에서 속성 추출 | qwen (0.54) | qwen (0.97) | 0.06 | 0.00 | 0.48 | 0.80 |
| 영업시간 문의 | gemma (0.91) | gemma (0.97) | 0.06 | 0.01 | 0.21 | 0.07 |

- 고른 모델은 10건 모두 v1과 같습니다. 이미지와 코드 요청 세 건은 qwen, 나머지는 gemma입니다.
- BFF의 기준(신뢰도 0.6)을 넘는 요청이 v1의 7건에서 9건으로 늘었습니다. v1에서 기본 처리가 되던 "상품 이미지에서 속성 추출"(route 0.54)과 "이름, 연락처, 주소가 든 배송지 변경"(route 0.57, policy 0.72)이 v2에서는 Decider의 판단대로 갑니다. 개인정보가 든 요청은 두 경우 모두 Gemma로 가고 민감 정보 요청으로 다뤄집니다.
- "요금제 비교 계산"은 v2에서도 route 신뢰도가 0.40이어서 기본 처리가 됩니다. 개인정보가 없다는 판단은 기준을 넘으므로 민감 정보 요청으로 다루지 않습니다(2026-11-17에 바꾼 규칙).
- thinking 판단은 요청에 따라 방향이 바뀌었습니다. "리뷰 200건 요약"과 "상품 이미지에서 속성 추출"이 v2에서는 0.5를 넘어 thinking이 켜집니다.
- `DECIDER_MIN_CONFIDENCE`는 0.6 그대로 두었습니다. 요청 10건으로 본 것이고 정확도를 평가한 것은 아닙니다.

## 자원 사용

| 항목 | v1 (2B, g6.xlarge) | v2 (12B, g6e.xlarge) |
|---|---|---|
| GPU 메모리 | L4 23,034MiB 중 5,150MiB | L40S 46,068MiB 중 23,725MiB |
| 컨테이너 메모리 (`kubectl top`) | 3,166MiB | 3,333MiB |

- Ready 약 1분 뒤 컨테이너 cgroup의 최대 메모리는 13.40GiB였습니다. 그중 12.23GiB가 파일 캐시이고 익명 메모리는 1.15GiB입니다. 서버는 가중치 파일을 메모리에 복사해 두지 않고 읽어서 GPU로 옮깁니다.
- 매니페스트의 메모리 요청 24Gi와 한도 28Gi는 가중치 크기에 맞춰 잡은 값이고, 측정한 사용량보다 큽니다. 노드를 Decider가 혼자 쓰므로 그대로 두었습니다.
- g6e.xlarge 노드의 할당 가능한 메모리는 29.93GiB(31,381,832Ki)입니다.

## 비용

| 인스턴스 | 시간당 On-Demand 가격 (서울 리전, Linux) |
|---|---|
| g6.xlarge (v1의 노드) | 0.9896달러 |
| g6e.xlarge (v2의 노드) | 2.2880달러 |

- 2026-11-26에 AWS Price List API로 조회한 값입니다(가격표의 적용일은 2026-11-01).
- Decider 노드 한 대의 차이는 시간당 1.2984달러입니다. 전체 고정 비용 추정은 2026-11-15의 약 10.05달러/시간(`docs/07-bff.md`)에서 약 11.35달러/시간이 됩니다. 10.05달러의 항목별 내역은 문서에 남아 있지 않아 노드 가격의 차이만 더했습니다.

## 다음에 영향을 주는 점

- 공개 서빙 이미지가 strands-decider 0.4.0 이상을 담으면 그 이미지의 다이제스트로 돌아가고 ECR 저장소 `ow-on-gpu/decider`를 지울 수 있습니다. 그때 `k8s/decider/install.sh`의 `build`와 이미지 자리 채우기도 필요 없어집니다.
- S3에는 v1 체크포인트(`models/strands-decider-2B-qwen3.5-v1-2610/`)와 그 기반 모델(`models/Qwen3.5-2B-Base/`)이 남아 있습니다. v1로 되돌릴 일이 없으면 지웁니다.
- 노드가 새로 뜨는 경우 Ready까지 5분 33초가 걸렸습니다. 그동안 BFF는 기본 처리를 씁니다.
- `docs/08-results.md`의 구간별 TTFT에 든 Decider 구간은 v1로 측정한 값입니다. 화면(상태, API 호출, 구축 과정 보기)과 인포그래픽(08, 09, 10)의 Decider 이름, 노드, 수치는 2026-11-24에 v2 값으로 고쳐 배포했습니다. 블로그 원고(`blog/`) 3편은 2026-11-26에 v2 값으로 고쳤고, 개인 블로그의 같은 3편은 2026-11-27에 고쳐 게시했습니다. 고정 비용 추정은 약 11.35달러/시간으로 고쳐 2026-11-27에 화면에 배포했습니다.

## 확인하지 못한 것

- 동시 요청에서의 지연과 `--max-concurrency`를 올렸을 때의 GPU 메모리
- 예열을 끈 구성의 첫 요청 시간(v1에서는 약 28초)
- 이미지를 붙인 요청. v2 체크포인트는 이미지를 받지만(`/health`의 `images: true`) 보내 보지 않았습니다
- 16,384 토큰에 가까운 긴 입력에서의 지연과 메모리
- 판단의 정확도. 예시 요청 10건의 답을 v1과 견준 것이 전부입니다

## v1 기록 (2026-11-14, Strands Decider 2B)

아래는 v1 구성의 기록입니다. 2026-11-24에 v2로 바꾸기 전까지 이 구성으로 실행했습니다.

2026-11-14에 Strands Decider 2B를 g6.xlarge(L4) On-Demand 노드에 배포하고 판단 지연을 쟀습니다. 원시 측정값과 로그는 `results/2026-11-14-decider/`에 있습니다. 각 구성에서 한 번씩 실행한 결과입니다.

### 서빙 방식

strands-labs/strands-decider 저장소의 SageMaker 배포 가이드(`deploy/sagemaker`)가 쓰는 방식을 그대로 썼습니다.

| 항목 | 값 |
|---|---|
| 이미지 | `763104351884.dkr.ecr.ap-northeast-2.amazonaws.com/strands-decider`, 태그 `serve-sagemaker-cuda-v1`의 2026-11-13 빌드를 다이제스트로 고정 (strands-decider 0.3.1.dev1, CUDA 12.9.1, 압축 크기 6.66GB) |
| 서버 | 이미지 안에서 `strands-decider serve --host 0.0.0.0 --port 8080`이 실행됨 |
| 엔드포인트 | `POST /v1/systemone`, `GET /health` |
| 모델 배치 | `/opt/ml/model/strands-decider-2B-qwen3.5-v1-2610/`와 `/opt/ml/model/base/`. 저장소의 `scripts/fetch-model.ts`와 같은 배치 |
| 기반 모델 | initContainer가 `strands_decider_config.json`의 `base_model`을 `/opt/ml/model/base`로 바꿈. `HF_HUB_OFFLINE=1`이라 Hugging Face에 접근하지 않음 |
| 가중치 출처 | S3의 `models/strands-decider-2B-qwen3.5-v1-2610/`와 `models/Qwen3.5-2B-Base/` |
| 게이트웨이 | HTTPRoute `decider`가 `POST /decide`를 `/v1/systemone`으로 경로를 바꿔 Service로 보냄. InferencePool은 쓰지 않음 |

- EKS 노드가 이 공개 이미지를 받을 수 있습니다. 노드 역할의 ECR 읽기 권한만으로 됐습니다.
- `/health` 응답의 `base_model`이 `/opt/ml/model/base`이고 `device`가 `cuda`입니다. 서버가 로컬 기반 모델로 떴습니다.
- 저장소 문서는 이 서버에 인증이 없고 동시 요청 동작을 검증하지 않았다고 적습니다. 이 구성에서는 ClusterIP Service와 내부 NLB 뒤의 `/decide`로만 닿습니다.

### 기동 시간

| 구간 | 예열 끔 (`DECIDER_WARMUP=0`) | 예열 켬 (기본) |
|---|---|---|
| 노드 프로비저닝 (NodeClaim 생성부터 Ready) | 55초 | 노드 재사용 |
| 모델 받기 (S3에서 4.5GB) | 18초 | 16초 |
| 이미지 pull (6.66GB) | 89초 | 받아 둔 이미지 사용 |
| 컨테이너 시작부터 Ready | 23초 | 87초 |

- 예열을 켜면 서버가 요청을 받기 전에 질문 종류와 질문 수별로 한 번씩 스스로 실행합니다. 로그는 `[strands-decider] warmed up in 70.5 s`입니다.
- 예열이 끝날 때까지 `/health`가 실패하므로, 파드는 예열이 끝난 뒤에 Ready가 됩니다.
- 첫 배포는 적용부터 Ready까지 3분 28초였습니다(11:59:44Z에서 12:03:12Z, 예열 끔).

### 예열 전후 지연

판단 세 종류를 요청 하나에 질문 하나씩 넣어 차례로 보냈습니다. 지연은 클러스터 안의 파드에서 잰 클라이언트 값이고, 괄호 안은 서버가 응답에 넣어 준 값입니다.

| 구성 | 맨 첫 요청 | 그 뒤 요청의 중앙값 |
|---|---|---|
| 예열 끔 | 27,968ms (27,940ms) | 약 70ms (약 63ms) |
| 예열 켬 | 89.9ms (67.8ms) | 약 70ms (약 64ms) |

- 예열을 끄면 첫 요청 하나가 컴파일 시간을 떠안아 약 28초가 걸립니다. 같은 서버의 두 번째 요청부터는 예열한 서버와 같습니다.
- 예열을 끈 구성에서 맨 첫 요청은 route 판단이었습니다. 그 뒤에 처음 보낸 policy와 thinking 판단은 각각 75.0ms와 68.8ms로, 종류가 달라도 다시 컴파일하지 않았습니다.

### 판단별 지연

예열을 켠 구성에서 판단마다 50회씩 쟀습니다(`bench/decider/bench.py`).

| 경로 | 판단 | 중앙값 | p95 | 서버 중앙값 | 서버 p95 |
|---|---|---|---|---|---|
| Service 직접 | route (선택지 2개) | 70.1ms | 80.3ms | 64.3ms | 69.5ms |
| Service 직접 | policy (정책 판단) | 70.1ms | 72.2ms | 64.1ms | 65.9ms |
| Service 직접 | thinking (thinking 판단) | 70.0ms | 75.7ms | 63.5ms | 69.5ms |
| 게이트웨이 `/decide` | route | 72.6ms | 78.1ms | 64.8ms | 68.5ms |
| 게이트웨이 `/decide` | policy | 72.8ms | 75.9ms | 64.5ms | 66.8ms |
| 게이트웨이 `/decide` | thinking | 73.0ms | 77.3ms | 64.5ms | 67.7ms |

- 세 판단의 지연은 서로 거의 같습니다. 입력은 113에서 118 토큰이었습니다.
- 게이트웨이를 거치면 중앙값이 약 2.5ms에서 3ms 늘어납니다.
- 요청을 하나씩 차례로 보낸 값입니다. 동시 요청에서의 지연은 재지 않았습니다. 서버는 `DECIDER_MAX_CONCURRENCY=1`이어서 동시 요청은 하나씩 처리됩니다.

### 예시 요청에 대한 판단

측정에 쓴 한국어 요청 10개에 대한 답입니다. route는 고른 선택지와 신뢰도, policy와 thinking은 "예"일 확률입니다.

| 요청 | route | policy | thinking |
|---|---|---|---|
| 주문한 운동화 배송 문의 | gemma (0.95) | 0.06 | 0.34 |
| 상품 설명 번역 | gemma (0.88) | 0.06 | 0.33 |
| 영수증 사진에서 금액 추출 | qwen (0.81) | 0.06 | 0.37 |
| 파이썬 함수 수정 | qwen (0.85) | 0.08 | 0.59 |
| 이름, 연락처, 주소가 든 배송지 변경 | gemma (0.57) | 0.72 | 0.29 |
| 리뷰 200건 요약 | gemma (0.79) | 0.05 | 0.45 |
| 환불 규정 문의 | gemma (0.78) | 0.06 | 0.46 |
| 요금제 비교 계산 | gemma (0.30) | 0.05 | 0.54 |
| 상품 이미지에서 속성 추출 | qwen (0.54) | 0.06 | 0.48 |
| 영업시간 문의 | gemma (0.91) | 0.06 | 0.21 |

- 이미지와 코드 요청 세 건은 qwen으로, 나머지는 gemma로 갔습니다. 개인정보가 든 요청만 policy가 0.72로 높습니다.
- 신뢰도가 낮은 답이 있습니다(요금제 계산의 route 0.30, 상품 이미지의 route 0.54). AGENT.md의 데이터 정책은 신뢰도가 기준보다 낮으면 Gemma, thinking off, 민감 정보 있음으로 처리하게 되어 있습니다. 기준값은 7단계에서 정해야 합니다.
- 질문 문구와 선택지 설명은 측정용으로 제가 쓴 것입니다. 정확도를 평가한 것은 아닙니다.

### 자원 사용

- GPU 메모리는 L4의 23,034MiB 중 5,150MiB를 씁니다.
- 컨테이너 메모리는 3,166MiB입니다.

### 다음 단계에 영향을 주는 점

- 판단 1회가 약 70ms이므로, AGENT.md대로 세션 시작 시 한 번만 판단하고 재사용하면 메시지마다의 TTFT에는 더해지지 않습니다.
- 노드가 새로 뜨는 경우 예열 70초가 Ready까지의 시간에 들어갑니다. 그동안 BFF는 Decider 응답이 없는 경우의 기본 처리(Gemma, thinking off, 민감 정보 있음)를 쓰게 됩니다.
- 이미지 태그는 매주 다시 빌드됩니다. 다이제스트를 고정했으므로 올리려면 `k8s/decider/deployment.yaml`의 다이제스트를 바꿔야 합니다.
