# 0단계. 버전과 사전 확인

확인 일자는 2026-11-14입니다. 이 단계에서는 AWS 리소스를 만들지 않았고, 읽기 전용 조회만 실행했습니다. 아래 값은 표에 적은 출처에서 직접 조회하거나 태그 시점의 소스를 읽어 확인한 것입니다. 클러스터나 GPU에서 실행해 본 것은 없습니다. 계획과 달라 결정이 필요한 점은 7절에, 확인하지 못한 항목은 8절에 모았습니다.

## 버전 조합

모든 구성 요소는 최신 버전을 쓰되 서로의 지원 범위 안에서 맞추기로 했습니다(2026-11-14 결정). 처음 계획은 EKS 1.36, Karpenter 1.14, vLLM v0.26.0이었습니다. 아래가 2026-11-14 기준 조합이고, 근거의 세부 내용은 1절부터 5절에 있습니다.

| 구성 요소 | 버전 | 호환 근거 |
|---|---|---|
| EKS | 1.37 | 서울 리전의 최신이자 기본 버전 |
| EKS 애드온 | vpc-cni v1.23.3-eksbuild.1, coredns v1.14.7-eksbuild.35, kube-proxy v1.37.0-eksbuild.39, eks-pod-identity-agent v1.4.1-eksbuild.3 | `describe-addon-versions --kubernetes-version 1.37`의 최신 버전 |
| GPU 노드 AMI | EKS 최적화 AL2023 NVIDIA 1.37.1-20261107. nvidia-kmod 기본 580.178.04, nvidia-container-toolkit 1.20.1 | [amazon-eks-ami v20261107 릴리스](https://github.com/awslabs/amazon-eks-ami/releases/tag/v20261107) |
| Karpenter | v1.15.2 | 호환표에서 쿠버네티스 1.37은 Karpenter 1.15 계열 |
| AWS Load Balancer Controller | v3.6.3 (차트 3.6.3) | 쿠버네티스 1.22 이상. 1.37을 명시한 문구는 없음(8절) |
| Gateway API CRD | v1.6.3 | agentgateway 1.7.x의 지원 범위가 Gateway API 1.4에서 1.6이고, llm-d-router v1.0.0의 `go.mod`가 v1.6.3에 의존. 최신 v1.7.0은 지원표 밖이라 쓰지 않음 |
| GAIE CRD | v1.6.2 | agentgateway v1.7.0과 llm-d-router v1.0.0의 `go.mod`가 모두 GAIE v1.6.2에 의존 |
| llm-d-router (EPP, InferenceObjective) | v1.0.0 | 릴리스 노트 "Bumps Gateway API / GAIE to v1.6.2". `k8s.io/api` v0.37.1 |
| agentgateway | v1.7.0 | 지원표에서 쿠버네티스 1.32에서 1.37. `k8s.io/api` v0.37.1 |
| vLLM | v0.33.0 (`vllm/vllm-openai:v0.33.0`) | 이미지가 CUDA 13.0.2 기반이고 NVIDIA 문서에서 CUDA 13.0의 대응 드라이버 브랜치는 R580. GPU AMI의 기본 드라이버 580.178.04가 이 브랜치. 이미지의 `TORCH_CUDA_ARCH_LIST`에 8.9(Ada)가 들어 있음 |
| strands-decider | 0.4.0 (저장소 v0.4.0 태그의 `deploy/sagemaker/Dockerfile`로 빌드한 이미지) | Decider v2 체크포인트는 0.4.0 이상에서만 읽힘. 2026-11-24에 변경. 그전에는 공개 서빙 이미지에 든 0.3.1.dev1(`docs/05-decider.md`) |
| 지표 수집기 | Prometheus v3.16.0 (`quay.io/prometheus/prometheus:v3.16.0`, agent 모드) | 2026-11-05 릴리스. `promtool check config`와 `--agent` 플래그를 이미지에서 확인. Pod Identity 자격 증명으로 AMP에 remote write 되는 것을 확인 |
| Mountpoint S3 CSI 드라이버 | EKS 애드온 v2.9.2-eksbuild.1 | `describe-addon-versions --kubernetes-version 1.37`의 최신. 콜드 스타트의 기준 구성에서만 씀 |
| BFF | Python 3.13(`python:3.13-slim`), aiohttp 3.14.5, PyJWT 2.15.1, cryptography 50.0.2 | 2026-11-14 `pip index versions`의 최신. 이미지 안에서 시험 17개 통과 |
| 확인용 페이지 | React 19.3.1, react-markdown 10.1.0, remark-gfm 4.0.1, remark-cjk-friendly 2.3.4, remark-cjk-friendly-gfm-strikethrough 2.3.3, Vite 8.3.8, @vitejs/plugin-react 6.3.0 (Node.js 24.22.0에서 빌드) | 2026-11-14 `npm view`의 최신. 빌드와 브라우저 확인 통과 |

최신을 쓰지 않은 것은 Gateway API CRD 하나입니다. 서로 함께 시험했다는 문서가 없는 조합은 8절에 적었습니다.

## 1. EKS, Karpenter, AWS Load Balancer Controller

EKS, Karpenter, 애드온은 배포 시점의 최신 버전을 씁니다.

| 항목 | 확인한 값 | 출처 |
|---|---|---|
| EKS | 1.37이 서울 리전의 최신이자 기본 버전입니다. 출시 2026-10-01, 표준 지원 종료 2027-12-01 | `aws eks describe-cluster-versions --region ap-northeast-2` |
| GPU 노드 AMI | EKS 최적화 AL2023 NVIDIA(x86_64) 1.37 권장 릴리스 1.37.1-20261107. Bottlerocket NVIDIA 변형(aws-k8s-1.37-nvidia)은 1.69.0 | SSM 파라미터 `/aws/service/eks/optimized-ami/1.37/amazon-linux-2023/x86_64/nvidia/recommended/release_version`, `/aws/service/bottlerocket/aws-k8s-1.37-nvidia/x86_64/latest/image_version` |
| Karpenter | 최신 릴리스 v1.15.2(2026-11-12). 호환표에서 쿠버네티스 1.37은 Karpenter 1.15 계열을 요구합니다 | [Karpenter 호환표](https://karpenter.sh/docs/upgrading/compatibility/), [v1.15.2 릴리스](https://github.com/aws/karpenter-provider-aws/releases/tag/v1.15.2) |
| AWS Load Balancer Controller | 최신 릴리스 v3.6.3(2026-11-13), Helm 차트 3.6.3 | [v3.6.3 릴리스](https://github.com/kubernetes-sigs/aws-load-balancer-controller/releases/tag/v3.6.3), [eks-charts index.yaml](https://aws.github.io/eks-charts/index.yaml) |

쿠버네티스 1.37 기준 애드온 버전(`aws eks describe-addon-versions --kubernetes-version 1.37`)은 다음과 같습니다.

| 애드온 | 기본 버전 | 최신 버전 |
|---|---|---|
| vpc-cni | v1.22.4-eksbuild.14 | v1.23.3-eksbuild.1 |
| coredns | v1.14.7-eksbuild.35 | v1.14.7-eksbuild.35 |
| kube-proxy | v1.37.0-eksbuild.39 | v1.37.0-eksbuild.39 |
| eks-pod-identity-agent | v1.4.1-eksbuild.3 | v1.4.1-eksbuild.3 |
| aws-ebs-csi-driver | v1.68.0-eksbuild.1 | v1.68.0-eksbuild.1 |
| metrics-server | v0.9.1-eksbuild.2 | v0.9.1-eksbuild.2 |
| eks-node-monitoring-agent | v1.7.7-eksbuild.1 | v1.7.7-eksbuild.1 |

참고할 점은 다음과 같습니다.

- 클러스터를 배포할 때 함께 설치할 주요 애드온은 vpc-cni, coredns, kube-proxy, eks-pod-identity-agent입니다. 나머지는 1단계에서 필요 여부를 정합니다.
- 쿠버네티스 1.37은 다른 구성 요소의 지원 범위 안에 있습니다. agentgateway 1.7.x 지원표는 1.32에서 1.37까지이고, llm-d 가이드는 최근 세 개 마이너 릴리스를 요구합니다(업스트림 안정 버전은 v1.37.2).
- Karpenter v1.15.2는 이틀 전, LBC v3.6.3은 하루 전에 나온 릴리스입니다. 문제가 있으면 직전 패치인 v1.15.1, v3.6.2로 내립니다.
- LBC 설치 문서의 지원 버전 절은 "v2.5.0+ requires Kubernetes 1.22+"까지만 적고 있고, v3.0.0 릴리스 노트도 "requires Kubernetes 1.22+"로만 표기합니다. 상한은 없지만 1.37을 시험했다는 문구도 찾지 못했습니다(8절).
- LBC v3.6.0 릴리스 노트에 따르면 컨트롤러는 Gateway API CRD v1.6.0 기준으로 빌드됩니다. 이 프로젝트는 LBC를 Service 어노테이션으로 NLB를 만드는 데와 Ingress로 BFF의 내부 ALB를 만드는 데(2026-11-15부터) 쓰고, LBC의 Gateway API 기능은 켜지 않습니다. 2026-11-15에 다시 확인했을 때도 v3.6.3이 최신 릴리스였습니다.
- EKS 사용 설명서의 LBC Helm 설치 페이지는 아직 v2.14.1(차트 1.14.0)을 기준으로 적혀 있습니다. 고정할 버전은 GitHub 릴리스를 기준으로 정했습니다.

## 2. GAIE와 llm-d-router

2절과 3절은 릴리스 노트, 태그 시점의 CRD와 소스, 공식 문서를 읽어 확인한 내용입니다.

GAIE v1.6.0부터 구성이 바뀌었습니다. EPP, 본문 기반 라우팅(BBR), InferenceObjective, Helm 차트가 GAIE 저장소에서 빠져 llm-d 조직으로 옮겨졌고, GAIE에는 InferencePool CRD와 적합성 시험용 경량 EPP만 남았습니다. [v1.6.0 릴리스 노트](https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/tag/v1.6.0)의 문구는 "Full-featured Endpoint Picker (EPP), Body-Based Routing (BBR), and Latency Predictor components have moved to the llm-d repository"입니다.

| 구성 요소 | 최신 안정 버전 | 날짜 | 설치 위치 |
|---|---|---|---|
| GAIE CRD | v1.6.2 | 2026-09-17 | `https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/download/v1.6.2/manifests.yaml` |
| EPP, InferenceObjective | llm-d-router v1.0.0 | 2026-10-16 | CRD는 `https://github.com/llm-d/llm-d-router/releases/download/v1.0.0/manifests.yaml`, 차트는 `oci://ghcr.io/llm-d/charts/llm-d-router-gateway` v1.0.0 |
| 본문 기반 라우팅 | llm-d-inference-payload-processor v1.0.0 | 2026-10-20 | `oci://ghcr.io/llm-d/charts/payload-processor` v1.0.0. agentgateway에서는 쓰지 않습니다(3절) |

InferencePool (GAIE v1.6.2의 CRD)

- API 그룹은 `inference.networking.k8s.io`, 버전은 `v1` 하나입니다.
- `spec.selector.matchLabels`(필수), `spec.targetPorts[].number`(필수, 1개에서 8개), `spec.appProtocol`(`http` 또는 `kubernetes.io/h2c`, 기본 `http`).
- `spec.endpointPickerRef`: `name`, `group`, `kind`(기본 `Service`), `port.number`, `failureMode`(`FailOpen` 또는 `FailClose`, 기본 `FailClose`).

InferenceObjective (llm-d-router v1.0.0의 CRD)

- API 그룹은 `llm-d.ai`입니다. `v1`은 제공되지만 저장 버전이 아니고, `v1alpha2`가 저장 버전이면서 폐기 예정으로 표시되어 있습니다. GAIE v1.5.0까지의 `inference.networking.x-k8s.io/v1alpha2`는 없어졌습니다.
- `v1`의 필드는 `spec.priority`(int32, 선택)와 `spec.poolRefs[]`(`name` 필수, `group` 기본 `inference.networking.k8s.io`, `kind` 기본 `InferencePool`) 또는 `spec.poolSelector`입니다.
- `priority`는 음수를 허용하고 기본값이 없으며, 비워 두면 EPP가 0으로 취급합니다. CRD 설명은 "negative values _are_ allowed"입니다.
- 차트 v1.0.0의 `router.inferenceObjectives` 값은 폐기 예정인 `llm-d.ai/v1alpha2`와 `poolRef`로 리소스를 만듭니다. `v1`으로 만들려면 매니페스트를 직접 작성해야 합니다.

부하 시 우선순위 동작 ([flow-control 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md))

- flow control이 꺼진 기본 상태에서는 풀이 포화되면 음수 priority 요청을 대기시키지 않고 HTTP 429로 즉시 거절합니다. 0 이상인 요청은 그대로 모델 서버로 갑니다.
- `featureGates: ["flowControl"]`을 켜면 priority 구간별 큐에 넣고 높은 구간부터 처리합니다. 큐 한도를 넘거나 TTL(기본 60초)이 지나면 429를 반환합니다.

Objective 선택 헤더

- 현재 이름은 `x-llm-d-inference-objective`입니다. `x-gateway-inference-objective`는 폐기 예정 별칭으로 아직 읽습니다(llm-d-router v1.0.0 `pkg/epp/metadata/consts.go`).
- 값은 InferenceObjective의 이름이고, InferencePool과 같은 네임스페이스에서 찾습니다. 문서는 외부에서 들어온 이 헤더를 지우고 신뢰하는 상위 계층이 넣도록 권합니다.

EPP 차트(`llm-d-router-gateway` v1.0.0)의 주요 값

- `provider.name`: agentgateway에는 `none`을 씁니다.
- `router.modelServers.matchLabels`(필수), `router.modelServers.targetPorts`(기본 8000), `router.modelServers.type`(기본 `vllm`).
- `router.epp.replicas`(기본 1), `router.epp.haMode`. 복제본이 2개 이상이면 차트가 리더 선출을 켜고 리더만 Ready가 됩니다. 리더 장애 후 10초에서 30초 동안 EPP가 없습니다.
- `router.inferencePool.failureMode`: 차트 기본값은 `FailOpen`입니다(CRD 기본값은 `FailClose`).
- 기본 리소스 요청이 CPU 8, 메모리 8Gi입니다. 풀 2개에 EPP를 2개씩 두면 요청량만 32 vCPU이므로 시스템 노드 크기를 정할 때 값을 낮춰야 합니다.

## 3. agentgateway

| 항목 | 확인한 값 | 출처 |
|---|---|---|
| 최신 안정 버전 | v1.7.0 (2026-10-27) | [v1.7.0 릴리스](https://github.com/agentgateway/agentgateway/releases/tag/v1.7.0) |
| 지원 범위 | 쿠버네티스 1.32에서 1.37, Gateway API 1.4에서 1.6, Helm 3.12 이상 | [버전 지원표](https://agentgateway.dev/docs/kubernetes/latest/release-notes/versions/) |
| 설치 | `oci://cr.agentgateway.dev/charts/agentgateway-crds`와 `oci://cr.agentgateway.dev/charts/agentgateway`를 v1.7.0으로 `agentgateway-system` 네임스페이스에 설치. GatewayClass 이름은 `agentgateway` | [Helm 설치 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/install/helm/) |
| GAIE 활성화 | Helm 값 `inferenceExtension.enabled=true` (기본 false) | v1.7.0 `controller/install/helm/agentgateway/values.yaml` |
| GAIE 의존 버전 | v1.7.0의 `go.mod`가 GAIE v1.6.2에 의존. InferencePool `inference.networking.k8s.io/v1` 사용 | v1.7.0 소스 |
| 적합성 보고서 | agentgateway v1.6.0이 GAIE v1.6.2로 시험한 보고서가 있음(14개 통과). v1.7.0 보고서는 아직 없음 | GAIE 저장소 `conformance/reports/` |

Gateway API CRD는 지원표에 맞춰 v1.6 계열을 씁니다. v1.7.0이 2026-10-29에 나왔지만 지원표에는 없습니다.

본문의 model 값으로 라우팅하는 방법

- 별도 ext-proc 배포가 필요 없습니다. 문서 문구는 "With agentgateway, you do not need an external processing callout to BBR for this pattern"입니다.
- Gateway를 대상으로 하는 `AgentgatewayPolicy`(`agentgateway.dev/v1alpha1`)에 `spec.traffic.phase: PreRouting`과 `spec.traffic.transformation.request.set`을 두고, 값에 `json(request.body).model`을 써서 헤더를 만듭니다. HTTPRoute는 그 헤더로 매칭합니다. 문서 예시의 헤더 이름은 `X-Gateway-Base-Model-Name`입니다.
- 이 정책은 HTTPRoute가 아닌 Gateway를 대상으로 해야 합니다.
- 본문이 없는 요청(GET `/v1/models` 등)에서는 헤더가 만들어지지 않고, 클라이언트가 보낸 같은 이름의 헤더도 지워집니다(v1.7.0 소스에서 확인, 문서에는 없음).

게이트웨이 Service와 파드 설정

- `AgentgatewayParameters`(`agentgateway.dev/v1alpha1`)를 만들고 Gateway의 `spec.infrastructure.parametersRef`로 참조합니다. `spec.service.metadata.annotations`에 LBC 어노테이션을, `spec.deployment.spec`에 `replicas`, `nodeSelector`, `tolerations`, `topologySpreadConstraints`를 둡니다.
- 생성되는 Service는 기본 type이 `LoadBalancer`이고 이름이 Gateway와 같습니다.
- 내부 NLB와 IP 대상은 LBC 문서 기준으로 `service.beta.kubernetes.io/aws-load-balancer-type: external`, `aws-load-balancer-nlb-target-type: ip`, `aws-load-balancer-scheme: internal`을 쓰거나 `spec.loadBalancerClass: service.k8s.aws/nlb`를 씁니다. LBC 문서는 이미 있는 Service의 type 어노테이션을 바꾸지 말라고 하므로, Gateway를 만들 때부터 parametersRef를 붙입니다.

그 밖에 4단계에 영향을 주는 점

- agentgateway는 EPP 응답을 기본 10초 기다립니다. 넘으면 500(`external processing failed`)을 반환하고, 이 경우 `FailOpen`은 적용되지 않습니다. flow control로 요청을 오래 대기시키려면 EPP Service를 대상으로 한 `AgentgatewayPolicy`의 `spec.backend.http.requestTimeout`을 늘려야 합니다.
- HTTPRoute 한 rule에 path 매치와 InferencePool backendRef를 함께 쓸 수 있습니다. 문서 예시는 `PathPrefix /v1/`과 헤더 조건을 함께 씁니다. `Exact` path 두 개로 제한하는 구성은 Gateway API 규격상 가능하지만 InferencePool과 함께 쓴 문서 예시는 찾지 못했습니다.

## 4. vLLM

쓸 버전은 v0.33.0입니다. v0.26.0은 처음 계획의 버전이고, 아래 v0.26.0 확인 결과는 버전을 바꾼 근거와 플래그 대조 기록으로 남깁니다.

### v0.26.0 (처음 계획의 버전)

v0.26.0 태그 소스(커밋 `568afb3a`), 릴리스 노트, Docker Hub API로 확인했습니다. 이미지를 실행하지는 않았으므로 "코드에서 확인"이라고 적은 항목은 3단계에서 `vllm serve --help`와 실제 기동으로 다시 확인합니다.

| 항목 | 확인 내용 |
|---|---|
| 릴리스 | 2026-07-27 게시. v0.26.1 정식 릴리스는 없고 `v0.26.1rc0` 태그만 있습니다 |
| 이미지 | `vllm/vllm-openai:v0.26.0`이 있습니다. linux/amd64 압축 크기 8.91GB, linux/arm64 10.35GB. CUDA 13.0.2 기반 |
| Gemma 4 | `Gemma4ForConditionalGeneration`이 모델 레지스트리에 등록되어 있고, 체크포인트의 `architectures`와 일치합니다 |
| Qwen3.8-27B | `Qwen3_5ForConditionalGeneration`이 등록되어 있고, 체크포인트의 `architectures`와 일치합니다. 다만 `Qwen/Qwen3.8-27B` 저장소는 v0.26.0 릴리스 뒤인 2026-08-05에 생겼고, v0.26.0에서 로드했다는 직접 자료는 찾지 못했습니다. 공식 recipe는 "Requires vLLM >= 0.17.0"이라고 적으면서 예시 이미지는 `vllm/vllm-openai:qwen38`을 씁니다 |

AGENT.md의 시작 설정에 있는 플래그는 v0.26.0에 철자 그대로 모두 있습니다. 값과 기본값은 다음과 같습니다.

| 플래그, 기능 | 확인 내용 |
|---|---|
| `--load-format runai_streamer` | 있습니다. 이미지에 `runai-model-streamer[s3,gcs,azure]`가 들어 있고, 모델 인자에 `s3://` 경로를 그대로 줍니다. `--model-loader-extra-config`의 허용 키는 `distributed`, `concurrency`, `memory_limit`입니다. config와 tokenizer 파일은 로컬 캐시로 내려받고 safetensors만 스트리밍합니다 |
| `--language-model-only` | 있습니다. 모든 멀티모달 입력 한도를 0으로 둡니다 |
| `--max-num-seqs` | GPU 메모리가 70GiB 미만이면 기본값이 256입니다. L40S가 여기에 해당합니다. 1024는 70GiB 이상인 GPU의 기본값입니다 |
| Mamba 캐시 블록 검사 | 하이브리드 모델에서 `max_num_seqs`가 Mamba 캐시 블록 수보다 크면 "max_num_seqs (...) exceeds available Mamba cache blocks (...)" 오류로 시작이 실패합니다(`vllm/config/compilation.py`). `--max-num-seqs 32`를 명시하는 계획과 맞습니다 |
| `--kv-cache-dtype fp8` | 있습니다. Triton 어텐션 백엔드의 fp8은 SM 8.9 이상을 요구하고 Ada가 여기에 해당합니다 |
| `--gpu-memory-utilization` | 기본값은 0.92입니다 |
| `--enable-prefix-caching` | 하이브리드 모델(Qwen3.5 계열)은 v0.26.0에서 기본이 꺼짐입니다. 계획처럼 플래그를 명시하면 켜집니다. Gemma 4는 기본이 켜짐입니다 |
| `--scheduling-policy priority` | 값은 `fcfs`(기본)와 `priority`입니다. 요청 본문의 `priority`(정수, 기본 0)는 작을수록 먼저 처리합니다. priority 정책이 아닌 서버에 0이 아닌 값을 보내면 오류가 납니다 |
| `--enable-auto-tool-choice`, `--tool-call-parser` | `gemma4`와 `qwen3_coder` 파서가 있습니다 |
| `--reasoning-parser` | `gemma4`와 `qwen3`가 있습니다 |
| `--enable-sleep-mode` | `VLLM_SERVER_DEV_MODE=1`일 때만 `POST /sleep?level=N`, `POST /wake_up`, `GET /is_sleeping`이 등록됩니다. `/health`는 엔진 오류만 보고 sleep 상태를 보지 않습니다(코드에서 확인) |
| `--speculative-config` | `"method":"mtp"`가 있습니다. Qwen3.5 계열은 모델 자신의 MTP 헤드를 쓰고, Gemma 4는 별도 assistant 체크포인트를 `model`에 줘야 합니다 |
| `VLLM_CACHE_ROOT` | 하위 `torch_compile_cache/`에 컴파일 캐시가 쌓입니다. 문서는 이 디렉터리를 다른 머신으로 복사해 쓸 수 있다고 적습니다 |
| `chat_template_kwargs` | 요청별 `enable_thinking`을 받습니다. Qwen3 계열은 thinking이 기본 켜짐, Gemma 4는 기본 꺼짐입니다 |

v0.26.0에서 계획과 부딪히는 점은 다음과 같습니다.

1. Qwen의 sleep 복귀. 하이브리드 모델에 양자화 KV 캐시(`fp8`)를 쓰면 `/wake_up`이 `AttributeError: 'list' object has no attribute 'zero_'`로 실패한다는 버그가 있습니다([#41564](https://github.com/vllm-project/vllm/issues/41564)). v0.26.0 소스에 해당 코드(`gpu_model_runner.py`의 `cache_tensor.zero_()`)가 그대로 있고, 수정은 v0.27.0 릴리스 노트에 "fixed /wake_up crash on hybrid models (#41602)"로 올라 있습니다. AGENT.md의 Qwen 설정은 sleep mode와 `--kv-cache-dtype fp8`을 함께 씁니다. g7e 측정이 같은 조합에서 복귀에 성공했는지는 이 저장소의 자료로 알 수 없습니다.
2. Gemma 4의 KV 캐시 요구량. v0.25.1에서 v0.26.0으로 올리면 같은 설정에서 KV 캐시 요구량이 약 40% 늘었다는 보고가 열려 있습니다([#49878](https://github.com/vllm-project/vllm/issues/49878)). 0.90으로 시작하지 못하면 0.85로 낮춘다는 3단계 절차가 이 경우를 다룹니다.
3. Gemma 4 응답 끝의 `<turn|>`. v0.26.0에서 스트리밍 응답 끝에 `<turn|>` 토큰이 붙는다는 보고가 있습니다([#49955](https://github.com/vllm-project/vllm/issues/49955)). 요청마다 `enable_thinking: false`를 명시하면 피한다는 댓글이 있습니다.
4. Qwen3.8이 v0.26.0에서 로드되는지에 대한 직접 근거가 없습니다(위 표).

### v0.33.0 (쓸 버전)

- 이미지 환경 변수는 `CUDA_VERSION=13.0.2`, `TORCH_CUDA_ARCH_LIST=7.5 8.0 8.6 8.9 9.0 10.0 12.0`이고 진입점은 `vllm serve`입니다(Docker 레지스트리의 amd64 이미지 설정에서 확인).
- 최신 정식 릴리스는 v0.33.0(2026-11-01)이고 `vllm/vllm-openai:v0.33.0` 이미지가 있습니다(linux/amd64 9.74GB). v0.26.0 뒤로 v0.27.0, v0.27.1, v0.28.0부터 v0.33.0까지 나왔고, v0.34.0은 rc3까지 나와 있습니다.
- v0.33.0 태그 소스에서 계획에 쓰는 것이 그대로 있는지 확인했습니다. 모델 클래스(`Gemma4ForConditionalGeneration`, `Qwen3_5ForConditionalGeneration`, `Qwen3_5MTP`), 파서(`gemma4`, `qwen3_coder`, `qwen3`), `runai_streamer`, `--scheduling-policy`, `--enable-sleep-mode`와 세 엔드포인트, `--language-model-only`, `--kv-cache-dtype`, MTP가 모두 있습니다. `--gpu-memory-utilization` 기본값은 0.92로 같고, L40S의 `--max-num-seqs` 기본값도 256으로 같습니다.
- 이 구성에 영향을 주는 변경은 다음과 같습니다(각 릴리스 노트).
  - v0.27.0(2026-08-10): 하이브리드 모델의 `/wake_up` 실패 수정. PyTorch 2.13.0으로 올림.
  - v0.28.0(2026-08-26): Mamba 계열 모델의 prefix caching 기본값이 켜짐으로 바뀜. Qwen3.5 텍스트 전용 체크포인트 수정.
  - v0.29.0(2026-09-09): Model Runner V2가 모든 모델의 기본값. V1은 폐기 예정.
  - v0.31.0(2026-10-05): 재시작 사이에 양자화된 가중치를 GPU 메모리에 유지하는 `vllm preload` 추가. `--max-num-active-seqs` 추가.
  - v0.32.0(2026-10-18): Python 3.10 지원 종료, 기본 CORS origin 제한.
- v0.33.0에서는 Qwen의 sleep 복귀 문제를 피합니다. 대신 1부와 2부(g7e)의 측정 버전과 다르면 콜드 스타트와 처리량 수치를 같은 조건으로 비교할 수 없으므로, 비교표에 엔진 버전을 함께 적습니다. compile 캐시 prefix의 버전 문자열은 `v0.33.0`으로 씁니다.
- v0.26.0에서 대조한 플래그의 기본값은 버전에 따라 달라졌습니다(prefix caching, Model Runner). 3단계에서 v0.33.0 이미지 안의 `vllm serve --help`로 다시 확인합니다.

## 5. 체크포인트

Hugging Face API(`/api/models/<repo>?blobs=true`)와 각 저장소의 `config.json`, `recipe.yaml`, `README.md`를 직접 읽어 정리했습니다. 크기는 저장소 파일 크기의 합이며 1GB는 10^9바이트입니다.

| 용도 | 저장소 | 리비전 | 전체 크기 | 가중치 파일 | 라이선스 | 양자화 방식 |
|---|---|---|---|---|---|---|
| Gemma | [RedHatAI/gemma-4-31B-it-FP8-dynamic](https://huggingface.co/RedHatAI/gemma-4-31B-it-FP8-dynamic) | `d4ab4f57` (2026-08-13) | 33.30GB | safetensors 2개, 33.27GB | apache-2.0 (카드의 license_link는 Gemma 4 라이선스 페이지) | compressed-tensors, FP8_DYNAMIC. 가중치는 채널별 정적 FP8, 활성값은 토큰별 동적 FP8. vision, lm_head, embed_tokens는 양자화 제외 |
| Qwen (per-channel) | [AzatAI/Qwen3.8-27B-FP8-dynamic](https://huggingface.co/AzatAI/Qwen3.8-27B-FP8-dynamic) | `10c68ff4` (2026-08-15) | 36.80GB | safetensors 3개, 36.78GB (MTP 헤드 `model_mtp.safetensors` 0.85GB 포함) | apache-2.0 | compressed-tensors, FP8_DYNAMIC. 가중치는 채널별 정적 FP8, 활성값은 토큰별 동적 FP8. lm_head, visual, embed_tokens, mlp.gate, shared_expert_gate, linear_attn 전체, mtp 전체는 양자화 제외 |
| Qwen (공식 block) | [Qwen/Qwen3.8-27B-FP8](https://huggingface.co/Qwen/Qwen3.8-27B-FP8) | `c3a462cc` (2026-11-07) | 30.89GB | safetensors 66개, 30.87GB | apache-2.0 | `quant_method: fp8`, `fmt: e4m3`, `activation_scheme: dynamic`, `weight_block_size: [128, 128]`. 카드 문구는 "fine-grained fp8 quantization with block size of 128" |
| Decider (v2, 2026-11-24부터) | [StrandsAgents/strands-decider-12B-gemma4-v2-2611](https://huggingface.co/StrandsAgents/strands-decider-12B-gemma4-v2-2611) | `41d5dc0d` (2026-11-23) | 23.97GB | safetensors 1개 23.92GB, readout 0.002GB | apache-2.0 | 양자화 없음(bf16). `google/gemma-4-12B-it`에 LoRA 어댑터를 병합한 전체 가중치와 토큰 readout |
| Decider (v1, 2026-11-24까지) | [StrandsAgents/strands-decider-2B-qwen3.5-v1-2610](https://huggingface.co/StrandsAgents/strands-decider-2B-qwen3.5-v1-2610) | `216d1ccb` (2026-10-09) | 0.235GB | LoRA 어댑터 0.202GB, readout 헤드 0.013GB | apache-2.0 | 양자화 없음(bf16). `Qwen/Qwen3.5-2B-Base` 위에 올리는 rank 48 LoRA 어댑터와 헤드 |

체크포인트별 확인 내용은 다음과 같습니다.

- Gemma 저장소의 `config.json`은 `architectures: Gemma4ForConditionalGeneration`이고, 파라미터는 BF16 19.9억 개와 F8_E4M3 292.9억 개입니다. 카드에는 시험한 버전으로 vLLM 0.24.0이 적혀 있고, 예시 명령에 `--language-model-only`가 들어 있습니다. 기반 모델 `google/gemma-4-31B-it`도 apache-2.0으로 표기되어 있고 접근 제한(gated)이 없습니다.
- AzatAI 저장소의 `config.json` ignore 목록에는 `re:^mtp.*`가 들어 있고, MTP 헤드는 별도 파일(`model_mtp.safetensors`)로 있습니다. AGENT.md의 함정 항목("양자화 ignore 목록에 `mtp.*`가 없으면 드래프트 수락이 0")이 요구하는 조건을 설정상으로는 만족합니다. 실제 수락률은 3단계에서 지표로 확인합니다.
- AzatAI 저장소는 개인 조직이 올린 것이고 다운로드 수가 422회입니다(공식 FP8은 546만 회). 파일은 safetensors뿐이어서 pickle 실행 위험은 없지만, 적재 Job에서는 위 리비전 해시로 고정해 내려받는 편이 안전합니다.
- 두 Qwen 저장소는 모두 `architectures: Qwen3_5ForConditionalGeneration`, `model_type: qwen3_5`입니다. 파라미터 구성은 AzatAI가 BF16 89.9억 개와 FP8 187.9억 개, 공식 FP8이 BF16 30.8억 개와 FP8 247.0억 개입니다. AzatAI 쪽은 linear_attn 계층을 BF16으로 남겨 두어 파일이 5.9GB 더 큽니다.
- Decider v2 저장소는 가중치를 모두 담고 있어 기반 모델을 따로 받지 않습니다. `decision_config.json`에 기반 모델(`google/gemma-4-12B-it`)과 리비전이 출처로만 적혀 있습니다. v2를 읽으려면 `strands-decider` 0.4.0(2026-11-20) 이상이 필요합니다. 아래 두 항목은 v1을 확인한 2026-11-14의 내용입니다.
- Decider v1 저장소에는 기반 모델 가중치가 없습니다. 코드 저장소 문서에 따르면 로더가 처음 실행될 때 `Qwen/Qwen3.5-2B-Base`(4.57GB, apache-2.0)를 Hugging Face에서 내려받습니다. 같은 파일이 `amazon/strands-decider-2B-qwen3.5-v1-2610`에도 있습니다. 코드는 [strands-labs/strands-decider](https://github.com/strands-labs/strands-decider), PyPI 패키지는 `strands-decider` 0.3.0(2026-11-05)입니다.
- Decider의 공식 서빙 방법은 `strands-decider serve <모델> --port 8000`입니다. 엔드포인트는 `POST /v1/systemone`과 `GET /health`이고, 서버가 예열을 마칠 때까지 `/health`가 실패합니다. 문서는 서버가 기본으로 `127.0.0.1`에 바인딩되고 인증이 없으며 동시 요청 동작은 검증하지 않았다고 적습니다. 저장소의 배포 가이드는 로컬, SageMaker, Lambda 세 가지이고 쿠버네티스 가이드는 없습니다.

### Qwen: 공식 block FP8과 per-channel FP8-dynamic 중 L40S에서 쓸 쪽

| 기준 | per-channel FP8-dynamic (AzatAI) | 공식 block FP8 |
|---|---|---|
| vLLM의 Ada 지원 | 문서의 양자화 지원표가 "llm-compressor FP8 (W8A8)"을 Ada 지원으로 표시합니다(v0.26.0 `docs/features/quantization/README.md`) | CUTLASS block FP8 커널은 SM 9.0 이상에서만 지원합니다. v0.26.0 소스의 주석은 "CUTLASS block-quantized FP8 kernels need at least CUDA 12.0 and at least SM90 (Hopper)"입니다 |
| Ada에서의 동작 | 지원 경로 | 시작이 실패한다는 자료는 찾지 못했습니다. 커널 후보 목록에서 다음 순서의 커널로 내려갑니다. RTX 6000 Ada에서 Marlin FP8 커널로 내려간다는 보고([#58241](https://github.com/vllm-project/vllm/issues/58241), vLLM 0.29.0)와 L40S에서 "Performance might be sub-optimal" 경고가 뜬다는 보고가 있습니다. SM 8.9용 CUTLASS 커널 PR(#61224)은 조회 시점에 열려 있었습니다 |
| 가중치 크기 | 36.78GB (34.3GiB) | 30.87GB (28.7GiB) |
| KV 캐시에 남는 메모리 (계산값) | L40S 44.7GiB의 0.85는 38.0GiB이므로 약 3.7GiB | 약 9.2GiB |
| MTP 헤드 | 별도 파일, 양자화 제외 | 저장소 설정에서 따로 확인하지 않음 |

- 정리하면 두 체크포인트 모두 L40S에서 시작은 될 것으로 보이지만, 문서가 Ada 지원을 명시한 쪽은 per-channel입니다. block은 Ada에서 가장 빠른 커널을 쓰지 못합니다. AGENT.md의 선택(per-channel)을 유지할 근거가 됩니다.
- 대신 per-channel은 가중치가 5.9GB 커서 KV 캐시에 남는 메모리가 적습니다. 위 수치는 파일 크기로 계산한 값이고 측정값이 아닙니다. `--max-model-len 32768`, `--max-num-seqs 32`로 시작되는지와 실제 KV 캐시 크기는 3단계에서 로그로 확인합니다. AGENT.md의 "level 1 sleep은 가중치 약 30GiB를 호스트 RAM에 보존"도 이 체크포인트에서는 약 34GiB가 될 수 있습니다.

## 6. 서비스 할당량과 AZ

`aws service-quotas list-service-quotas --service-code ec2 --region ap-northeast-2`로 조회했습니다.

| 할당량 | 코드 | 현재 값 | 이 구성에 필요한 vCPU | 여유 |
|---|---|---|---|---|
| Running On-Demand G and VT instances | L-DB2E81BA | 768 vCPU | 36 (Gemma g6e.4xlarge 16, Qwen g6e.4xlarge 16, Decider 4. 2026-11-24에 g6.xlarge에서 g6e.xlarge로 바꿨고 vCPU 수는 같음) | 충분 |
| All G and VT Spot Instance Requests | L-3819A6DF | 64 vCPU | 0 | 쓰지 않음 |

- 조회 시점에 실행 중인 G, VT 계열 인스턴스는 없었습니다.
- GPU 노드 세 대는 모두 On-Demand입니다. Qwen은 처음 계획이 Spot이었고 2026-11-14에 On-Demand로 바꿨습니다.

인스턴스 사양(`aws ec2 describe-instance-types`)은 다음과 같습니다.

| 인스턴스 | vCPU | 메모리 | GPU | GPU 메모리 | 네트워크 | 인스턴스 스토어 |
|---|---|---|---|---|---|---|
| g6e.4xlarge | 16 | 128GiB | L40S 1장 | 45,776MiB (44.7GiB) | 20 Gigabit | 600GB |
| g6e.xlarge (2026-11-24부터 Decider) | 4 | 32GiB | L40S 1장 | 45,776MiB (44.7GiB) | Up to 20 Gigabit | 250GB |
| g6.xlarge (2026-11-24까지 Decider) | 4 | 16GiB | L4 1장 | 22,888MiB (22.4GiB) | Up to 10 Gigabit | 250GB |

AZ별 제공 여부(`aws ec2 describe-instance-type-offerings --location-type availability-zone`)는 다음과 같습니다.

| 인스턴스 | 2a (apne2-az1) | 2b (apne2-az2) | 2c (apne2-az3) | 2d (apne2-az4) |
|---|---|---|---|---|
| g6e.4xlarge | 제공 | 제공 | 없음 | 없음 |
| g6e.xlarge | 제공 | 제공 | 없음 | 없음 |
| g6.xlarge | 제공 | 없음 | 제공 | 제공 |

- GPU 노드는 AZ를 가리지 않고 쓰기로 했지만, g6e.4xlarge가 실제로 뜰 수 있는 곳은 2a와 2b 두 곳입니다. eks-vpc는 네 AZ 모두에 Private 서브넷이 있으므로 Karpenter가 2a와 2b에서 g6e.4xlarge를, 2a, 2c, 2d에서 g6.xlarge를 고를 수 있습니다. 2026-11-24에 Decider 노드를 g6e.xlarge로 바꾼 뒤에는 GPU 노드 세 대가 모두 2a와 2b에서만 뜹니다(2026-11-24 조회).
- g6e.4xlarge 1대 기준 Spot placement score는 apne2-az1이 9, apne2-az2가 8입니다(`aws ec2 get-spot-placement-scores --single-availability-zone`, 2026-11-14 조회).
- 최근 24시간 내 g6e.4xlarge Linux Spot 가격은 2a가 시간당 1.7644달러, 2b가 1.8541달러였습니다(`aws ec2 describe-spot-price-history`, 2026-11-13 기준 값).

## 7. 계획과 달라 결정이 필요한 점

1번부터 3번은 최신 버전 조합을 쓰기로 하면서 정해져 AGENT.md와 prompts.md에 반영했고, 6번은 2단계에서 반영했습니다. 5번(`/v1/models`)과 9번(EPP 리소스)은 4단계에서 정해 `docs/04-gateway.md`에 적었고, 8번(Qwen 메모리)은 3단계에서 `--gpu-memory-utilization`을 0.90으로 올려 해결했습니다. 7번(Decider 서빙)은 5단계에서 저장소의 공식 컨테이너 방식으로 정해 `docs/05-decider.md`에 적었습니다. 4번(batch의 429 처리)은 8단계에서 값을 확인했고(`docs/08-results.md`의 우선순위 효과), 배치 작업의 재시도 방식은 아직 정하지 않았습니다.

1. vLLM 버전(반영함). v0.33.0을 씁니다. 1부, 2부와 엔진 버전이 다르면 비교표에 버전을 함께 적습니다.
2. GAIE 구성(반영함). EPP와 InferenceObjective는 GAIE가 아닌 llm-d-router v1.0.0에서 설치합니다. 4단계의 설치 대상에 llm-d-router가 추가되고, InferenceObjective의 API 그룹은 `llm-d.ai`가 됩니다.
3. Objective 헤더(반영함). 7단계의 헤더를 `x-gateway-inference-objective`에서 `x-llm-d-inference-objective`로 바꿨습니다.
4. batch 우선순위. batch를 음수 priority로 두면 기본 설정에서는 풀이 포화될 때 대기하지 않고 429로 거절됩니다. 배치 작업이 재시도하게 하거나 flow control을 켜야 합니다.
5. `/v1/models` 경로. 본문이 없는 요청이라 model 헤더가 만들어지지 않습니다. 두 풀 중 어느 쪽으로 보낼지, 풀별 경로를 따로 둘지 4단계에서 정해야 합니다.
6. Decider의 기반 모델(반영함). 서빙 파드가 S3에서만 읽게 하려면 `Qwen/Qwen3.5-2B-Base`도 S3에 올려야 합니다. 2단계의 적재 대상과 AGENT.md의 S3 구조에 `models/Qwen3.5-2B-Base/`를 추가했습니다. 2026-11-24에 Decider를 v2로 바꾸면서 적재 대상에서 뺐습니다(v2는 기반 모델이 필요 없음).
7. Decider 서빙. 엔드포인트가 `/v1/systemone`이므로 게이트웨이의 `/decide` 경로에서 경로를 바꿔 줘야 합니다. 저장소에 쿠버네티스 배포 가이드가 없고 서버를 로컬 실험용이라고 적고 있어서, 5단계 전에 이 서버를 EKS에 올리는 방식을 그대로 쓸지 확인이 필요합니다.
8. Qwen 메모리 여유. per-channel 체크포인트는 KV 캐시에 남는 메모리가 약 3.7GiB로 계산됩니다(5절). 시작하지 못하면 `--max-model-len`을 낮출지, 공식 block FP8로 바꿀지 정해야 합니다.
9. EPP 리소스. 차트 기본 요청이 CPU 8, 메모리 8Gi여서 시스템 노드 크기를 정하기 전에 값을 낮춰야 합니다.

## 8. 확인하지 못한 항목

- LBC v3.6.3이 쿠버네티스 1.37을 지원한다는 명시 문구. 1단계 적용 뒤 1.37 클러스터에서 컨트롤러 파드 2개가 오류 로그 없이 기동하는 것까지 확인했습니다(2026-11-14). NLB 생성은 4단계에서 확인합니다.
- agentgateway v1.7.0, llm-d-router v1.0.0, GAIE v1.6.2를 함께 시험했다는 문서. agentgateway 1.7.x 문서는 router 차트 v0.9.0을, llm-d v1.0.0 가이드는 agentgateway v1.1.0을 씁니다.
- agentgateway v1.7.0의 GAIE 적합성 보고서(v1.6.0까지만 있음).
- GAIE v1.6.2가 요구하는 Gateway API와 쿠버네티스 최소 버전. 명시 문장이 없고 `go.mod`와 가이드의 고정 버전만 있습니다.
- LBC 어노테이션을 agentgateway가 만든 Service에 붙였을 때의 실제 동작.
- `Exact` path와 InferencePool backendRef를 함께 쓴 문서 예시.
- Qwen3.8-27B per-channel 체크포인트가 v0.33.0에서 로드되는지. 클래스 등록과 릴리스 노트의 Qwen3.8 언급만 확인했습니다.
- llm-d-router v1.0.0의 EPP가 읽는 vLLM 지표 이름이 v0.33.0과 맞는지.
- L40S에서 block FP8 체크포인트가 실제로 고르는 커널과 per-channel 대비 성능 차이.
- sleep 중 `/health`가 200을 반환하는지(코드에서만 확인).
- sleep mode와 높은 `--gpu-memory-utilization` 조합의 시작 실패가 v0.26.0에서 재현되는지. 관련 이슈([#40256](https://github.com/vllm-project/vllm/issues/40256))는 수정 없이 닫혔습니다.
- Qwen의 MTP 헤드가 BF16이어야 한다는 요구 사항의 1차 자료. AGENT.md 함정 항목의 근거를 릴리스 노트, 문서, 이슈에서 찾지 못했습니다.
- CUDA 13.0.2가 요구하는 정확한 최소 드라이버 버전. 대응 브랜치가 R580이라는 것과 AMI 기본 드라이버가 580.178.04라는 것까지 확인했습니다.
- 이미지 안에서 실행한 `vllm serve --help` 출력. 플래그는 태그 소스로 확인했고 이미지는 실행하지 않았습니다.
- v0.33.0에서 이 구성 전체가 동작하는지. 클래스와 플래그가 있는지만 태그 소스에서 확인했습니다. v0.26.0에서 보고된 Gemma 4의 KV 캐시 요구량 증가와 응답 끝 `<turn|>` 문제가 v0.33.0에 남아 있는지도 확인하지 않았습니다.
- Decider가 기반 모델을 로컬 경로에서 읽게 하는 설정 방법과 바인딩 주소를 바꾸는 옵션.
