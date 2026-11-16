# 4단계. GAIE와 게이트웨이

2026-11-14에 게이트웨이 계층을 설치하고 클러스터 안에서 시험했습니다. 시험 출력과 리소스 상태는 `results/2026-11-14-gateway/`에 있습니다.

## 설치한 것

| 구성 요소 | 버전 | 설치 방법 |
|---|---|---|
| Gateway API CRD | v1.6.3 (standard) | `kubectl apply --server-side -k k8s/gateway/crds` |
| GAIE CRD (InferencePool) | v1.6.2 | 위와 같음 |
| llm-d-router CRD (InferenceObjective) | v1.0.0 | 위와 같음 |
| agentgateway | v1.7.0 | Helm 차트 `agentgateway-crds`, `agentgateway` (`agentgateway-system` 네임스페이스) |
| EPP와 InferencePool | llm-d-router-gateway v1.0.0 | Helm 릴리스 `gemma`, `qwen` (`inference` 네임스페이스) |

전체 순서는 `k8s/gateway/install.sh apply`에 있고 72초 걸렸습니다. agentgateway v1.7.0과 llm-d-router v1.0.0을 함께 쓴 문서가 없었는데, 이 조합으로 동작합니다.

## 요청 경로

```
클라이언트
  │ HTTP 80
내부 NLB (TCP 80, IP 대상)
  │
agentgateway 파드 2개 (Gateway inference-gateway)
  │ 1. 본문의 model 값을 X-Gateway-Base-Model-Name 헤더로 옮김 (AgentgatewayPolicy, PreRouting)
  │ 2. HTTPRoute가 경로와 헤더로 풀을 고름
  ├─ model=gemma-4-31b ─ InferencePool gemma ─ EPP gemma-epp ─ vllm-gemma
  └─ model=qwen38-27b  ─ InferencePool qwen  ─ EPP qwen-epp  ─ vllm-qwen
```

- Gateway, HTTPRoute, InferencePool은 모두 `Accepted=True`, `ResolvedRefs=True`입니다.
- InferenceObjective는 풀마다 두 개입니다. `gemma-interactive`와 `qwen-interactive`는 priority 10, `gemma-batch`와 `qwen-batch`는 priority -1입니다. 요청은 `x-llm-d-inference-objective` 헤더에 이 이름을 넣습니다.

## 시험 결과

클러스터 안의 임시 파드에서 게이트웨이 Service와 NLB 주소로 요청을 보냈습니다(`gateway-test.txt`).

| 요청 | Service | NLB |
|---|---|---|
| `/v1/chat/completions`, model=gemma-4-31b | 200, Gemma가 응답 | 200, Gemma가 응답 |
| `/v1/chat/completions`, model=qwen38-27b | 200, Qwen이 응답 | 200, Qwen이 응답 |
| `/v1/chat/completions`, 등록하지 않은 model | 404 | 404 |
| `POST /sleep?level=1` | 404 | 404 |
| `POST /sleep?level=1`, 모델 헤더를 직접 넣음 | 404 | 404 |
| `POST /sleep?level=1`, 본문에 model=qwen38-27b | 404 | 404 |
| `POST /wake_up`, `GET /is_sleeping`, `GET /metrics` | 404 | 시험하지 않음 |
| `POST /v1/completions` | 404 | 시험하지 않음 |
| 본문은 gemma, 헤더는 qwen으로 위조 | 200, Gemma가 응답 | 시험하지 않음 |
| `GET /v1/models`, `x-model: gemma-4-31b` | 200, `gemma-4-31b` | 시험하지 않음 |
| `GET /v1/models`, `x-model: qwen38-27b` | 200, `qwen38-27b` | 시험하지 않음 |
| `GET /v1/models`, 헤더 없음 | 404 | 시험하지 않음 |
| objective 헤더 `gemma-interactive`, `gemma-batch`, `qwen-batch` | 200 | 시험하지 않음 |
| `stream: true` | 200, 청크 15개에서 16개, 첫 청크 0.08초와 0.16초 | 시험하지 않음 |

- model 값만 바꿔 두 모델이 각각 응답합니다.
- `/sleep`을 포함해 등록하지 않은 경로는 맞는 rule이 없어 게이트웨이가 404(`route not found`)를 반환합니다. 시험 뒤 Qwen의 `/is_sleeping`은 `false`였습니다.
- 클라이언트가 모델 헤더를 직접 넣어도 본문의 model 값이 덮어씁니다.
- 스트리밍 응답이 청크 단위로 도착합니다. 첫 청크 시간은 한 번 잰 값입니다.

