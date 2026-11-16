# 6단계. Qwen sleep 컨트롤러

2026-11-14에 Qwen의 sleep 운영 구성을 적용하고 sleep 진입과 복귀 시간을 쟀습니다. 원시 자료는 `results/2026-11-14-sleep/`에 있습니다.

## 구성

| 객체 | 내용 |
|---|---|
| CronJob `qwen-sleep` | 평일 19:00(Asia/Seoul)에 `/sleep?level=1&mode=wait` 호출. 이미 잠들어 있으면 아무것도 하지 않음 |
| CronJob `qwen-wake` | 평일 08:30(Asia/Seoul)에 깨우기 API 호출 |
| Deployment, Service `qwen-wake-api` | `POST /wake`만 제공. `/is_sleeping`을 확인하고 잠들어 있으면 `/wake_up`을 호출. ClusterIP, 복제본 2개(2b, 2d) |
| Service `vllm-qwen-admin` | 관리 요청용 헤드리스 Service. NotReady 파드의 주소도 돌려줌 |
| NetworkPolicy `vllm-qwen-ingress` | Qwen의 8000 포트에 게이트웨이, EPP, 깨우기 API, `ow-on-gpu/qwen-admin` 라벨 파드만 허용 |
| NetworkPolicy `qwen-wake-api-ingress` | 깨우기 API의 8080 포트에 `ow-on-gpu/wake-client` 라벨 파드만 허용 |

- 업무 시간은 평일 09:00에서 19:00으로 가정했습니다. 시간은 CronJob의 `schedule`로 바꿉니다.
- `mode=wait`는 진행 중인 요청이 끝난 뒤에 잠들게 합니다. vLLM의 기본값 `abort`는 진행 중인 요청을 끊습니다.
- 잠든 Qwen 파드는 NotReady가 되어 일반 Service(`vllm-qwen`)의 엔드포인트에서 빠집니다. 그래서 `/sleep`, `/wake_up`, `/is_sleeping`은 `vllm-qwen-admin`으로 보냅니다.
- 깨우기 API는 HTTPRoute에 등록하지 않았습니다. 게이트웨이와 NLB로는 닿지 않습니다.

NetworkPolicy를 쓰려고 VPC CNI 애드온에 `enableNetworkPolicy: "true"`를 설정했습니다(`infra/terraform/eks.tf`). 기본값은 꺼짐이어서 그전에는 정책을 만들어도 적용되지 않았습니다. 적용할 때 `aws-node` 데몬셋이 노드 7대에서 37초에 걸쳐 다시 시작됐고, 그동안 두 모델과 Decider는 다시 시작 없이 응답했습니다.

## 측정 방법

`bench/sleep/measure.py`를 클러스터 안의 파드에서 실행해 5회 반복했습니다. 한 번의 순환은 다음과 같습니다.

1. `vllm-qwen-admin`으로 `/sleep?level=1&mode=wait`를 호출하고 응답까지의 시간을 잽니다.
2. 일반 Service에서 파드가 빠질 때까지 기다립니다.
3. 깨우기 API의 `/wake`를 호출하고 응답까지의 시간을 잽니다.
4. 일반 Service가 다시 응답할 때까지, 그리고 게이트웨이로 보낸 대화 요청이 성공할 때까지의 시간을 잽니다.

파드의 Ready 전환 시각은 작업 장비에서 `kubectl get pod -w`로 받은 이벤트의 도착 시각으로 잡았습니다. 측정 파드와 작업 장비의 시계가 다르므로 이 값에는 두 장비의 시계 오차가 들어갑니다.

## 결과

| 항목 | 최소 | 최대 |
|---|---|---|
| sleep 진입 (`/sleep` 응답까지) | 2.977초 | 2.981초 |
| 복귀 (깨우기 API 응답까지) | 3.655초 | 3.662초 |
| 복귀 중 vLLM의 `/wake_up` | 3.637초 | 3.641초 |
| 깨우기 응답 뒤 파드가 Ready로 전환 | 0.03초 | 0.04초 |
| 깨우기 응답 뒤 일반 Service가 다시 응답 | 1.115초 | 1.169초 |
| 깨우기 응답 뒤 게이트웨이의 대화 요청이 성공 | 1.344초 | 1.400초 |
| sleep 응답 뒤 일반 Service에서 빠짐 | 1.808초 | 2.724초 |

- 다섯 번의 값이 거의 같습니다.
- 파드의 Ready 전환은 깨우기 API가 응답한 것과 거의 같은 시각에 일어났습니다. 0.03초는 두 장비의 시계 오차 범위 안이라, "응답과 동시"까지만 말할 수 있습니다.
- BFF 입장에서는 깨우기 요청을 보낸 뒤 약 5초(깨우기 3.66초에 게이트웨이 반영 1.4초)가 지나야 Qwen 요청이 성공합니다. 파드가 Ready가 된 뒤에도 Service와 게이트웨이가 엔드포인트를 다시 잡는 데 1초 남짓 걸립니다.

