# k8s 모듈

## Role

클러스터에 적용하는 매니페스트입니다. 디렉터리마다 구성 요소 하나를 담고 kustomize로 묶습니다. 구성 요소의 값과 이유는 `AGENT.md`의 "확정된 결정"과 단계 문서(`docs/03-vllm.md`에서 `docs/07-bff.md`)에 있습니다.

## Key Files

| 디렉터리 | 내용 |
|---|---|
| `base/` | 네임스페이스, NodePool, EC2NodeClass, NVIDIA device plugin, compile 캐시를 내려받는 `cache-restore.py` |
| `gemma/`, `qwen/` | vLLM Deployment와 Service, InferencePool과 EPP 값(`epp-values.yaml`), HTTPRoute와 InferenceObjective(`routes.yaml`) |
| `decider/` | Strands Decider 12B(v2)의 Deployment, Service, HTTPRoute. `install.sh build`, `render`, `diff`, `apply` |
| `gateway/` | Gateway API와 GAIE CRD, agentgateway 값, Gateway. `install.sh`로 적용 |
| `sleep-controller/` | Qwen을 재우고 깨우는 CronJob, 깨우기 API, NetworkPolicy |
| `bff/` | BFF의 NodePool, Deployment, Service, Ingress(내부 ALB). `install.sh render`, `diff`, `apply` |
| `observability/` | 지표 수집기(Prometheus agent)와 대시보드 JSON |
| `bench/` | 측정 Job 전용 NodePool |

## Rules

- 적용 전에 `kubectl diff` 결과를 보여 주고 승인을 받습니다. GPU 노드가 뜨거나 vLLM 파드가 다시 시작되는 변경은 따로 알립니다(콜드 스타트가 몇 분 걸립니다)
- `kubectl diff`는 서버 dry-run이라 클러스터의 웹훅이 더하는 줄까지 보여 줍니다. 내가 쓰지 않은 줄이 있으면 적용하지 않고 무엇이 더하는지 먼저 확인합니다
- 2026-11-16부터 이 클러스터에는 파드 템플릿이 바뀌는 Deployment에 자동 계측 애노테이션을 붙이는 웹훅이 있습니다(`amazon-cloudwatch-observability` 애드온, 이 저장소가 설치하지 않음). `bff/bff.yaml`과 `decider/deployment.yaml`만 `instrumentation.opentelemetry.io/inject-*: "false"`로 거부를 명시했습니다. 다른 Deployment의 템플릿을 바꾸면 계측이 붙습니다(`docs/07-bff.md`)
- CRD 필드, Helm values, vLLM 플래그는 설치된 버전에서 확인합니다(`kubectl explain`, `helm show values`, 이미지 안의 `vllm serve --help`). 확인하지 못한 값은 `TODO(verify)`로 남기고 보고합니다
- vLLM의 Deployment 전략은 Recreate입니다(GPU 한 장에 파드 하나). Qwen의 readinessProbe는 `/is_sleeping`을 봅니다
- 계정 ID가 든 값은 매니페스트 파일에 적지 않습니다. `install.sh`가 Terraform 출력에서 읽어 채웁니다
- `base/params.yaml`(모델 버킷 이름)과 `observability/prometheus.yml`(Prometheus 작업 공간 주소)은 추적하지 않습니다. 추적하는 것은 자리 표시만 든 `*.example`입니다. 새로 받은 저장소에서는 `scripts/setup.sh`가 예시를 복사하고, 값은 `terraform output`(`model_bucket`, `amp_workspace_id`)으로 채웁니다. 실제 파일을 고치면 예시도 함께 고칩니다(시험이 어긋남을 알립니다)
- 자격 증명을 매니페스트에 넣지 않습니다. 권한은 EKS Pod Identity로만 부여합니다
- kubectl은 `KUBECONFIG=infra/terraform/.kubeconfig`으로 씁니다
