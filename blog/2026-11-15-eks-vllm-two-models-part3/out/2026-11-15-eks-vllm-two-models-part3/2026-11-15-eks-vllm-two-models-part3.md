---
title: "두 모델을 하나의 엔드포인트로 – Amazon EKS에서 Gateway API Inference Extension과 BFF로 만드는 모델 라우팅 (3부)"
date: 2026-11-15
author: "Woohyung Choi"
status: draft
---

# 두 모델을 하나의 엔드포인트로 – Amazon EKS에서 Gateway API Inference Extension과 BFF로 만드는 모델 라우팅 (3부)

by WOO HYUNG CHOI on 15 11월 2026 in [Advanced (300)](https://aws.amazon.com/ko/blogs/tech/category/learning-levels/advanced-300/), [Amazon Elastic Kubernetes Service](https://aws.amazon.com/ko/blogs/tech/category/compute/amazon-kubernetes-service/), [Generative AI](https://aws.amazon.com/ko/blogs/tech/category/artificial-intelligence/generative-ai/)

이 글은 시리즈 "Amazon EKS에서 vLLM으로 두 모델 서빙하기"의 3부입니다. 이 시리즈는 Amazon Elastic Kubernetes Service(Amazon EKS)에서 vLLM으로 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙한 기록입니다. 1부(TODO: Part 1 링크)는 콜드 스타트를 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화의 네 구간으로 나눴습니다. 그 결과 Gemma 4 31B의 파드 생성부터 Ready까지가 394초에서 260초로 줄었습니다. 2부(TODO: Part 2 링크)는 SLO 하 처리량을 쟀습니다. SLO는 첫 토큰까지의 시간(TTFT) p99 500ms와 조각 사이의 간격(ITL) p99 50ms입니다. NVIDIA L40S(g6e.4xlarge)에서는 ITL p99가 동시성 1에서도 Gemma 4 31B 57.7ms, Qwen3.8-27B 74.3ms로 기준을 넘었습니다. Qwen3.8-27B는 MTP(Multi-Token Prediction) 설정 때문에 동시에 3건만 실행했고 MTP를 끄면 20건까지 실행했습니다.

두 모델이 각자의 GPU 노드에서 응답하게 된 뒤에도 정할 것이 남습니다. 클라이언트의 요청을 어느 모델로 보낼지 누가 정하는지, 그 판단과 경로가 TTFT에 얼마나 더해지는지입니다. 이 환경에서는 모델 선택을 BFF(Backend for Frontend)와 게이트웨이가 나눠 맡습니다. BFF는 정책과 판단으로 모델을 정해 요청 본문의 `model` 값에 적고 게이트웨이는 그 값으로 모델별 풀을 고릅니다. 이 앞단을 모두 더해도 사용자가 본 첫 내용까지의 시간은 대부분 vLLM이 사용했습니다(Gemma 4 31B는 중앙값 81.9ms 중 63.2ms). 본문의 값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)에서 측정했고 반복 횟수는 측정마다 함께 적었습니다. BFF는 처음에 Amazon Elastic Container Service(Amazon ECS)의 AWS Fargate 태스크로 실행했고 11월 15일에 Amazon EKS의 파드로 옮겼습니다. 본문은 옮긴 뒤의 구성을 기준으로 설명하고 옮기기 전에 확인한 값에는 그 조건을 적었습니다. 이 글은 Amazon EKS에서 GPU 워크로드를 운영하는 플랫폼 엔지니어를 대상으로 하며 Kubernetes Gateway API와 LLM 서빙의 기본 개념을 알고 있다면 무리 없이 읽을 수 있습니다.

## 1. 요청 경로와 역할 분담

측정 환경은 서울 리전의 EKS 1.37, Karpenter 1.15, vLLM v0.33.0입니다. GPU 노드는 g6e.4xlarge 2대(모델마다 1대)와 Strands Decider 2B용 g6.xlarge 1대입니다.

![사용자의 요청이 CloudFront와 AWS WAF, VPC origin, 내부 ALB를 지나 Amazon EKS 클러스터 안의 BFF 파드, agentgateway, 모델별 EPP를 거쳐 Gemma 4 31B와 Qwen3.8-27B의 vLLM 파드에 도달하는 경로. BFF 파드는 게이트웨이와 깨우기 API를 클러스터 안의 Service로 호출하고 배치 작업은 게이트웨이의 내부 NLB로 들어온다.](images/2026-11-15-eks-vllm-two-models-part3-fig01-request-path.png)

*그림 1. 요청 경로와 접근 제한. 게이트웨이 파드, EPP(Endpoint Picker), 깨우기 API, BFF 파드는 각각 2개이고 그림에는 하나씩만 표시했습니다. 점선은 배치 작업이 BFF를 거치지 않고 게이트웨이의 내부 NLB로 들어오는 경로입니다.*

사용자의 요청은 Amazon CloudFront, 내부 Application Load Balancer(ALB), BFF, 게이트웨이를 차례로 지나 vLLM에 도착합니다. 인터넷에 열린 곳은 CloudFront 하나이고 그 뒤의 구성 요소는 모두 VPC 안에 있습니다. BFF부터는 EKS 클러스터 안의 파드이고 BFF는 게이트웨이를 클러스터 안의 Service로 호출합니다. 계층별 역할은 표 1과 같이 나눴습니다.

| 계층 | 구성 요소 | 맡은 일 |
|---|---|---|
| 엣지 | CloudFront, AWS WAF | 정적 페이지와 `/v1/*` 분기, IP별 속도 제한 |
| 앱 | 내부 ALB, BFF(EKS 파드) | 로그인 토큰 검증, 모델과 우선순위 결정, Qwen 깨우기, 도구 실행 |
| 게이트웨이 | agentgateway, EPP, 배치 작업용 내부 NLB | 본문의 `model` 값으로 풀 선택, 노출 경로 제한, 포화 시 배치 요청 거절 |
| 엔진 | vLLM(Gemma 4 31B, Qwen3.8-27B) | 추론, priority 스케줄링 |
| 판단 | Strands Decider 2B | 규칙으로 정해지지 않는 요청의 모델 판단 |

*표 1. 계층별 구성 요소와 역할*

모델 선택에 관여하는 계층은 BFF와 게이트웨이입니다. BFF는 요청의 내용과 정책을 보고 모델을 정해 본문의 `model` 값을 채우고 게이트웨이는 그 값만 보고 풀을 고릅니다. 풀 선택을 게이트웨이에 둔 이유는 배치 작업에 있습니다. 배치 작업은 BFF를 거치지 않고 게이트웨이 앞의 내부 Network Load Balancer(NLB)를 직접 호출하므로, 게이트웨이가 `model` 값으로 라우팅해야 두 경로에 같은 규칙이 적용됩니다. 업무는 모델별로 나눴습니다. 상담, 번역, 요약은 Gemma 4 31B가, 이미지 이해, OCR, 코딩은 Qwen3.8-27B가 맡습니다.

## 2. 본문의 model 값으로 풀을 고르는 게이트웨이

### 2.1 InferencePool, EPP, agentgateway

