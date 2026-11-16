# Claude Code 단계별 프롬프트

`AGENT.md`를 저장소 루트에 둔 상태에서 아래 프롬프트를 순서대로 입력합니다. 단계마다 결과를 확인하고 다음 단계로 넘어갑니다. 단계가 바뀔 때 대화를 새로 시작해도 `AGENT.md`가 맥락을 유지합니다.

---

## 0단계. 사전 확인

```
AGENT.md를 읽고 0단계 사전 확인만 진행해 주세요. 리소스는 만들지 않습니다.

1. 아래 버전의 최신 호환 정보를 공식 문서와 릴리스 노트로 확인하고 docs/00-versions.md에 정리해 주세요.
   - EKS, Karpenter, 애드온의 최신 버전과 AWS Load Balancer Controller 호환 버전
   - GAIE CRD 최신 안정 버전과 InferencePool, InferenceObjective의 API 그룹과 필드 이름
   - agentgateway의 GAIE 지원 버전과 body 기반 model 라우팅 설정 방법
   - vLLM v0.33.0의 Gemma4, Qwen3_5 아키텍처 지원 여부, runai_streamer, sleep mode, MTP, priority 스케줄링 플래그
2. 체크포인트 3개(Gemma FP8-dynamic, Qwen FP8 per-channel, Decider 2B)의 Hugging Face 저장소, 크기, 라이선스, 양자화 방식을 확인해 주세요. Qwen은 공식 block FP8과 per-channel FP8-dynamic 중 L40S에서 쓸 수 있는 쪽을 근거와 함께 정리해 주세요.
3. ap-northeast-2의 G 계열 On-Demand, Spot vCPU 서비스 할당량을 aws service-quotas로 조회하고, g6e.4xlarge 2대와 g6.xlarge 1대에 필요한 vCPU와 비교해 주세요.
4. 확인하지 못한 항목은 따로 목록으로 보고해 주세요.
```

## 1단계. 네트워크와 EKS 기반

```
1단계를 진행해 주세요. infra/terraform에 아래를 작성하고 terraform plan 결과만 보여 주세요. apply는 제가 승인한 뒤에 합니다.

- VPC는 새로 만든 eks-vpc(CDK 스택 EksVpcStack, infra/cdk-vpc)를 씁니다. Terraform에서는 VPC, 서브넷, 엔드포인트를 만들지 않고 조회해서 씁니다. S3 Gateway Endpoint와 ECR, STS, EKS 인터페이스 엔드포인트는 이 VPC에 이미 있고, 워크로드는 Private 서브넷에 둡니다.
- EKS 클러스터, Karpenter, AWS Load Balancer Controller를 설치합니다. EKS, Karpenter, 애드온은 배포 시점의 최신 버전(docs/00-versions.md 기준 EKS 1.37, Karpenter 1.15)을 쓰고, 주요 애드온(vpc-cni, coredns, kube-proxy, eks-pod-identity-agent)은 클러스터를 배포할 때 함께 설치합니다.
- S3 버킷 1개(models, vllm-cache prefix)와, 서빙 파드용 읽기 전용 역할, 적재와 캐시 게시 Job용 쓰기 역할을 Pod Identity로 연결합니다.

k8s/base에는 아래를 작성해 주세요.
- NodePool 4개: gemma-od(g6e.4xlarge, on-demand), qwen-od(g6e.4xlarge, on-demand), decider(g6.xlarge), system(CPU 인스턴스, AZ 분산)
- GPU NodePool에는 taint를 두고, 각 NodePool에 GPU 개수 limits를 걸어 의도하지 않은 노드 증가를 막습니다.
- EC2NodeClass: NVIDIA 드라이버가 포함된 AMI, userData로 vllm/vllm-openai:v0.33.0 이미지 사전 pull, 로컬 NVMe를 instance store 정책으로 사용
- consolidateAfter는 변수로 두고 기본값과 그 이유를 주석으로 남깁니다.

완료 기준: terraform validate 통과, kubectl apply --dry-run=server 통과(클러스터 생성 후), plan 요약 보고
```

## 2단계. 모델 적재

```
2단계를 진행해 주세요. jobs/model-sync에 Hugging Face에서 S3로 체크포인트 3개를 적재하는 Kubernetes Job을 만들어 주세요.

- s5cmd로 병렬 업로드하고, AGENT.md의 S3 구조를 따릅니다.
- Job은 system NodePool에서 실행하고, 적재 역할(Pod Identity)만 씁니다.
- 업로드 후 객체 수와 총 크기를 로그로 남기고 results/에 저장하는 방법도 함께 적어 주세요.

완료 기준: Job 매니페스트 dry-run 통과, 실행 명령과 예상 소요 시간 근거 보고. 실행은 제가 승인한 뒤에 합니다.
```