## 내부 NLB

| 항목 | 값 |
|---|---|
| 스킴과 유형 | internal, network |
| 리스너 | TCP 80 하나 |
| 대상 그룹 | IP 대상, TCP 80, 상태 확인 TCP |
| 서브넷 | 2a, 2b, 2c, 2d의 Private 서브넷 |
| 정상 대상 | 게이트웨이 파드 2개(2b, 2d) |
| 보안 그룹 인바운드 | 10.200.0.0/16에서 TCP 80 |
| 교차 영역 분산 | 꺼짐(기본값) |

AWS Load Balancer Controller v3.6.3이 agentgateway가 만든 Service로 NLB를 만들었습니다. Service에는 `loadBalancerClass: service.k8s.aws/nlb`가 자동으로 들어갔습니다.

2026-11-15에 BFF를 EKS 파드로 옮긴 뒤로 BFF는 이 NLB를 거치지 않고 게이트웨이의 Service(`inference-gateway.inference.svc`)를 직접 부릅니다. NLB는 클러스터 밖의 배치 클라이언트용으로 남아 있고, 보안 그룹(`ow-on-gpu-gateway-nlb`)은 배치 클라이언트의 보안 그룹만 허용합니다(`docs/07-bff.md`).

## 파드 배치

| 워크로드 | 복제본 | 배치 |
|---|---|---|
| agentgateway 컨트롤러 | 1 | system NodePool |
| 게이트웨이 파드 | 2 | system NodePool, 2b와 2d에 하나씩 |
| gemma-epp | 2 | 2b(리더, Ready), 2d(대기, NotReady) |
| qwen-epp | 2 | 2b(리더, Ready), 2d(대기, NotReady) |

system NodePool에는 c7i-flex.xlarge 두 대가 2b와 2d에 떠 있습니다.

## 적용하면서 고친 것

- 게이트웨이 파드의 AZ 분산이 처음에는 걸리지 않았습니다. `topologySpreadConstraints`만으로는 system 노드가 한 AZ에만 있을 때 두 파드가 같은 노드에 올라갔고, `minDomains: 2`를 넣은 뒤에는 교체 중에 이전 파드까지 세어 새 파드 둘이 한 AZ에 몰렸습니다. `minDomains: 2`와 `matchLabelKeys: [pod-template-hash]`를 함께 두자 2b와 2d로 나뉘었습니다.
- `GET /v1/models`는 본문이 없어서 model 값으로 고를 수 없습니다. `x-model` 헤더로 모델을 지정하게 했는데, `default()`를 겹쳐 본문 파싱 실패를 받아 내는 식은 본문이 없는 GET에서 동작하지 않았습니다. 요청 메서드로 나누는 식으로 바꿨습니다.

## 알아 둘 동작

- EPP는 풀마다 2개지만 리더 하나만 요청을 처리합니다. 대기 복제본은 설계상 NotReady입니다. 차트 문서에 따르면 리더 장애 후 10초에서 30초 동안 EPP가 없고, 그동안은 `FailOpen` 설정에 따라 게이트웨이가 EPP 없이 풀의 파드로 보냅니다. 이 장애 동작은 시험하지 않았습니다.
- batch의 priority는 -1입니다. flow control이 꺼진 기본 상태에서는 풀이 포화되면 batch 요청이 대기하지 않고 429로 거절됩니다. 포화 상태의 동작은 8단계의 우선순위 측정에서 확인합니다.
- `/v1/models`는 EPP를 거치지 않고 각 모델의 Service로 바로 갑니다. Qwen이 잠들어 있으면 파드가 NotReady라서 응답하지 않습니다.
- NLB는 네 AZ에 있고 대상은 두 AZ에만 있습니다. 교차 영역 분산이 꺼져 있으므로 대상이 없는 AZ의 NLB 노드는 요청을 처리하지 못합니다. NLB 주소로 보낸 시험 요청은 모두 정상이었습니다.

## 확인하지 못한 것

- EPP가 vLLM v0.33.0의 지표(대기 요청 수, KV 캐시 사용률)를 제대로 읽는지. EPP 로그에 수집 오류는 없지만, EPP의 지표 엔드포인트가 인증을 요구해(401) 값을 직접 보지 못했습니다. 8단계에서 인증을 붙여 수집할 때 확인합니다.
- EPP 리더 장애와 게이트웨이 파드 장애 시의 동작.
- 풀이 포화됐을 때 interactive와 batch가 실제로 다르게 처리되는지.