[Gateway API Inference Extension](https://gateway-api-inference-extension.sigs.k8s.io/)(GAIE)은 Kubernetes Gateway API에 추론 워크로드용 리소스를 더하는 프로젝트입니다. InferencePool은 모델 서버 파드의 묶음으로 HTTPRoute의 백엔드가 되고 EPP는 풀 안에서 요청을 받을 파드를 고릅니다. [GAIE v1.6.0 릴리스 노트](https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/tag/v1.6.0)에 따르면 이 버전부터 EPP와 본문 기반 라우팅(BBR), InferenceObjective가 llm-d 프로젝트로 옮겨졌습니다. 그래서 이 환경은 InferencePool CRD만 GAIE에서 설치하고 EPP와 InferenceObjective는 llm-d-router에서 설치했습니다.

| 구성 요소 | 버전 | 이 환경에서 하는 일 |
|---|---|---|
| Gateway API CRD | v1.6.3 | Gateway, HTTPRoute |
| GAIE CRD | v1.6.2 | InferencePool |
| llm-d-router | v1.0.0 | 풀마다 EPP 2개, InferenceObjective |
| agentgateway | v1.7.0 | 게이트웨이 구현체(파드 2개), 본문 기반 라우팅 |
| AWS Load Balancer Controller | v3.6.3 | 게이트웨이 Service 앞의 내부 NLB, BFF 앞의 내부 ALB |

*표 2. 게이트웨이 계층의 구성 요소와 버전(2026년 11월 14일 기준)*

agentgateway v1.7.0과 llm-d-router v1.0.0을 함께 시험했다는 문서는 찾지 못했고 이 환경에서는 이 조합으로 동작했습니다. CRD부터 Gateway까지 전체 설치는 72초가 걸렸습니다.

이 환경은 풀마다 vLLM 파드가 하나라서 EPP가 고를 대상이 하나뿐입니다. EPP의 스케줄링 시간은 요청당 0.03ms였습니다. 여기서 EPP가 실제로 하는 일은 풀이 포화됐는지 판단해 우선순위가 낮은 요청을 거절하는 것이고 그 효과는 뒤에서 설명할 우선순위 측정에서 확인합니다. EPP는 풀마다 2개를 두었지만 리더 하나만 요청을 처리하고 나머지는 대기합니다. 리더가 응답하지 않으면 게이트웨이가 EPP 없이 풀의 파드로 보내도록 `failureMode: FailOpen`으로 설정했는데 이 장애 동작은 시험하지 않았습니다.

### 2.2 본문 기반 라우팅과 노출 경로 제한

OpenAI 호환 API에서 모델 이름은 URL이 아닌 요청 본문에 있습니다. 경로와 헤더로 백엔드를 고르는 HTTPRoute만으로는 두 모델을 가를 수 없으므로, 라우팅 전에 본문의 `model` 값을 헤더로 옮겨야 합니다. [agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)에 따르면 이 패턴에는 별도의 외부 처리(ext-proc) 서비스가 필요 없고 Gateway를 대상으로 하는 `AgentgatewayPolicy` 하나로 처리합니다.

```yaml
# k8s/gateway/gateway.yaml에서 발췌(주석 생략)
apiVersion: agentgateway.dev/v1alpha1
kind: AgentgatewayPolicy
metadata:
  name: model-routing
spec:
  targetRefs:
    - group: gateway.networking.k8s.io
      kind: Gateway
      name: inference-gateway
  traffic:
    phase: PreRouting
    transformation:
      request:
        set:
          - name: X-Gateway-Base-Model-Name
            value: 'request.method == "GET" ? default(request.headers["x-model"], "") : string(json(request.body).model)'
```

HTTPRoute는 이 헤더와 경로가 모두 정확히 맞는 요청만 풀로 보냅니다.

```yaml
# k8s/gemma/routes.yaml에서 발췌. Qwen의 HTTPRoute는 헤더 값과 풀 이름만 다릅니다.
rules:
  - matches:
      - path:
          type: Exact
          value: /v1/chat/completions
        headers:
          - type: Exact
            name: X-Gateway-Base-Model-Name
            value: gemma-4-31b
    backendRefs:
      - group: inference.networking.k8s.io
        kind: InferencePool
        name: gemma
    timeouts:
      request: 300s
```

경로를 `PathPrefix`가 아닌 `Exact`로 둔 데에는 이유가 있습니다. Qwen 파드의 8000 포트에는 추론 API와 함께 `/sleep`, `/wake_up` 같은 관리 엔드포인트가 열려 있습니다. 등록한 경로만 통과시키면 이 엔드포인트는 맞는 rule이 없어 게이트웨이에서 404로 끝납니다. 표 3은 클러스터 안의 임시 파드에서 게이트웨이 Service로 요청을 보내 확인한 결과입니다.

| 요청 | 결과 |
|---|---|
| `/v1/chat/completions`, `model`은 `gemma-4-31b` | 200, Gemma 4 31B가 응답 |
| `/v1/chat/completions`, `model`은 `qwen38-27b` | 200, Qwen3.8-27B가 응답 |
| `/v1/chat/completions`, 등록하지 않은 `model` | 404 |
| 본문은 gemma, 헤더는 qwen으로 위조 | 200, Gemma 4 31B가 응답 |
| `POST /sleep?level=1` (모델 헤더나 본문의 `model`을 넣은 경우 포함) | 404 |
| `POST /wake_up`, `GET /is_sleeping`, `GET /metrics`, `POST /v1/completions` | 404 |
| `stream: true` | 200, 청크 15개에서 16개로 나뉘어 도착 |

*표 3. 게이트웨이 Service로 보낸 시험 요청과 결과(2026년 11월 14일, 요청마다 한 번)*

클라이언트가 `X-Gateway-Base-Model-Name` 헤더를 직접 넣어도 본문의 `model` 값이 덮어쓰므로, 헤더를 위조해 다른 풀을 고르는 길은 막혀 있습니다. 본문이 없는 `GET /v1/models`만 예외로 `x-model` 헤더를 보고 이 경로는 EPP를 거치지 않고 각 모델의 Service로 갑니다.

구성하면서 고친 것이 두 가지 있습니다. 처음에는 `default()`를 겹쳐 본문 파싱 실패를 받아 내는 식을 사용했는데 본문이 없는 GET에서 동작하지 않아, 위 발췌처럼 요청 메서드로 나누는 식으로 바꿨습니다. 게이트웨이 파드 2개의 AZ 분산도 `topologySpreadConstraints`만으로는 걸리지 않았습니다. `minDomains: 2`와 `matchLabelKeys: [pod-template-hash]`를 함께 두자 두 파드가 서로 다른 AZ에 배치됐습니다.

게이트웨이 앞의 내부 NLB는 AWS Load Balancer Controller가 agentgateway가 만든 Service의 어노테이션을 읽어 만듭니다. 리스너는 TCP 80 하나이고 대상은 게이트웨이 파드의 IP입니다. 이 NLB는 배치 작업이 사용하며 보안 그룹은 배치 클라이언트의 보안 그룹만 허용합니다. BFF는 같은 Service를 클러스터 안에서 직접 호출합니다.

## 3. 배치 부하에서 상담 요청을 지키는 우선순위

Gemma 4 31B는 사용자가 기다리는 상담 요청과, 배치로 처리해도 되는 번역과 요약 요청을 함께 받습니다. 배치 요청이 KV 캐시를 채우고 있을 때 상담 요청이 얼마나 기다리는지가 문제입니다. 이 구성에서 우선순위를 지정하는 곳은 두 군데입니다.

- 게이트웨이: `InferenceObjective`에 priority를 정의하고 요청은 `x-llm-d-inference-objective` 헤더로 그 이름을 고릅니다. [llm-d의 flow control 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md)에 따르면 flow control을 켜지 않은 기본 상태에서는 priority가 0보다 낮은 요청만 다르게 처리합니다. 풀이 포화되면 이런 요청을 대기시키지 않고 HTTP 429로 거절하고 나머지 요청은 그대로 모델 서버로 보냅니다.
- 엔진: vLLM을 `--scheduling-policy=priority`로 실행하고 요청 본문의 `priority`로 지정합니다. [vLLM의 스케줄러 설정 문서](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)에 따르면 값이 작을수록 먼저 처리합니다.

두 값은 방향이 반대입니다. 이 환경에서 상담 요청은 게이트웨이에서 priority 10인 objective를, 엔진에서는 `priority` 0을 받습니다. 배치 요청은 각각 -1과 10입니다. BFF가 결정에 따라 헤더와 본문의 값을 함께 채웁니다.

```yaml
# k8s/gemma/routes.yaml에서 발췌(주석 생략). Qwen에도 같은 두 개가 있습니다.
apiVersion: llm-d.ai/v1
kind: InferenceObjective
metadata:
  name: gemma-interactive
spec:
  priority: 10
  poolRefs:
    - name: gemma
---
apiVersion: llm-d.ai/v1
kind: InferenceObjective
metadata:
  name: gemma-batch
spec:
  priority: -1
  poolRefs:
    - name: gemma
```

어느 쪽이 효과가 있는지 네 가지 경우로 나눠 쟀습니다. Gemma 4 31B에 배치 요청(상품 리뷰 요약, 입력 평균 1,845토큰, 출력 최대 256토큰)을 32개씩 끊임없이 보내 KV 캐시를 채웠습니다. 그 상태에서 상담 요청(짧은 질문, 출력 최대 48토큰)을 1.5초마다 하나씩 90초 동안 60건 보내 TTFT를 쟀습니다. 요청은 모두 게이트웨이를 거쳤고 429로 거절된 배치 요청은 0.5초 뒤에 다시 보냈습니다.

| 경우 | 상담 TTFT p50 | p90 | p99 | 배치 429 거절 | 배치 출력 처리량 | 엔진의 대기 요청 수(평균) |
|---|---:|---:|---:|---:|---:|---:|
| 우선순위 없음 | 30,895ms | 39,154ms | 39,839ms | 0건 | 170.1 tok/s | 31.0 |
| 게이트웨이만 | 11,183ms | 23,081ms | 27,563ms | 1,907건 | 175.7 tok/s | 15.3 |
| 엔진만 | 190ms | 1,244ms | 1,409ms | 0건 | 159.2 tok/s | 17.9 |
| 둘 다 | 193ms | 1,030ms | 1,433ms | 1,988건 | 173.0 tok/s | 9.3 |

*표 4. 배치 부하 중 상담 요청의 TTFT와 배치 처리 결과(Gemma 4 31B, 2026년 11월 14일, 경우마다 90초씩 한 번). "게이트웨이만"은 objective 헤더만, "엔진만"은 본문의 priority만 지정한 경우입니다.*

![Gemma 4 31B에 배치 요청 32개를 계속 보내는 동안 상담 요청의 TTFT를 로그 눈금 막대로 비교한 그래프. 우선순위가 없으면 p50이 30.9초, 게이트웨이 우선순위만 켜면 11.2초, 엔진 우선순위를 켜면 190ms, 둘 다 켜면 193ms이다.](images/2026-11-15-eks-vllm-two-models-part3-fig02-priority-ttft.png)

*그림 2. 배치 부하 중 상담 요청의 TTFT(p50, p90, p99). 세로축은 로그 눈금입니다.*

상담 요청의 대기를 없앤 것은 엔진 우선순위입니다. 우선순위가 없으면 상담 요청이 배치 요청 뒤에서 차례를 기다려 TTFT 중앙값이 30.9초였고 엔진 우선순위를 켜면 0.19초였습니다. 게이트웨이 우선순위만으로는 11.2초였습니다. 게이트웨이는 90초 동안 배치 요청을 1,907건 거절해 엔진의 대기 요청 수를 평균 31.0에서 15.3으로 줄였습니다. 그래도 이미 엔진에 들어간 배치 요청과 같은 순서로 기다리는 것은 그대로였습니다. 둘 다 켠 경우의 상담 TTFT는 엔진만 켠 경우와 같은 수준이고 차이는 엔진의 대기 요청 수(17.9에서 9.3)에 있습니다.

배치의 출력 처리량은 네 경우 모두 초당 159토큰에서 176토큰입니다. 엔진이 포화된 상태에서 우선순위는 처리 순서를 바꿨고 전체 처리량은 바꾸지 않았습니다.

운영에 옮기기 전에 볼 점이 세 가지 있습니다. 배치 클라이언트 32개가 0.5초 간격으로 다시 보내면 90초에 약 1,900건이 429로 돌아오므로, 배치 작업에는 재시도 간격을 늘리는 처리를 넣어야 합니다. 엔진 우선순위를 켜도 p90은 1.2초였습니다. 상담 요청이 들어온 순간 엔진이 긴 배치 입력의 prefill을 처리하고 있으면 그 단계가 끝날 때까지 기다리는 것으로 추정하며 확인하지는 않았습니다. 마지막으로 이 측정은 Gemma 4 31B로만 했고 Qwen3.8-27B 쪽은 재지 않았습니다.

## 4. BFF의 모델 결정 순서와 Strands Decider 2B

### 4.1 규칙을 먼저 적용하는 결정 순서

BFF는 OpenAI 호환 `POST /v1/chat/completions`를 받는 Python 서비스이고 EKS 클러스터의 파드 2개로 실행합니다. 요청마다 판단 모델을 부르면 그 시간이 TTFT에 더해집니다. 그래서 비용이 거의 없는 규칙을 먼저 적용하고 규칙으로 정해지지 않는 요청만 Strands Decider 2B에 묻고 한 번 정한 결과는 세션에 저장해 다시 사용합니다.

![세션에 저장된 결정이 없는 요청을 BFF가 어느 모델로 보낼지 정하는 흐름도. 주민등록번호나 카드번호 형식이 있으면 Gemma 4 31B, 업무 종류가 있으면 배정표의 모델, 이미지가 있으면 Qwen3.8-27B로 보내고, 어느 것에도 해당하지 않을 때만 Strands Decider 2B에 묻는다.](images/2026-11-15-eks-vllm-two-models-part3-fig03-bff-decision.png)

*그림 3. BFF의 모델 결정 순서. 로그인 토큰 검증과 세션 조회는 생략했습니다.*

1. 로그인 토큰을 검증합니다. 통과하지 못하면 401로 끝냅니다.
2. 세션(`x-session-id`)에 저장된 결정이 있으면 그 결정을 사용합니다. 주민등록번호와 카드번호 형식은 세션에 결정이 있어도 메시지마다 다시 확인합니다.
3. 주민등록번호나 카드번호(Luhn 검사 통과) 형식이 있으면 Gemma 4 31B로 보내고 민감으로 표시합니다. Decider를 부르지 않습니다.
4. 업무 종류(`x-task`)가 있으면 배정표를 따릅니다.
5. 업무 종류가 없고 이미지가 첨부되어 있으면 Qwen3.8-27B로 보냅니다.
6. 그 밖에는 게이트웨이의 `/decide` 경로로 Strands Decider 2B에 묻습니다. 응답 실패, 2초 초과, 신뢰도 0.6 미만이면 Gemma 4 31B, thinking 끔, 민감으로 처리합니다.

결정이 나면 BFF는 본문의 `model`, `priority`, `chat_template_kwargs.enable_thinking`과 헤더 `x-llm-d-inference-objective`를 채워 게이트웨이로 보냅니다. 이 환경의 데이터 정책은 민감 정보가 든 요청을 Gemma 4 31B로만 보내도록 정했습니다. Gemma 4 31B는 이 구성에서 이미지를 받지 않으므로, 민감 정보와 이미지가 함께 온 요청은 422로 거절합니다. 어떤 결정이 났는지는 응답 헤더 `x-bff-model`, `x-bff-decision`, `x-bff-sensitive`에 담깁니다.

### 4.2 Strands Decider 2B의 판단 지연

[Strands Decider](https://github.com/strands-labs/strands-decider)는 선택지 가운데 하나를 고르거나 예와 아니오의 확률을 돌려주는 판단 모델입니다. g6.xlarge(NVIDIA L4) 노드 한 대에 배포했고 GPU 메모리는 23,034MiB 중 5,150MiB를 사용합니다. BFF는 요청 하나에 질문 세 개를 담아 보냅니다. 모델 선택(route), 개인정보 포함 여부(policy), 여러 단계의 추론이 필요한지(thinking)입니다. 게이트웨이에서는 HTTPRoute가 `POST /decide`의 경로를 서버의 `/v1/systemone`으로 바꿔 Service로 직접 보냅니다.

| 경로 | 판단 | 중앙값 | p95 |
|---|---|---:|---:|
| Service 직접 | route | 70.1ms | 80.3ms |
| Service 직접 | policy | 70.1ms | 72.2ms |
| Service 직접 | thinking | 70.0ms | 75.7ms |
| 게이트웨이 `/decide` | route | 72.6ms | 78.1ms |
| 게이트웨이 `/decide` | policy | 72.8ms | 75.9ms |
| 게이트웨이 `/decide` | thinking | 73.0ms | 77.3ms |

*표 5. Strands Decider 2B의 판단 지연(2026년 11월 14일, 예열을 켠 구성, 질문 하나를 담은 요청을 판단마다 50회씩 차례로 보낸 값)*

질문 하나의 판단은 약 70ms이고 게이트웨이를 거치면 중앙값이 2.5ms에서 3ms 늘어납니다. BFF가 세 질문을 한 요청에 담아 게이트웨이로 보낸 왕복은 BFF 로그에서 139.4ms에서 150.0ms였습니다(2026년 11월 15일, 4건). 세션의 첫 요청에서 한 번만 묻고 결과를 다시 사용하므로 이 시간은 메시지마다 더해지지 않습니다. 동시 요청을 보냈을 때의 지연은 재지 않았고 서버는 `DECIDER_MAX_CONCURRENCY=1`로 동시 요청을 하나씩 처리합니다.

이 서버는 요청을 받기 전에 질문 종류별로 한 번씩 스스로 실행하는 예열을 기본으로 켭니다. 예열을 끄면 첫 요청 하나가 컴파일 시간을 떠안아 27,968ms가 걸렸고 켜면 첫 요청이 89.9ms였습니다. 대신 컨테이너 시작부터 Ready까지가 23초에서 87초로 늘어납니다. 그동안 BFF는 Decider 응답이 없을 때의 기본 처리(Gemma 4 31B, thinking 끔, 민감)를 사용합니다.

### 4.3 경로별 결정 확인

CloudFront 주소로 요청을 보내 결정과 첫 내용까지의 시간을 확인했습니다. 표 6과 그 아래의 세션 고정 확인은 BFF가 ECS Fargate였던 2026년 11월 14일에 확인한 결과이고 EKS 파드로 옮긴 뒤에는 다시 확인하지 않았습니다.

| 요청 | 모델 | 결정 근거 | 민감 | 사용자가 본 첫 내용 |
|---|---|---|---|---:|
| 상담 (`x-task: support`) | gemma-4-31b | task | false | 1,611ms |
| 번역 (`x-task: translate`) | gemma-4-31b, batch | task | false | 103ms |
| 코딩 (`x-task: coding`), Qwen이 깨어 있음 | qwen38-27b | task | false | 198ms |
| 업무 종류 없음, 코드 수정 요청 | qwen38-27b | decider | false | 355ms |
| 업무 종류 없음, 요약 요청 | gemma-4-31b | decider | false | 241ms |
| 코딩인데 주민등록번호 형식 포함 | gemma-4-31b | rule | true | 92ms |
| 코딩, Qwen이 잠들어 있음 | qwen38-27b | task | false | 4,050ms |

*표 6. 경로별 결정과 사용자가 본 첫 내용까지의 시간(2026년 11월 14일, BFF가 ECS Fargate였던 구성, 요청마다 한 번)*

상담 요청의 첫 내용이 1.6초인 것은 주문 조회 도구 때문입니다. 모델이 먼저 `get_order`를 부르고 BFF가 고정 데이터로 답한 뒤 두 번째 응답에서 내용이 나옵니다. 규칙이나 업무 종류로 결정하는 데는 0.1ms에서 0.5ms가 걸렸습니다. 잠든 Qwen에 보낸 요청은 뒤에서 설명할 깨우기 시간이 더해져 4.05초였습니다.

BFF의 세션 캐시는 파드마다 메모리에 있습니다. 파드가 2개라서 같은 세션의 요청이 다른 파드로 가면 Decider에 다시 묻습니다. 이 문제는 ALB 대상 그룹의 고정 세션(sticky sessions)으로 줄였습니다. 같은 브라우저의 요청은 ALB가 만든 쿠키를 따라 같은 대상으로 갑니다. 11월 14일의 확인에서는 같은 세션 ID로 여섯 번 보냈을 때 쿠키를 함께 보내면 두 번째 요청부터 세션의 결정을 다시 사용했습니다. 쿠키 없이 보내면 두 번째 요청이 다른 태스크로 가서 Decider에 다시 물었습니다. 파드로 옮긴 뒤의 대상 그룹에도 같은 설정(쿠키 고정 1,800초)을 넣었습니다.

Decider 판단의 정확도는 평가하지 않았습니다. 지연 측정에 사용한 한국어 예시 요청 10개 가운데 3개는 모델 선택의 신뢰도가 0.6에 못 미쳤습니다(0.57, 0.30, 0.54). BFF의 기준값 0.6을 적용하면 이런 요청은 기본 처리로 넘어갑니다. 2026년 11월 15일에 업무 종류 없이 보낸 요청 4건에서도 2건은 Decider가 Qwen3.8-27B를 골랐고 2건은 신뢰도가 0.6에 못 미쳐 기본 처리로 넘어갔습니다.

## 5. Qwen3.8-27B의 sleep과 깨우기

내부 업무용인 Qwen3.8-27B는 업무 시간(평일 09:00에서 19:00으로 가정) 밖에는 vLLM의 sleep mode로 재웁니다. [vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)에 따르면 level 1 sleep은 가중치를 GPU에서 내리고 KV 캐시를 비웁니다. 이 환경에서 GPU 메모리 사용량은 40,899MiB에서 2,299MiB로 줄었습니다. sleep은 파드와 노드를 그대로 두므로 노드 요금은 줄지 않습니다. 복귀는 약 3.7초로, 파드를 다시 띄우는 웜 재시작(최적화 구성에서 123초, 1부에서 다룸)보다 짧습니다.

| 객체 | 내용 |
|---|---|
| CronJob `qwen-sleep` | 평일 19:00(Asia/Seoul)에 `/sleep?level=1&mode=wait` 호출 |
| CronJob `qwen-wake` | 평일 08:30(Asia/Seoul)에 깨우기 API 호출 |
| Deployment `qwen-wake-api` | `POST /wake`만 제공. `/is_sleeping`을 확인하고 잠들어 있으면 `/wake_up` 호출. 복제본 2개 |
| Service `vllm-qwen-admin` | 관리 요청용 헤드리스 Service. NotReady 파드의 주소도 돌려줌 |
| NetworkPolicy 2개 | Qwen의 8000 포트와 깨우기 API의 8080 포트에 정해진 파드만 허용 |

*표 7. Qwen3.8-27B의 sleep 운영 구성*

재우는 쪽에서는 진행 중인 요청을 끊지 않는 것이 먼저입니다. `/sleep`에 `mode=wait`를 주면 진행 중인 요청이 끝난 뒤에 잠들고 기본값 `abort`는 진행 중인 요청을 중단합니다. 이 인자는 sleep mode 문서 페이지에 설명이 없어 vLLM v0.33.0의 소스에서 확인했습니다.

잠든 파드가 요청을 받지 않게 하는 일은 readinessProbe가 맡습니다. vLLM의 `/health`는 sleep 중에도 200을 반환하므로 `/is_sleeping`으로 판정하는 exec probe로 바꿨습니다. 잠든 파드는 NotReady가 되어 일반 Service의 엔드포인트에서 빠지고 관리 요청은 `publishNotReadyAddresses: true`인 헤드리스 Service로 보냅니다.

관리 엔드포인트에 닿는 경로는 좁혔습니다. vLLM 문서는 `VLLM_SERVER_DEV_MODE=1`로 열리는 이 엔드포인트를 사용자에게 노출하지 말라고 안내합니다. 깨우기 API는 깨우는 동작만 하고 이 API로는 모델을 재울 수 없습니다. 게이트웨이의 HTTPRoute에 등록하지 않는 것에 더해 NetworkPolicy로 Qwen 파드의 8000 포트에 닿는 파드를 제한했습니다.

```yaml
# k8s/sleep-controller/networkpolicies.yaml에서 발췌(주석과 일부 출발지 생략)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: vllm-qwen-ingress
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: vllm-qwen
  policyTypes: ["Ingress"]
  ingress:
    - ports:
        - protocol: TCP
          port: 8000
      from:
        - podSelector:
            matchLabels:
              gateway.networking.k8s.io/gateway-name: inference-gateway
        - podSelector:
            matchLabels:
              llm-d-router-gateway: qwen-epp
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: qwen-wake-api
```

NetworkPolicy를 적용하려면 Amazon VPC CNI 애드온의 구성 값에 `enableNetworkPolicy: "true"`를 넣어야 합니다. 이 값을 넣기 전에는 정책을 만들어도 적용되지 않았습니다. 값을 넣을 때 `aws-node` 데몬셋이 노드 7대에서 37초에 걸쳐 다시 시작됐고 그동안 두 모델과 Decider는 다시 시작 없이 응답했습니다.

| 항목 | 최소 | 최대 |
|---|---:|---:|
| sleep 진입 (`/sleep` 응답까지) | 2.977초 | 2.981초 |
| 복귀 (깨우기 API 응답까지) | 3.655초 | 3.662초 |
| 깨우기 응답 뒤 일반 Service가 다시 응답 | 1.115초 | 1.169초 |
| 깨우기 응답 뒤 게이트웨이의 대화 요청이 성공 | 1.344초 | 1.400초 |

*표 8. sleep 진입과 복귀 시간(2026년 11월 14일, 같은 파드에서 5회 반복)*

다섯 번의 값이 거의 같습니다. 복귀 자체는 3.66초이고 그 뒤 Service와 게이트웨이가 엔드포인트를 다시 잡는 데 1초 남짓 더 걸립니다. 파드가 뜬 뒤 첫 sleep만은 31.71초가 걸렸고 새 파드에서 다시 재도 같았습니다. 2026년 11월 15일에 다시 쟀을 때는 31.77초였습니다.

잠든 동안 게이트웨이로 보낸 Qwen 요청은 0.02초 만에 HTTP 503을 받습니다. 그래서 BFF는 Qwen으로 갈 요청마다 깨우기 API를 먼저 호출하고 잠들어 있었다면 게이트웨이의 503을 최대 10초 동안 0.2초 간격으로 다시 시도합니다. BFF를 EKS 파드로 옮긴 뒤인 2026년 11월 15일에 잠든 Qwen에 코딩 요청을 한 번 보냈습니다. 깨우기 API 호출이 3,662ms, 응답 헤더까지 3.91초, 첫 내용까지 4.06초였습니다. 표 6의 4,050ms는 BFF를 옮기기 전에 같은 요청을 보낸 값입니다. Qwen이 깨어 있을 때도 이 호출은 요청마다 일어나며 20건의 중앙값이 12.8ms(9.7ms에서 21.8ms)였습니다.

두 CronJob은 수동으로 한 번씩 실행해 동작을 확인했습니다. 일정에 따른 자동 실행은 측정 시점까지 확인하지 못했습니다. 적용한 날이 토요일이었기 때문입니다.

## 6. CloudFront에서 BFF까지의 앱 계층

### 6.1 CloudFront VPC origins와 Ingress로 만드는 내부 ALB

CloudFront 배포의 기본 경로는 Amazon Simple Storage Service(Amazon S3)의 정적 페이지를 오리진 액세스 제어(OAC)로 읽고 `/v1/*`만 내부 ALB로 보냅니다. 내부 ALB는 [CloudFront VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)로 연결했습니다. 프라이빗 서브넷의 ALB, NLB, EC2 인스턴스를 오리진으로 사용하는 기능이고 Terraform에서는 `aws_cloudfront_vpc_origin` 리소스로 만듭니다. VPC origin을 만들면 CloudFront가 `CloudFront-VPCOrigins-Service-SG`라는 보안 그룹을 VPC에 만듭니다. 내부 ALB의 보안 그룹은 이 보안 그룹에서 오는 80 포트만 허용합니다.

내부 ALB는 AWS Load Balancer Controller가 BFF의 Ingress에서 만듭니다. ALB의 설정은 Ingress의 어노테이션으로 지정합니다.

```yaml
# k8s/bff/bff.yaml의 Ingress에서 발췌(주석 생략). ${ALB_LOG_BUCKET}은 설치 스크립트가 채우는 자리입니다.
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: bff
  namespace: app
  annotations:
    alb.ingress.kubernetes.io/load-balancer-name: ow-on-gpu-bff-pods
    alb.ingress.kubernetes.io/scheme: internal
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}]'
    alb.ingress.kubernetes.io/security-groups: ow-on-gpu-bff-alb
    alb.ingress.kubernetes.io/manage-backend-security-group-rules: "true"
    alb.ingress.kubernetes.io/healthcheck-path: /healthz
    alb.ingress.kubernetes.io/load-balancer-attributes: idle_timeout.timeout_seconds=120,access_logs.s3.enabled=true,access_logs.s3.bucket=${ALB_LOG_BUCKET},access_logs.s3.prefix=bff
    alb.ingress.kubernetes.io/target-group-attributes: deregistration_delay.timeout_seconds=30,stickiness.enabled=true,stickiness.type=lb_cookie,stickiness.lb_cookie.duration_seconds=1800
spec:
  ingressClassName: alb
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: bff
                port:
                  number: 8080
```

| 어노테이션 | 이 환경의 값 | 동작 |
|---|---|---|
| `scheme` | `internal` | 인터넷에 노출하지 않는 내부 ALB로 생성 |
| `target-type` | `ip` | 파드의 IP를 대상으로 등록. ALB의 고정 세션을 사용하려면 이 유형이 필요 |
| `security-groups` | `ow-on-gpu-bff-alb` | ALB에 연결할 보안 그룹을 직접 지정. 이름은 보안 그룹의 `Name` 태그와 대조 |
| `manage-backend-security-group-rules` | `"true"` | 컨트롤러가 공용 백엔드 보안 그룹을 ALB에 추가로 연결하고 노드와 파드 쪽 보안 그룹 규칙에 사용 |
| `load-balancer-attributes` | 유휴 제한 시간 120초, Amazon S3 접근 로그 | ALB 속성을 지정. 어노테이션에 적은 속성만 갱신 |
| `target-group-attributes` | 등록 해제 지연 30초, ALB 쿠키 고정 1,800초 | 대상 그룹 속성을 지정 |

*표 9. 내부 ALB를 만드는 Ingress의 어노테이션. 이름 앞의 `alb.ingress.kubernetes.io/`는 생략했고 동작은 AWS Load Balancer Controller 문서의 설명입니다.*

[AWS Load Balancer Controller의 Ingress 어노테이션 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/)에 따르면 `security-groups`를 지정하지 않으면 컨트롤러가 보안 그룹을 하나 만들어 ALB에 연결합니다. 노드와 파드의 보안 그룹도 그 그룹에서 오는 트래픽을 받도록 함께 고칩니다. 직접 지정한 경우에는 노드와 파드가 ALB의 트래픽을 받도록 사용자가 보안 그룹 규칙을 구성해야 합니다. `manage-backend-security-group-rules`를 `true`로 두면 이 규칙도 컨트롤러가 관리합니다. 이 환경에서는 ALB로 들어오는 쪽을 Terraform으로 만든 보안 그룹이 CloudFront VPC origin으로 제한합니다. ALB에서 BFF 파드로 가는 쪽은 컨트롤러가 관리합니다. 컨트롤러는 ALB에 백엔드 보안 그룹을 추가로 연결했고 파드가 사용하는 클러스터 보안 그룹의 인바운드 규칙에 그 그룹을 넣었습니다.

서브넷은 어노테이션에 적지 않았습니다. [서브넷 자동 탐색 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/subnet_discovery/)에 따르면 컨트롤러는 내부 로드 밸런서의 후보로 `kubernetes.io/role/internal-elb` 태그가 있는 프라이빗 서브넷을 찾고 AZ마다 하나를 고릅니다. 컨트롤러는 이 환경의 ALB를 AZ 네 곳의 프라이빗 서브넷에 만들었습니다.

유휴 제한 시간, 접근 로그, 쿠키 고정에는 BFF가 ECS Fargate였을 때 Terraform으로 만든 ALB와 같은 값을 넣었습니다. ALB 가운데 Terraform에 남긴 것은 보안 그룹과 CloudFront 쪽 연결입니다. Terraform은 컨트롤러가 만든 ALB를 태그(`ingress.k8s.aws/stack`)로 조회해 VPC origin의 대상으로 지정합니다.

### 6.2 Graviton 노드에서 실행하는 BFF 파드

BFF 파드 2개는 네임스페이스 `app`에서 실행되고 Karpenter가 관리하는 전용 NodePool `app`의 노드에 배치됩니다. 이 NodePool은 arm64 아키텍처(AWS Graviton)의 c와 m 계열 7세대 이상 가운데 vCPU가 2개인 On-Demand 인스턴스만 고릅니다. taint(`ow-on-gpu/app`)로 다른 파드를 막고 `limits`에 CPU 8개를 두어 노드가 의도와 다르게 늘지 않게 했습니다. 2026년 11월 15일에 Karpenter는 이 NodePool에서 c7g.large 2대를 서로 다른 AZ에 만들었습니다.

BFF 파드는 `nodeSelector`(`karpenter.sh/nodepool: app`)와 toleration으로 이 노드만 고르고 `topologySpreadConstraints`로 AZ 두 곳에 나뉩니다. 게이트웨이 파드를 구성할 때 확인한 대로 `minDomains: 2`와 `matchLabelKeys`를 함께 두었습니다. 자원은 CPU 500m과 메모리 512Mi를 요청하고 메모리 한도는 1Gi입니다. 종료할 때는 `preStop`에서 15초를 기다려 ALB가 파드를 대상에서 뺄 시간을 두었습니다. 파드 하나가 내려갈 때 진행 중인 스트림이 어떻게 되는지는 확인하지 않았습니다.

BFF는 게이트웨이와 깨우기 API를 클러스터 안의 Service 주소로 호출합니다. 게이트웨이는 네임스페이스 `inference`의 Service `inference-gateway`이고 깨우기 API는 같은 네임스페이스의 Service `qwen-wake-api`(8080 포트)입니다. 두 호출 모두 로드 밸런서를 거치지 않습니다.

BFF가 AWS 자격 증명으로 호출하는 API는 뒤에서 설명할 웹 검색 하나입니다. [EKS Pod Identity](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)는 IAM 역할을 Kubernetes ServiceAccount에 연결해 파드에 자격 증명을 주는 기능입니다. 웹 검색 권한(`bedrock-agentcore:InvokeWebSearch`)만 가진 역할을 네임스페이스 `app`의 ServiceAccount `bff`에 연결했습니다. 로그인 토큰 검증은 공개 키만 읽으므로 AWS 권한이 필요하지 않습니다.

### 6.3 접근 제한

CloudFront 뒤로는 구간마다 정해진 출발지만 허용했습니다.

| 대상 | 허용하는 출발지 | 수단 |
|---|---|---|
| 내부 ALB (80) | CloudFront VPC origin의 보안 그룹 | 보안 그룹 |
| BFF 파드 (8080) | 내부 ALB에 연결된 백엔드 보안 그룹. 클러스터 안의 파드는 따로 제한하지 않음 | 보안 그룹 |
| 게이트웨이 내부 NLB (80) | 배치 클라이언트의 보안 그룹 | 보안 그룹 |
| 깨우기 API 파드 (8080) | 네임스페이스 `app`의 BFF 파드, `ow-on-gpu/wake-client` 라벨 파드 | NetworkPolicy |
| Qwen 파드 (8000) | 게이트웨이, EPP, 깨우기 API, 지표 수집기, `ow-on-gpu/qwen-admin` 라벨 파드 | NetworkPolicy |

*표 10. 구간별 접근 제한*

깨우기 API를 호출할 수 있는 파드는 NetworkPolicy로 정했습니다. BFF가 클러스터 안의 파드이므로 출발지를 파드의 라벨로 지정합니다.

```yaml
# k8s/sleep-controller/networkpolicies.yaml에서 발췌(주석 생략)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: qwen-wake-api-ingress
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: qwen-wake-api
  policyTypes: ["Ingress"]
  ingress:
    - ports:
        - protocol: TCP
          port: 8080
      from:
        - podSelector:
            matchLabels:
              ow-on-gpu/wake-client: "true"
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: app
          podSelector:
            matchLabels:
              app.kubernetes.io/name: bff
```

허용하는 출발지는 네임스페이스 `app`의 BFF 파드와 `ow-on-gpu/wake-client` 라벨이 있는 파드입니다. 이 라벨은 깨우기 CronJob의 파드에 넣었습니다.

2026년 11월 15일에 클러스터 안에 라벨 없는 파드를 띄워 확인했을 때 깨우기 API의 Service로 보낸 요청은 시간 초과였습니다. 남아 있는 틈도 있습니다. 같은 파드에서 BFF의 Service와 게이트웨이의 Service로 보낸 요청은 200이었습니다. BFF의 `/v1/*`는 클러스터 안에서 온 요청에도 로그인 토큰을 요구하지만 게이트웨이의 Service는 표 3의 시험처럼 토큰 없이 추론 요청을 받습니다. Gemma 파드의 8000 포트에는 NetworkPolicy를 걸지 않았고 CloudFront와 내부 ALB 사이도 VPC 안에서 HTTP로 통신합니다.

### 6.4 로그인과 속도 제한

CloudFront 주소는 누구나 열 수 있으므로 `/v1/*` 요청에는 Amazon Cognito 로그인을 요구합니다. 정적 페이지가 브라우저에서 Cognito의 `InitiateAuth`(`USER_PASSWORD_AUTH` 흐름)를 직접 호출하므로 비밀번호는 BFF를 거치지 않습니다. BFF는 사용자 풀의 공개 키(JWKS)로 액세스 토큰의 서명을 확인하고 발급자, 만료 시각, `token_use`, 앱 클라이언트 ID를 확인합니다. 앱 클라이언트 ID가 정적 페이지에 드러나므로 사용자 풀의 가입은 막았습니다.

인증은 BFF에서 합니다. 로그인하지 않은 요청도 CloudFront와 ALB를 지나 BFF까지는 도달하고 거기서 401을 받습니다. BFF를 파드로 옮긴 뒤에도 토큰 없는 요청과 틀린 토큰을 넣은 요청은 401이었습니다. 토큰 없는 요청 6건은 두 파드의 로그에 3건씩 기록됐습니다. BFF 앞에서 막는 장치는 AWS WAF의 속도 기반 규칙(rate-based rule) 하나이고 IP 하나가 5분에 300회를 넘으면 차단하도록 설정했습니다.

이 규칙이 언제 작동하는지는 BFF가 ECS Fargate였던 2026년 11월 14일에 한 번 쟀고 파드로 옮긴 뒤에는 다시 재지 않았습니다. 정적 페이지에 0.5초 동안 400번을 연달아 요청하자 400번이 모두 200이었고 첫 403은 요청을 시작하고 25.6초 뒤에 나왔습니다. 차단은 첫 403에서 300.4초 뒤에 풀렸습니다. [AWS WAF 문서](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)에 따르면 속도 기반 규칙은 정밀한 요청 수 제한용이 아니며 감지까지의 지연은 보통 30초 미만입니다. 짧은 시간에 몰아서 보내는 요청은 한도보다 많이 통과한다는 점을 전제로 사용해야 합니다.

### 6.5 스트리밍에 맞춘 타임아웃

LLM 응답은 첫 토큰 전에 수 초 동안 아무것도 흐르지 않을 수 있고(판단, Qwen 깨우기), 그 뒤로는 수십 ms 간격으로 조각이 이어집니다. 경로의 타임아웃은 이 두 구간에 맞춰 정했습니다.

| 설정 | 값 | 근거 |
|---|---|---|
| CloudFront 오리진 응답 타임아웃 | 60초 (기본 30초) | 첫 바이트까지, 그리고 패킷 사이에 기다리는 시간. 잠든 Qwen에 보낸 요청은 응답 헤더까지 3.91초 |
| ALB 유휴 제한 시간(idle timeout) | 120초 (기본 60초) | CloudFront가 먼저 끊도록 그보다 길게 설정 |
| HTTPRoute의 요청 타임아웃 | 300초 | 확인용 페이지의 최대 출력 4,096토큰이 이 안에 끝남(Gemma 4 31B는 약 3분) |
| Decider 호출 | 2초 | 넘으면 기본 처리 |
| 깨우기 API 호출 | 60초 | 측정한 복귀 시간은 3.66초 |
| 깨운 뒤 503 재시도 | 최대 10초, 0.2초 간격 | 게이트웨이가 엔드포인트를 다시 잡는 데 1.4초 |

*표 11. 스트리밍 경로의 타임아웃 설정*

CloudFront의 오리진 응답 타임아웃은 Terraform에서 `origin_read_timeout`으로 지정합니다. [CloudFront 할당량 문서](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html)의 범위는 1초에서 120초이고 이 환경은 60초로 설정했습니다. ALB의 유휴 제한 시간은 Ingress의 `load-balancer-attributes` 어노테이션으로 지정합니다. `/v1/*` 동작은 캐시와 압축을 모두 껐습니다. 응답이 중간에서 모였다가 나오지 않게 하려는 설정입니다.

스트리밍이 끝까지 유지되는지는 BFF를 파드로 옮긴 뒤 상담 요청 하나를 CloudFront 주소로 보내 확인했습니다. 내용이 담긴 SSE 이벤트 53개가 간격 중앙값 53.5ms(최소 49.3ms, 최대 59.1ms)로 하나씩 도착했고 1ms 안에 붙어서 온 이벤트는 없었습니다. CloudFront, ALB, BFF 어디에서도 응답이 모였다가 나온 흔적이 없습니다. 응답이 60초 넘게 한 글자도 나오지 않는 경우의 동작은 재현하지 않았습니다.

## 7. 구간별 TTFT

지금까지의 계층을 모두 지난 요청에서 각 구간이 첫 내용까지의 시간을 얼마나 사용하는지 쟀습니다. BFF를 EKS 파드로 옮긴 뒤인 2026년 11월 15일에 서울 리전의 EC2에서 CloudFront 주소로 요청을 하나씩 보냈습니다. 모델마다 20건이고(연결을 여는 첫 요청 1건은 제외), 최대 출력은 32토큰입니다. Gemma 4 31B에는 상담 업무로 도구를 부르지 않는 질문을, Qwen3.8-27B에는 코딩 업무의 짧은 질문을 보냈습니다.

구간은 요청마다 기록을 이어서 나눴습니다. 사용자 쪽은 클라이언트가 잰 시각, CloudFront는 응답의 `Server-Timing` 헤더, ALB는 접근 로그를 사용했습니다. BFF는 파드의 표준 출력에 남긴 로그, vLLM은 요청 전후의 지표 차이(`vllm:time_to_first_token_seconds`)입니다. ALB 로그와 BFF 로그는 `X-Amzn-Trace-Id`로, BFF 로그와 클라이언트 기록은 요청 ID로 이었고 40건 모두 여섯 구간이 이어졌습니다.

| 구간 | Gemma 4 31B 중앙값 | Gemma 4 31B 최대 | Qwen3.8-27B 중앙값 | Qwen3.8-27B 최대 |
|---|---:|---:|---:|---:|
| 사용자와 엣지 사이 | 1.8ms | 3.2ms | 1.9ms | 5.0ms |
| CloudFront | 5.0ms | 79.0ms | 5.0ms | 9.0ms |
| ALB | 1.6ms | 4.2ms | 1.6ms | 12.7ms |
| BFF | 0.1ms | 0.1ms | 12.8ms | 21.9ms |
| 게이트웨이 (agentgateway, EPP) | 9.7ms | 16.4ms | 8.4ms | 78.0ms |
| vLLM | 63.2ms | 66.6ms | 147.6ms | 160.0ms |
| 사용자가 본 첫 내용 | 81.9ms | 153.6ms | 177.5ms | 253.1ms |

*표 12. 구간별 TTFT(2026년 11월 15일, BFF를 EKS 파드로 옮긴 뒤, 서울 리전의 EC2에서 요청을 하나씩, 모델마다 20건). 구간별 중앙값이므로 합이 마지막 행과 정확히 일치하지 않습니다.*

![사용자가 본 첫 내용까지의 시간을 여섯 구간으로 나눈 가로 막대 그래프. Gemma 4 31B는 중앙값 81.9ms 중 vLLM이 63.2ms, Qwen3.8-27B는 177.5ms 중 vLLM이 147.6ms이고, 나머지 구간은 BFF의 Qwen 12.8ms를 빼면 모두 10ms 미만이다.](images/2026-11-15-eks-vllm-two-models-part3-fig04-ttft-segments.png)

*그림 4. 구간별 TTFT 중앙값. 위 여섯 행이 구간이고 맨 아래 행이 사용자가 본 첫 내용입니다.*

첫 내용까지의 시간은 대부분 vLLM이 사용합니다. Gemma 4 31B는 81.9ms 중 63.2ms(77%), Qwen3.8-27B는 177.5ms 중 147.6ms(83%)입니다. vLLM의 TTFT는 거의 다 prefill입니다. 요청을 하나씩 보냈으므로 대기열 시간은 두 모델 모두 0ms였고 prefill이 각각 58.8ms와 144.4ms였습니다.

사용자에서 게이트웨이까지의 경로 구간을 중앙값으로 더하면 Gemma 4 31B 18.2ms, Qwen3.8-27B 29.7ms입니다. Qwen 쪽이 긴 것은 BFF가 Qwen 요청마다 깨우기 API를 한 번 호출하기 때문입니다(중앙값 12.8ms). 게이트웨이 구간은 agentgateway와 EPP를 합쳐 9.7ms와 8.4ms였습니다. BFF가 게이트웨이의 Service를 직접 호출하므로 이 구간에 NLB는 들어 있지 않습니다.

두 모델 모두 최댓값은 요청 한 건에서 나왔습니다. Gemma 4 31B의 153.6ms는 CloudFront 구간이 79ms였던 요청입니다. Gemma 4 31B의 CloudFront 구간은 20건 중 18건이 3ms에서 7ms였고 나머지 2건이 13ms와 79ms였습니다. Qwen3.8-27B의 CloudFront 구간은 20건 모두 4ms에서 9ms였습니다. Qwen3.8-27B의 253.1ms는 게이트웨이 구간이 78.0ms였던 요청이고 나머지 19건의 게이트웨이 구간은 14.9ms 이하였습니다. 두 경우 모두 원인은 확인하지 않았습니다.

이 표의 값은 세 가지 조건에서 잰 것입니다. 측정 장비가 같은 리전의 EC2라서 사용자와 엣지 사이의 시간이 짧고 다른 지역의 사용자는 이 구간이 늘어납니다. 이미 열린 연결로 보낸 요청의 값이며 TLS 연결을 새로 여는 데는 14.5ms와 14.2ms가 걸렸습니다. 요청을 하나씩 보낸 값이기도 합니다. 부하가 걸리면 배치 부하 측정에서 본 것처럼 vLLM의 대기 시간이 초 단위로 더해집니다.

측정 방법에도 주의할 점이 하나 있습니다. vLLM은 요청을 받자마자 응답 헤더를 보내므로 응답 헤더는 첫 내용보다 먼저 도착합니다(Gemma 19.8ms, Qwen 32.4ms). `Server-Timing`과 ALB 로그의 값은 응답 헤더까지의 시간이어서, 경로의 시간은 그 값으로 나누고 생성의 시간은 vLLM 지표로 나눴습니다.

## 8. BFF의 도구로 추가한 웹 검색

2026년 11월 15일에 BFF에 웹 검색 도구를 더했습니다. 추론은 그대로 Gemma 4 31B와 Qwen3.8-27B가 하고 검색만 [Amazon Bedrock AgentCore Web Search](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)가 합니다. API 이름은 `InvokeWebSearch`입니다. 요청이 `x-web-search: on` 헤더를 보내면 BFF가 모델 요청에 `web_search` 도구와 지시문을 넣습니다. 모델이 도구를 부르면 BFF가 `InvokeWebSearch`를 호출하고 결과에 번호를 매겨 모델에 돌려줍니다. 검색할지와 무엇을 검색할지는 모델이 정하고 한 요청에서 도구를 부를 수 있는 차례는 3번입니다.

BFF에는 주문 조회 도구를 실행하는 흐름이 이미 있어서 게이트웨이와 vLLM의 구성은 바꾸지 않았습니다. 이 API는 서울 리전에서 제공되지 않아 이 환경은 us-east-1의 API를 호출하도록 구성했습니다. 검색어가 서울 리전 밖으로 나가므로 민감 정보가 있는 요청에는 도구를 넣지 않고 모델이 만든 검색어에 주민등록번호나 카드번호 형식이 있으면 그 검색도 보내지 않습니다. 검색은 쿼리 1,000건당 7.00 USD의 요금이 있고 도구 정의만큼 프롬프트가 길어지므로, 요청이 켰을 때만 도구를 넣습니다. 이용 조건이 검색 결과를 사용한 출력에 출처와 링크를 표시하도록 요구하므로 답변 아래의 출처 목록은 화면이 직접 표시합니다.

서울의 BFF가 us-east-1의 API를 호출한 시간은 요청 8건에서 485ms에서 662ms(중앙값 568ms)였습니다. 이 값은 BFF를 파드로 옮기기 전에 잰 것이고 옮긴 뒤에는 두 파드에서 검색을 한 번씩 호출해 결과가 돌아오는 것만 확인했습니다. 검색을 사용한 요청은 도구 호출, 검색, 결과를 넣은 두 번째 추론이 첫 내용 앞에 놓이므로 첫 내용이 그만큼 늦어집니다.

## 9. 고정 비용

| 항목 | 시간당 |
|---|---:|
| 내부 ALB | 0.0225 USD |
| c7g.large 2대 (BFF용 Graviton 노드, 대당 0.0816 USD) | 0.1632 USD |
| 합계 | 0.1857 USD |

*표 13. 앱 계층의 시간당 고정 비용(2026년 11월 15일 기준, 서울 리전, 세전 USD). 사용량에 따라 부과되는 ALB의 처리 단위, CloudFront 전송량, AWS WAF, Amazon Cognito 요금은 포함하지 않았습니다.*

이 환경 전체의 고정 비용은 시간당 약 10.05 USD로 추정됩니다. 앱 계층의 0.1857 USD는 그 가운데 약 1.8%입니다. 첫 내용까지의 시간과 마찬가지로 비용에서도 앞단이 차지하는 몫은 작습니다.

## 10. BFF를 ECS Fargate에서 EKS 파드로 옮긴 전과 후

BFF는 처음에 ECS Fargate 태스크 2개(ARM64, 0.5 vCPU, 1GB)로 실행했고 2026년 11월 15일에 지금의 EKS 파드로 옮겼습니다. 클러스터 밖의 태스크는 ClusterIP Service에 닿지 못해 깨우기 API 앞에 전용 내부 NLB를 두고 그 NLB가 있는 서브넷 대역을 NetworkPolicy로 허용했습니다. 옮기기 전과 후에 확인한 차이는 표 14와 같습니다.

| 항목 | ECS Fargate (2026년 11월 14일) | EKS 파드 (2026년 11월 15일) |
|---|---|---|
| BFF에서 게이트웨이까지 | 게이트웨이의 내부 NLB | 클러스터 안의 Service |
| BFF에서 깨우기 API까지 | 전용 내부 NLB와 `TargetGroupBinding` | 클러스터 안의 Service. 전용 NLB는 삭제 |
| NetworkPolicy가 BFF의 호출을 허용하는 기준 | 전용 NLB를 둔 Isolated 서브넷의 IP 대역 | 네임스페이스 `app`의 BFF 파드 라벨 |
| 게이트웨이 구간의 중앙값 (Gemma 4 31B, Qwen3.8-27B) | 7.4ms, 8.1ms (NLB 포함) | 9.7ms, 8.4ms |
| 사용자가 본 첫 내용의 중앙값 (같은 순서) | 77.7ms, 179.6ms | 81.9ms, 177.5ms |
| 앱 계층의 시간당 고정 비용 | 0.0904 USD (ALB 0.0225, 깨우기 NLB 0.0225, Fargate 태스크 2개 0.0454) | 0.1857 USD (ALB 0.0225, c7g.large 2대 0.1632) |

*표 14. BFF를 옮기기 전과 후의 차이. 구간별 값은 두 날 모두 서울 리전의 EC2에서 요청을 하나씩, 모델마다 20건 보낸 측정의 중앙값이고 금액은 세전 USD입니다.*

경로에서 NLB가 빠졌는데도 게이트웨이 구간은 줄지 않았습니다. 두 측정 모두 20건의 중앙값을 한 번씩 잰 것이어서 이 차이가 구성 변경 때문인지 측정 사이의 편차인지는 가를 수 없습니다. vLLM 구간은 Gemma 4 31B가 두 날 모두 63.2ms, Qwen3.8-27B가 148.1ms와 147.6ms로 거의 같습니다. 고정 비용은 Fargate 태스크와 깨우기 NLB가 빠지고 c7g.large 2대가 더해져 시간당 0.0953 USD 늘었고 환경 전체로는 약 9.95 USD에서 약 10.05 USD가 됐습니다.

## 11. 마치며

세 편에 걸쳐 Amazon EKS에서 vLLM으로 두 모델을 서빙하는 구성을 콜드 스타트, 처리량, 요청 경로의 순서로 측정했습니다.

1부에서는 콜드 스타트를 네 구간으로 나눠 구간마다 다른 방법으로 줄였습니다. Gemma 4 31B의 콜드 스타트는 394초에서 260초로, 웜 재시작은 214초에서 86초로 줄었습니다. 2부에서는 L40S 한 장의 한계를 확인했습니다. Gemma 4 31B는 ITL p99가 동시성 1에서도 57.7ms여서 50ms 기준을 부하와 무관하게 만족하지 못했습니다. Qwen3.8-27B는 MTP를 켜면 동시에 3건, 끄면 20건을 실행했습니다. MTP를 끄면 최대 처리량이 초당 91.2토큰에서 281.8토큰으로 늘어나는 대신 요청 하나의 속도가 초당 32.5토큰에서 19.2토큰으로 줄었습니다.

3부의 질문은 모델 선택을 누가 맡고 그 경로가 시간을 얼마나 더하는지였습니다. BFF가 규칙과 Strands Decider 2B로 모델을 정하고 게이트웨이가 본문의 `model` 값으로 풀을 골랐습니다. 사용자에서 게이트웨이까지의 경로가 더한 시간은 중앙값으로 Gemma 4 31B 18.2ms, Qwen3.8-27B 29.7ms였고 나머지 63.2ms와 147.6ms는 vLLM이 사용했습니다. 배치 부하에서 상담 요청을 지킨 것도 엔진의 priority 스케줄링이었습니다(TTFT 중앙값 30.9초에서 0.19초). 게이트웨이의 InferenceObjective는 배치 요청을 거절해 엔진의 대기열을 줄이는 역할을 했습니다.

이 값들은 2026년 11월 14일과 15일에 서울 리전의 한 환경에서 잰 것이고 대부분 한 번씩 잰 값이라 반복했을 때의 편차는 확인하지 않았습니다. BFF를 EKS 파드로 옮긴 뒤 다시 확인하지 않은 값에는 본문에 그 조건을 적었습니다. EPP와 게이트웨이 파드의 장애 동작, Qwen3.8-27B의 우선순위 효과, 일정에 따른 sleep의 자동 실행도 확인하지 못한 항목으로 남아 있습니다. 이 글의 구성과 측정값이 여러분의 Amazon EKS 기반 LLM 서빙 경로 설계에 실질적인 참고가 되기를 바랍니다.

## 참고 자료

- [Introduction – Gateway API Inference Extension 문서](https://gateway-api-inference-extension.sigs.k8s.io/)
- [InferencePool – Gateway API Inference Extension API 문서](https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/)
- [Release v1.6.0 – Gateway API Inference Extension 릴리스 노트](https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/tag/v1.6.0)
- [Flow Control – llm-d v1.0.0 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md)
- [Multiple inference pools – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)
- [Inference routing – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/inference-routing/)
- [Sleep Mode – vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)
- [vllm.config.scheduler – vLLM API 문서](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)
- [strands-decider – GitHub 저장소](https://github.com/strands-labs/strands-decider)
- [Restrict access with VPC origins – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Origin settings – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html)
- [Quotas – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/cloudfront-limits.html)
- [Understand response headers policies – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/understanding-response-headers-policies.html)
- [Rate-based rule caveats in AWS WAF – AWS WAF Developer Guide](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)
- [Verifying JSON web tokens – Amazon Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-tokens-verifying-a-jwt.html)
- [Authentication flows – Amazon Cognito Developer Guide](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html)
- [Application Load Balancers – Elastic Load Balancing User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html)
- [Edit target group attributes for your Application Load Balancer – Elastic Load Balancing User Guide](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-target-group-attributes.html)
- [Ingress annotations – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/)
- [Security Groups for Load Balancers – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/security_groups/)
- [Subnet Auto-Discovery – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/subnet_discovery/)
- [TargetGroupBinding – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/targetgroupbinding/targetgroupbinding/)
- [NodePools – Karpenter 문서](https://karpenter.sh/docs/concepts/nodepools/)
- [Learn how EKS Pod Identity grants pods access to AWS services – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Restrict Pod network traffic with Kubernetes network policies – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html)
- [Search the web using Amazon Bedrock AgentCore Web Search – Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)
- [Introducing the Web Search API on Amazon Bedrock AgentCore – AWS Machine Learning Blog (2026년 11월 11일)](https://aws.amazon.com/ko/blogs/machine-learning/introducing-the-web-search-api-on-amazon-bedrock-agentcore/)
- [Amazon Bedrock AgentCore 요금 – 요금 페이지](https://aws.amazon.com/ko/bedrock/agentcore/pricing/)

*본문의 측정값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)의 한 환경에서 잰 값이며, 반복 횟수는 표마다 적었습니다. BFF가 ECS Fargate였던 11월 14일에 확인한 값은 해당 표와 문장에 표시했습니다. 금액은 2026년 11월 14일과 15일에 확인한 공개 단가를 바탕으로 한 시간당 세전 USD 추정치이고, 최종 금액은 사용량과 요금 변경에 따라 달라질 수 있습니다.*

## 저자 소개

**최우형 (Woohyung Choi)** 님은 AWS Korea의 Principal Solutions Architect로, 국내 주요 엔터프라이즈 및 디지털 기업의 클라우드 전환과 아키텍처 현대화를 지원하고 있습니다. 특히 클라우드 네이티브 아키텍처와 Agentic AI 분야에 전문성을 가지고 있으며, 고객이 Amazon Bedrock을 비롯한 AWS의 생성형 AI 및 Agentic AI 기술을 안정적이고 비용 효율적으로 도입하고 확장할 수 있도록 아키텍처 설계와 기술 자문을 제공하고 있습니다.

컨테이너, 네트워킹, 비용 최적화를 비롯한 클라우드 핵심 기술부터 Agentic AI를 활용한 업무 혁신과 지능형 시스템 구축까지 폭넓은 영역에서 AWS 아키텍처 모범 사례를 제시하고 있습니다. 이를 통해 고객의 복잡한 기술적 과제를 해결하고, AI와 클라우드를 기반으로 지속 가능한 기술 전략을 수립하고 실행할 수 있도록 기술 리더십을 발휘하고 있습니다.