### 첫 sleep은 훨씬 오래 걸립니다

| 시점 | sleep 진입 시간 |
|---|---|
| 파드가 뜬 뒤 첫 sleep (3단계에서 한 번 측정) | 31.71초 |
| 두 번째 이후 (이 단계, 5회) | 2.98초 |

같은 파드에서 처음 잠들 때만 31.71초가 걸렸고 그 뒤로는 2.98초입니다. 첫 sleep을 다시 재려면 파드를 새로 띄워야 해서 이 단계에서는 반복하지 않았습니다.

### g7e와의 비교

| 항목 | g7e.2xlarge (AGENT.md) | g6e.4xlarge (이번 측정) |
|---|---|---|
| sleep 복귀 | 0.97초 | 3.64초 (`/wake_up`), 3.66초 (깨우기 API) |

모델 체크포인트와 vLLM 버전이 다릅니다. g7e 측정의 조건은 이 저장소에 없으므로 같은 조건의 비교는 아닙니다.

## 잠든 동안의 동작

- 게이트웨이로 보낸 Qwen 요청은 0.02초 만에 HTTP 503을 받습니다. 메시지는 `failed to find endpoint candidates for serving the request`입니다. BFF가 깨우기 API를 먼저 호출해야 하는 이유입니다.
- GPU 메모리는 40,899MiB에서 2,299MiB로 줄어듭니다(3단계 측정).
- 컨테이너 메모리는 sleep을 거친 뒤 60.4GiB로 유지됩니다.

## CronJob 동작 확인

두 CronJob을 수동으로 한 번씩 실행했습니다.

- `qwen-sleep`: `{"action": "sleep", "sleeping": true, "seconds": 2.981}`
- `qwen-wake`: `{"action": "wake", "seconds": 4.702, "was_sleeping": true, "awake": true, "wake_seconds": 3.645}`

일정에 따른 자동 실행은 아직 한 번도 돌지 않았습니다. 적용한 날이 토요일이어서 첫 실행은 다음 평일입니다.

## NetworkPolicy 시험

`inference` 네임스페이스의 임시 파드에서 요청을 보냈습니다(`networkpolicy-test.txt`).

| 보낸 파드 | Qwen 8000 직접 | 깨우기 API | 게이트웨이 경유 Qwen |
|---|---|---|---|
| 라벨 없음 | 차단 | 차단 | 허용 |
| `ow-on-gpu/qwen-admin=true` | 허용 | 차단 | 허용 |
| `ow-on-gpu/wake-client=true` | 차단 | 허용 | 허용 |
| 다른 네임스페이스(`model-jobs`), 두 라벨 모두 | 차단 | 차단 | 허용 |

- 정책이 걸린 파드에서도 kubelet의 probe는 막히지 않습니다. Qwen과 깨우기 API 파드 모두 정책 적용 뒤 Ready를 유지했습니다.
- Gemma의 8000 포트에는 정책을 걸지 않았습니다. 클러스터 안의 어느 파드에서나 닿습니다. Gemma에는 `/sleep`이 없습니다.

## 다음 단계에 영향을 주는 점

- BFF는 ECS Fargate에 있어 ClusterIP Service에 닿지 못합니다. 7단계에서 BFF가 깨우기 API로 들어올 경로를 정하고, `qwen-wake-api-ingress`에 그 경로를 추가해야 합니다. (2026-11-15 변경: BFF를 EKS 파드로 옮겨 깨우기 API의 Service를 직접 부릅니다. 7단계에서 만든 전용 NLB와 TargetGroupBinding은 지웠고, `qwen-wake-api-ingress`는 `ow-on-gpu/wake-client` 라벨 파드와 네임스페이스 `app`의 BFF 파드만 허용합니다. 라벨 없는 파드에서 보낸 요청이 시간 초과로 막히는 것을 다시 확인했습니다.)
- CronJob이 켜져 있으므로 평일 19:00(Asia/Seoul)에 Qwen이 잠듭니다. 그 시간대에 측정하려면 `kubectl -n inference patch cronjob qwen-sleep -p '{"spec":{"suspend":true}}'`로 멈춰 둡니다.
- 8단계에서 Prometheus가 Qwen의 `/metrics`(8000 포트)를 읽으려면 `vllm-qwen-ingress`에 수집기를 추가해야 합니다.

## 측정 중 있었던 일

첫 측정 시도는 스크립트 오류로 첫 순환에서 멈췄습니다. vLLM의 `/health`가 본문 없이 200을 주는데 스크립트가 본문을 JSON으로 읽으려 했습니다. Qwen이 잠든 채 남아서 깨우기 API로 깨운 뒤 스크립트를 고쳐 다시 쟀습니다. 실패한 시도의 출력은 `measure-failed-attempt.*`로 남겼습니다.
