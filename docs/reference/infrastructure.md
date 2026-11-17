# Infrastructure / 인프라 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The runtime layer is one Amazon EKS 1.37 cluster in ap-northeast-2. Karpenter provisions GPU nodes for the two vLLM servers and the Decider, CPU nodes for the gateway, and Graviton nodes for the BFF. Workloads run in private subnets and read model weights only from Amazon S3.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| NodePools, EC2NodeClasses | `k8s/base/nodepools.yaml` | GPU and system nodes provisioned by Karpenter |
| Namespaces, device plugin | `k8s/base/namespaces.yaml` | Namespaces `inference` and `model-jobs`; NVIDIA device plugin in the same directory |
| vLLM Gemma | `k8s/gemma/deployment.yaml` | Gemma 4 31B on one g6e.4xlarge, Recreate strategy |
| vLLM Qwen | `k8s/qwen/deployment.yaml` | Qwen3.8-27B on one g6e.4xlarge with sleep mode |
| Decider | `k8s/decider/deployment.yaml` | Strands Decider 2B on one g6.xlarge |
| Inference gateway | `k8s/gateway/gateway.yaml` | agentgateway with Gateway API Inference Extension |
| Sleep controller | `k8s/sleep-controller/cronjobs.yaml` | CronJobs that put Qwen to sleep and wake it; wake API |
| BFF pods | `k8s/bff/bff.yaml` | Graviton NodePool, Deployment, Service, Ingress for the internal ALB |
| Metrics collector | `k8s/observability/collector.yaml` | Prometheus agent that remote-writes to Amazon Managed Service for Prometheus |
| Model jobs | `jobs/model-sync/job.yaml` | Jobs that load weights and publish compile caches to S3 |

### 3. Key Decisions
- FP8 checkpoints on L40S, because the GPU cannot run NVFP4 (`AGENT.md`, confirmed decisions).
- Both GPU nodes are On-Demand; Qwen moved from Spot on 2026-11-14.
- Serving pods never download from Hugging Face; a load Job writes to S3 once.
- vLLM Deployments use Recreate because one GPU holds one pod.
- Qwen sleeps outside working hours (weekdays 19:00 to 08:30, Asia/Seoul).

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `k8s/base/nodepools.yaml`: NodePool requirements and limits
- `k8s/gemma/deployment.yaml`: vLLM flags for Gemma
- `k8s/qwen/deployment.yaml`: vLLM flags for Qwen, sleep-aware readiness probe
- `k8s/gateway/install.sh`: Install order of CRDs, agentgateway and the Gateway
- `k8s/bff/install.sh`: render, diff, apply for the BFF manifests

### 5. Cross-references
- Related modules: `k8s/CLAUDE.md`, `jobs/CLAUDE.md`
- Related documents: `docs/03-vllm.md`, `docs/04-gateway.md`, `docs/05-decider.md`, `docs/06-sleep.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
실행 계층은 ap-northeast-2의 Amazon EKS 1.37 클러스터 하나입니다. Karpenter가 vLLM 서버 둘과 Decider의 GPU 노드, 게이트웨이의 CPU 노드, BFF의 Graviton 노드를 만듭니다. 워크로드는 Private 서브넷에서 실행하고 모델 가중치는 Amazon S3에서만 읽습니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| NodePools, EC2NodeClasses | `k8s/base/nodepools.yaml` | Karpenter가 만드는 GPU 노드와 시스템 노드 |
| Namespaces, device plugin | `k8s/base/namespaces.yaml` | 네임스페이스 `inference`, `model-jobs`. 같은 디렉터리에 NVIDIA device plugin |
| vLLM Gemma | `k8s/gemma/deployment.yaml` | g6e.4xlarge 한 대의 Gemma 4 31B, Recreate 전략 |
| vLLM Qwen | `k8s/qwen/deployment.yaml` | g6e.4xlarge 한 대의 Qwen3.8-27B, sleep mode 사용 |
| Decider | `k8s/decider/deployment.yaml` | g6.xlarge 한 대의 Strands Decider 2B |
| Inference gateway | `k8s/gateway/gateway.yaml` | agentgateway와 Gateway API Inference Extension |
| Sleep controller | `k8s/sleep-controller/cronjobs.yaml` | Qwen을 재우고 깨우는 CronJob, 깨우기 API |
| BFF pods | `k8s/bff/bff.yaml` | Graviton NodePool, Deployment, Service, 내부 ALB의 Ingress |
| Metrics collector | `k8s/observability/collector.yaml` | Amazon Managed Service for Prometheus로 보내는 Prometheus agent |
| Model jobs | `jobs/model-sync/job.yaml` | 가중치를 적재하고 compile 캐시를 S3에 게시하는 Job |

### 3. 주요 결정
- L40S는 NVFP4를 쓸 수 없어 FP8 체크포인트를 씁니다(`AGENT.md`의 확정된 결정).
- GPU 노드는 둘 다 On-Demand입니다. Qwen은 2026-11-14에 Spot에서 바꿨습니다.
- 서빙 파드는 Hugging Face에서 내려받지 않습니다. 적재 Job이 S3에 한 번 올립니다.
- GPU 한 장에 파드 하나라 vLLM Deployment는 Recreate 전략입니다.
- Qwen은 업무 시간 밖에 잠듭니다(평일 19:00에서 08:30, Asia/Seoul).

ADR은 `docs/decisions/ADR-001-narrow-decider-fallback.md` 하나입니다(Decider 기본값 처리의 범위). 그 밖의 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `k8s/base/nodepools.yaml`: NodePool의 요구 조건과 한도
- `k8s/gemma/deployment.yaml`: Gemma의 vLLM 플래그
- `k8s/qwen/deployment.yaml`: Qwen의 vLLM 플래그, sleep을 보는 readiness probe
- `k8s/gateway/install.sh`: CRD, agentgateway, Gateway의 설치 순서
- `k8s/bff/install.sh`: BFF 매니페스트의 render, diff, apply

### 5. 상호 참조
- 관련 모듈: `k8s/CLAUDE.md`, `jobs/CLAUDE.md`
- 관련 문서: `docs/03-vllm.md`, `docs/04-gateway.md`, `docs/05-decider.md`, `docs/06-sleep.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
