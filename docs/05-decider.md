# 5단계. Strands Decider 2B

2026-11-14에 Strands Decider 2B를 g6.xlarge(L4) On-Demand 노드에 배포하고 판단 지연을 쟀습니다. 원시 측정값과 로그는 `results/2026-11-14-decider/`에 있습니다. 각 구성에서 한 번씩 실행한 결과입니다.

## 서빙 방식

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

## 기동 시간

| 구간 | 예열 끔 (`DECIDER_WARMUP=0`) | 예열 켬 (기본) |
|---|---|---|
| 노드 프로비저닝 (NodeClaim 생성부터 Ready) | 55초 | 노드 재사용 |
| 모델 받기 (S3에서 4.5GB) | 18초 | 16초 |
| 이미지 pull (6.66GB) | 89초 | 받아 둔 이미지 사용 |
| 컨테이너 시작부터 Ready | 23초 | 87초 |

- 예열을 켜면 서버가 요청을 받기 전에 질문 종류와 질문 수별로 한 번씩 스스로 실행합니다. 로그는 `[strands-decider] warmed up in 70.5 s`입니다.
- 예열이 끝날 때까지 `/health`가 실패하므로, 파드는 예열이 끝난 뒤에 Ready가 됩니다.
- 첫 배포는 적용부터 Ready까지 3분 28초였습니다(11:59:44Z에서 12:03:12Z, 예열 끔).

## 예열 전후 지연

판단 세 종류를 요청 하나에 질문 하나씩 넣어 차례로 보냈습니다. 지연은 클러스터 안의 파드에서 잰 클라이언트 값이고, 괄호 안은 서버가 응답에 넣어 준 값입니다.

| 구성 | 맨 첫 요청 | 그 뒤 요청의 중앙값 |
|---|---|---|
| 예열 끔 | 27,968ms (27,940ms) | 약 70ms (약 63ms) |
| 예열 켬 | 89.9ms (67.8ms) | 약 70ms (약 64ms) |

- 예열을 끄면 첫 요청 하나가 컴파일 시간을 떠안아 약 28초가 걸립니다. 같은 서버의 두 번째 요청부터는 예열한 서버와 같습니다.
- 예열을 끈 구성에서 맨 첫 요청은 route 판단이었습니다. 그 뒤에 처음 보낸 policy와 thinking 판단은 각각 75.0ms와 68.8ms로, 종류가 달라도 다시 컴파일하지 않았습니다.

## 판단별 지연

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

## 예시 요청에 대한 판단

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

## 자원 사용

- GPU 메모리는 L4의 23,034MiB 중 5,150MiB를 씁니다.
- 컨테이너 메모리는 3,166MiB입니다.

## 다음 단계에 영향을 주는 점

- 판단 1회가 약 70ms이므로, AGENT.md대로 세션 시작 시 한 번만 판단하고 재사용하면 메시지마다의 TTFT에는 더해지지 않습니다.
- 노드가 새로 뜨는 경우 예열 70초가 Ready까지의 시간에 들어갑니다. 그동안 BFF는 Decider 응답이 없는 경우의 기본 처리(Gemma, thinking off, 민감 정보 있음)를 쓰게 됩니다.
- 이미지 태그는 매주 다시 빌드됩니다. 다이제스트를 고정했으므로 올리려면 `k8s/decider/deployment.yaml`의 다이제스트를 바꿔야 합니다.