## 3단계. vLLM 배포

```
3단계를 진행해 주세요. k8s/gemma와 k8s/qwen에 vLLM Deployment와 Service를 작성해 주세요.

- 플래그는 AGENT.md의 시작 설정을 쓰되, v0.33.0 이미지 안에서 vllm serve --help로 플래그 이름을 확인해 주세요.
- 가중치는 runai_streamer로 S3에서 직접 읽습니다.
- initContainer가 S3의 compile 캐시 prefix를 hostPath로 내려받고, 캐시가 없으면 건너뜁니다.
- Qwen은 VLLM_SERVER_DEV_MODE=1과 /is_sleeping 기반 readiness exec probe를 둡니다.
- 두 Deployment 모두 Recreate 전략, 해당 NodePool의 taint 허용과 nodeSelector를 둡니다.
- jobs/cache-publish에 첫 기동 후 hostPath의 compile 캐시를 S3 prefix로 게시하는 Job을 만들어 주세요.

완료 기준: kubectl diff 결과 보고. 배포 후 각 파드의 vLLM 로그에서 가중치 로드 시간, 엔진 초기화 시간, KV 캐시 크기를 뽑아 docs/03-vllm.md에 기록합니다. Gemma가 gpu-memory-utilization 0.90으로 시작하지 못하면 0.85로 낮추고 그 사실을 기록해 주세요.
```

## 4단계. GAIE와 게이트웨이

```
4단계를 진행해 주세요. k8s/gateway와 각 모델 디렉터리에 GAIE 리소스를 작성해 주세요.

- 0단계에서 확인한 버전의 Gateway API CRD, GAIE CRD, llm-d-router(EPP와 InferenceObjective CRD), agentgateway를 설치합니다.
- Gateway를 만들고, 게이트웨이 Service는 AWS Load Balancer Controller 어노테이션으로 내부 NLB(IP 대상, 단일 리스너)에 연결합니다.
- 요청 본문의 model 필드를 헤더로 바꾸는 body 기반 라우팅을 설정합니다.
- 모델별 InferencePool과 EPP, HTTPRoute를 만듭니다. HTTPRoute에는 /v1/chat/completions와 /v1/models만 등록해 /sleep, /wake_up 같은 경로가 게이트웨이로 노출되지 않게 합니다.
- InferenceObjective를 풀마다 2개(interactive, batch) 만들고, batch 우선순위는 0보다 낮게 둡니다.
- 게이트웨이와 EPP는 system NodePool에서 AZ를 나눠 2개 이상 실행합니다.

완료 기준: 클러스터 안에서 curl로 model 값만 바꿔 두 모델이 각각 응답하는지, /sleep 경로가 게이트웨이에서 막히는지 확인하고 결과를 docs/04-gateway.md에 기록합니다.
```

## 5단계. Strands Decider 2B

```
5단계를 진행해 주세요. k8s/decider에 Strands Decider 2B 서빙을 작성해 주세요.

- Strands Labs 저장소의 공식 서빙 방법을 확인해서 그대로 씁니다. 저장소에 없는 서빙 방식은 만들지 말고 먼저 알려 주세요.
- decider NodePool(g6.xlarge)에 올리고, 가중치는 S3에서 읽습니다.
- 파드 시작 후 예열 요청을 한 번 보낸 뒤 Ready가 되게 합니다.
- 게이트웨이에 /decide HTTPRoute로 연결합니다. InferencePool로 묶지 않습니다.
- bench/decider에 선택지 2개(gemma, qwen), 정책 판단, thinking 판단 3종의 판단 1회 지연(중앙값, p95)을 측정하는 스크립트를 만들어 주세요.

완료 기준: 예열 전후 지연과 판단별 지연을 results/에 저장하고 docs/05-decider.md에 요약합니다.
```

## 6단계. sleep 컨트롤러

```
6단계를 진행해 주세요. k8s/sleep-controller에 Qwen sleep 운영 구성을 작성해 주세요.

- 업무 시간 외 Qwen을 level 1 sleep으로 보내고 업무 시작 전에 깨우는 CronJob 2개(시간대 Asia/Seoul)
- BFF만 호출할 수 있는 작은 깨우기 API: Qwen 파드의 /is_sleeping을 확인하고 잠들어 있으면 /wake_up을 호출합니다. ClusterIP Service로만 노출하고 HTTPRoute에 등록하지 않습니다.
- NetworkPolicy 또는 보안 그룹으로 깨우기 API와 Qwen 파드 8000 포트 접근을 제한합니다.

완료 기준: sleep 진입 시간, 복귀 시간, 복귀 후 readiness 전환까지 걸린 시간을 측정해 results/에 저장합니다.
```

## 7단계. 앱 계층

```
7단계를 진행해 주세요. app/bff와 infra/terraform에 앱 계층을 작성해 주세요.

BFF (ECS Fargate)
- OpenAI 호환 /v1/chat/completions를 받아 업무 종류, 첨부 여부, 데이터 정책 규칙, Decider 판단으로 model 값을 정합니다. 결정은 세션 단위로 캐시합니다.
- 결정적 민감 정보 규칙(주민등록번호, 카드번호 형식)을 Decider보다 먼저 적용합니다.
- Decider 응답 실패나 낮은 신뢰도는 Gemma, thinking off, 민감 정보 있음으로 처리합니다.
- 상담 요청에는 x-llm-d-inference-objective 헤더와 본문 priority를 함께 설정합니다.
- Qwen으로 보낼 요청은 깨우기 API를 먼저 호출합니다.
- SSE를 버퍼링 없이 그대로 전달합니다.
- 주문 조회는 고정 데이터를 돌려주는 목 API로 함수 호출 흐름만 보여 줍니다.

인프라
- 내부 ALB(private subnet), ECS Fargate 서비스, CloudFront 배포(VPC origins로 내부 ALB, 정적 페이지는 S3), WAF 요청 빈도 제한
- 보안 그룹: NLB는 BFF와 배치 작업에서만, ALB는 CloudFront VPC origin에서만 접근 허용
- CloudFront 오리진 응답 타임아웃과 ALB idle timeout은 스트리밍 기준으로 설정하고 값의 근거를 주석으로 남깁니다.

완료 기준: terraform plan 보고. 배포 후 CloudFront 주소로 상담 요청을 보내 스트리밍이 토큰 단위로 도착하는지 확인합니다.
```

## 8단계. 관측과 측정

```
8단계를 진행해 주세요. 관측 구성과 측정 스크립트를 작성해 주세요.

관측
- vLLM, EPP, 게이트웨이 메트릭을 Amazon Managed Service for Prometheus로 수집하고 Grafana 대시보드 JSON을 만듭니다.
- 모델별로 TTFT, ITL, 대기 요청 수, KV 캐시 사용률, MTP 수락률을 나눠 봅니다.

측정 스크립트 (bench/)
1. 콜드 스타트 4구간 분해: 파드 생성부터 Ready까지를 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화, 기타로 나눔. 시나리오는 콜드 기준, 콜드 최적화, 웜 재시작 기준, 웜 재시작 최적화, sleep 복귀
2. 구간별 TTFT: 사용자, CloudFront, ALB, BFF, 게이트웨이, vLLM 구간의 지연을 요청 ID로 연결해 분해
3. SLO 하 처리량: TTFT p99 500ms와 ITL p99 50ms를 동시에 만족하는 최대 동시성을 모델별로 탐색
4. 우선순위 효과: 배치 부하를 걸면서 상담 요청 TTFT를 측정. 게이트웨이 우선순위만, 엔진 우선순위만, 둘 다 켠 경우를 비교

완료 기준: 각 스크립트를 1회 실행해 results/에 원시 데이터를 저장하고, docs/08-results.md에 g7e.2xlarge 수치와 나란히 표로 정리합니다. 측정하지 않은 칸은 비워 둡니다.
```

## 9단계. 정리

```
9단계를 진행해 주세요. 전체 리소스를 역순으로 삭제하는 스크립트와 비용 확인 절차를 작성해 주세요.

- GPU 노드가 먼저 사라지도록 Deployment와 NodePool을 삭제한 뒤 terraform destroy를 실행합니다.
- S3의 models와 vllm-cache prefix는 기본적으로 남기고, 삭제는 별도 플래그로만 수행합니다.
- 삭제 후 남은 EC2, NLB, ALB, CloudFront 리소스를 조회하는 확인 명령을 포함합니다.

실행은 제가 승인한 뒤에 합니다.
```
