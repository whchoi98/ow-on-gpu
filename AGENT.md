# EKS vLLM 멀티 모델 서빙 (g6e.4xlarge, GAIE)

## 목적

블로그 시리즈 "EKS 기반 vLLM 서빙 최적화"의 3부 실측 환경입니다. 1부(콜드 스타트)와 2부(처리량과 SLO)는 g7e.2xlarge와 Gemma 4 31B NVFP4로 측정했습니다. 이 저장소는 같은 방법론을 g6e.4xlarge 2대에서 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙하는 구성으로 재현하고, 결과를 1부와 2부 수치와 비교할 수 있게 만드는 것이 목표입니다.

## 아키텍처

```
사용자                   Cognito 사용자 풀에 로그인해 액세스 토큰을 받음
  │ HTTPS, SSE
CloudFront + AWS WAF     기본 경로는 S3 정적 페이지(OAC), /v1/*만 아래로 보냄
  │ VPC origins
내부 ALB (private subnet) AWS Load Balancer Controller가 Ingress(app/bff)에서 만듦
  │
EKS: BFF 파드 2개        Graviton NodePool app(Karpenter). 토큰 검증, 정책 판단, Decider 호출, model 값과 우선순위 지정
  │                      Qwen 요청은 깨우기 API의 Service를 먼저 호출
  │                      게이트웨이는 Service로 직접 호출
  │                      (배치 작업은 BFF를 거치지 않고 내부 NLB로 게이트웨이를 직접 호출)
EKS: Inference gateway (agentgateway, GAIE)
  ├─ HTTPRoute model=gemma-4-31b ─ Gemma InferencePool ─ EPP ─ vLLM (g6e.4xlarge On-Demand)
  ├─ HTTPRoute model=qwen38-27b  ─ Qwen InferencePool  ─ EPP ─ vLLM (g6e.4xlarge On-Demand)
  └─ HTTPRoute /decide           ─ Strands Decider 12B Service  (g6e.xlarge)

Amazon S3 (S3 Gateway Endpoint 경유): 모델 가중치, compile 캐시. 서빙 파드는 S3에서만 읽음
```

## 확정된 결정

| 항목 | 값 |
|---|---|
| 리전 | ap-northeast-2 |
| VPC | 이 프로젝트용으로 새로 만든 eks-vpc(10.200.0.0/16)에 배포. CDK 스택 EksVpcStack(`infra/cdk-vpc`)이 4개 AZ의 Public, Private, Isolated 서브넷, AZ별 NAT 게이트웨이, S3와 DynamoDB 게이트웨이 엔드포인트, 인터페이스 엔드포인트 11종을 관리. 워크로드는 Private 서브넷에 둠 |
| EKS | 1.37, EKS Pod Identity. 클러스터 이름은 `ow-on-gpu` |
| 애드온용 노드 | 관리형 노드 그룹 `addons`: m7g.large(Graviton) 2대, `CriticalAddonsOnly` taint. Karpenter, CoreDNS, LBC 전용 |
| 네임스페이스 | `inference`(vLLM, Decider), `model-jobs`(적재와 캐시 게시 Job). Pod Identity가 연결된 ServiceAccount는 `inference`의 gemma, qwen, decider와 `model-jobs`의 model-sync, cache-publish |
| 노드 관리 | Karpenter 1.15 |
| 버전 방침 | 모든 구성 요소는 배포 시점의 최신 버전을 쓰되 서로의 지원 범위 안에서 맞춤. 2026-11-14 기준 조합은 `docs/00-versions.md`의 "버전 조합" 표 |
| EKS 애드온 | 주요 애드온(vpc-cni, coredns, kube-proxy, eks-pod-identity-agent)은 클러스터를 배포할 때 함께 설치. vpc-cni는 NetworkPolicy를 켬(`enableNetworkPolicy`) |
| Qwen sleep 일정 | 평일 19:00에 재우고 08:30에 깨움(Asia/Seoul). CronJob `qwen-sleep`, `qwen-wake`. 그 시간대에 측정할 때는 `qwen-sleep`을 suspend |
| GPU 노드 | g6e.4xlarge 2대 (L40S 1장, 가용 VRAM 44.7GiB, 시스템 메모리 128GiB, 네트워크 20Gbps 지속) |
| Gemma 노드 | On-Demand, 고객 경로 전용 |
| Qwen 노드 | On-Demand, 내부 업무 전용 (처음 계획은 Spot. 2026-11-14 변경) |
| Decider 노드 | g6e.xlarge 1대(L40S 1장, 시스템 메모리 32GiB), On-Demand (처음에는 g6.xlarge. 2026-11-24에 Decider v2 12B에 맞춰 변경) |
| GPU 노드 AZ | 제한 없음. GPU NodePool에는 zone 요구 조건을 두지 않고 Karpenter가 용량이 있는 AZ를 고르게 함 |
| 시스템 노드 | 게이트웨이와 EPP용 CPU 노드, AZ를 나눠 2대 이상 |
| vLLM 이미지 | vllm/vllm-openai:v0.33.0 (처음 계획은 v0.26.0. 1부, 2부와 엔진 버전이 다르면 비교표에 버전을 함께 적음) |
| 게이트웨이 | Gateway API CRD v1.6.3, GAIE v1.6.2(InferencePool CRD), llm-d-router v1.0.0(EPP와 InferenceObjective), agentgateway v1.7.0. GAIE v1.6부터 EPP와 InferenceObjective는 llm-d-router가 제공 |
| 앱 계층 | BFF는 EKS 파드(네임스페이스 `app`, Graviton NodePool `app`, EKS Pod Identity). 내부 ALB는 AWS Load Balancer Controller가 Ingress에서 만듦. CloudFront VPC origins, WAF. 2026-11-15에 ECS Fargate에서 옮겼고, 이전 Fargate 서비스와 Terraform이 만든 ALB, 깨우기 API용 NLB는 같은 날 지움(`docs/07-bff.md`의 "ECS Fargate에서 EKS 파드로"). 배포는 `k8s/bff/install.sh apply` |
| 관측 | Prometheus v3.16.0(agent 모드)이 vLLM, EPP, 게이트웨이 지표를 Amazon Managed Service for Prometheus로 보냄. 대시보드는 `k8s/observability/dashboards/serving.json` |
| 측정 | 방법과 결과는 `docs/08-results.md`. 부하 발생기는 측정 전용 NodePool `bench`에서 Job으로 실행(`bench/job.py`). 콜드 스타트의 기준 구성은 1부와 같은 Mountpoint FUSE(`bench/coldstart/k8s`) |
| 로그인 | Cognito 사용자 풀(가입 차단). `/v1/*`는 액세스 토큰이 있어야 BFF를 통과. 사용자는 `app/bff/create-user.sh`로 만들고 비밀번호는 코드와 Terraform state에 두지 않음 (2026-11-14 결정) |
| 정밀도 | FP8. L40S(Ada, SM 8.9)는 NVFP4를 쓸 수 없음 |
| Gemma 체크포인트 | RedHatAI/gemma-4-31B-it-FP8-dynamic |
| Qwen 체크포인트 | per-channel FP8-dynamic (예: AzatAI/Qwen3.8-27B-FP8-dynamic). 공식 block FP8은 Ada에서 커널 제약이 있어 0단계에서 비교 확인 |
| Decider 체크포인트 | strands-decider-12B-gemma4-v2-2611. v2에서 48GB GPU 한 장에 맞는 크기 (2026-11-24에 v1의 strands-decider-2B-qwen3.5-v1-2610에서 변경, `docs/05-decider.md`, ADR-002) |
| Decider 이미지 | ECR `ow-on-gpu/decider:0.4.0`. strands-decider 저장소 v0.4.0의 `deploy/sagemaker/Dockerfile`로 빌드(`k8s/decider/install.sh build`). v2 체크포인트는 strands-decider 0.4.0 이상이 필요한데 공개 서빙 이미지는 2026-11-20 빌드까지 0.3.1.dev1이어서 직접 빌드함 |

## 업무와 모델 배정

| 업무 | 모델 | 우선순위 |
|---|---|---|
| 상담 챗봇 (함수 호출로 주문 조회) | Gemma | interactive |
| 상품 설명 다국어 번역, 리뷰 요약 | Gemma | batch |
| 상품 이미지 속성 추출, 문서 OCR | Qwen | interactive 또는 batch |
| 사내 코딩 에이전트 | Qwen | interactive |

데이터 정책: 개인정보가 들어간 요청은 Gemma로만 보냅니다. 형식이 정해진 민감 정보(주민등록번호, 카드번호 등)는 BFF의 결정적 규칙으로 먼저 거르고, Decider는 형식이 없는 경우의 보조 판단에만 씁니다. Decider 응답이 없거나 신뢰도가 기준보다 낮으면 Gemma, thinking off, 민감 정보 있음으로 처리합니다. 다만 모델 선택의 신뢰도만 낮고 개인정보가 없다는 판단이 기준 이상이면 Gemma, thinking off로 보내되 민감 정보 요청으로 다루지 않습니다(2026-11-17 변경. 업무 종류 없이 보낸 일반 질문에 웹 검색이 붙지 않던 문제 때문, `docs/10-web-search.md`). Decider 판단은 메시지마다가 아니라 세션 시작 시 한 번 내리고 재사용합니다.

## vLLM 시작 설정

아래는 시작값입니다. 플래그 이름과 지원 여부는 실제 이미지 안에서 `vllm serve --help`로 확인한 뒤 씁니다.

Gemma 4 31B

```
--load-format runai_streamer
--language-model-only
--max-model-len 16384
--kv-cache-dtype fp8
--gpu-memory-utilization 0.90        # sleep mode를 쓰지 않으므로 0.85보다 높게 시험
--enable-prefix-caching
--scheduling-policy priority
--enable-auto-tool-choice
--tool-call-parser gemma4
--reasoning-parser gemma4
# sleep mode 끔, speculative decoding 끔
```

Qwen3.8-27B

```
--load-format runai_streamer
--max-model-len 32768
--max-num-seqs 32                    # 기본 1024는 Mamba 캐시 블록 부족으로 엔진 시작 실패
--kv-cache-dtype fp8
--gpu-memory-utilization 0.90        # L40S에서 0.85는 KV 캐시가 0.24GiB만 남아 시작 실패(docs/03-vllm.md). g7e에서는 sleep mode와 0.90 조합이 시작 실패였음
--enable-sleep-mode                  # VLLM_SERVER_DEV_MODE=1 필요
--enable-prefix-caching
--scheduling-policy priority
--speculative-config '{"method":"mtp","num_speculative_tokens":3}'
--reasoning-parser qwen3
--enable-auto-tool-choice
--tool-call-parser qwen3_coder
```

공통

- 환경 변수 `VLLM_CACHE_ROOT=/vllm-cache`, hostPath `/var/cache/vllm`을 `/vllm-cache`에 마운트
- initContainer가 S3의 compile 캐시를 hostPath로 미리 내려받음
- Deployment 전략은 Recreate (GPU 1장에 파드 1개)
- Qwen readinessProbe는 `/is_sleeping`을 확인하는 exec probe. `/health`는 sleep 중에도 200을 반환하므로 쓰지 않음

## S3 구조

```
s3://<bucket>/models/gemma-4-31B-it-FP8-dynamic/
s3://<bucket>/models/Qwen3.8-27B-FP8-dynamic/
s3://<bucket>/models/strands-decider-12B-gemma4-v2-2611/   # Decider v2. 가중치를 모두 담고 있어 기반 모델이 따로 없음
s3://<bucket>/models/strands-decider-2B-qwen3.5-v1-2610/   # 2026-11-24까지 쓴 Decider v1. 쓰지 않지만 남아 있음
s3://<bucket>/models/Qwen3.5-2B-Base/                      # Decider v1의 기반 모델. 쓰지 않지만 남아 있음
s3://<bucket>/vllm-cache/v0.33.0-gemma4-31b-fp8-l40s/
s3://<bucket>/vllm-cache/v0.33.0-qwen38-27b-fp8-l40s/
```

compile 캐시 prefix에는 vLLM 버전, 모델, 정밀도, GPU 아키텍처를 넣습니다. 구성이 하나라도 바뀌면 새 prefix로 게시합니다.

## 측정 기준

- SLO: TTFT p99 500ms, ITL p99 50ms 동시 만족
- 콜드 스타트는 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화 4구간과 기타로 분해
- 비교 대상: g7e.2xlarge 실측(콜드 기준 428초, 최적화 226초, 웜 재시작 314초와 133초, sleep 복귀 0.97초, 가중치 로드 127.6초에서 19.8초)
- 원시 로그와 측정 스크립트 출력은 `results/<날짜>-<항목>/`에 그대로 저장

## 작업 규칙

- AWS 리소스를 만들거나 바꾸거나 지우기 전에 `terraform plan` 또는 `kubectl diff` 결과를 먼저 보여 주고 승인을 받은 뒤 실행합니다. GPU 노드가 뜨는 작업은 실행 전에 그 사실을 따로 알립니다.
- CRD 필드, Helm values, vLLM 플래그는 기억에 의존하지 않고 실제 설치 버전에서 확인합니다(`kubectl explain`, `helm show values`, 이미지 안의 `vllm serve --help`). 확인하지 못한 값은 `TODO(verify)` 주석으로 남기고 보고합니다.
- 측정값을 추정하거나 만들어 내지 않습니다. 측정하지 않은 수치는 문서에 쓰지 않습니다.
- 자격 증명은 코드와 매니페스트에 넣지 않습니다. AWS 권한은 EKS Pod Identity와 IAM 역할로만 부여합니다.
- 계정 ID, ARN, CloudFront 주소, 로드 밸런서 주소, 사용자 풀 ID, 버킷 이름의 접미사, 리소스 ID, 공인 IP 같은 환경 식별 값은 저장소에 올리지 않습니다. 결과 파일은 커밋하기 전에 `scripts/mask-identifiers.py`로 가리고, 환경별 값이 든 파일은 자리 표시만 든 `*.example`만 추적합니다. 화면을 찍은 그림에는 로그인한 계정이 보이지 않게 합니다. (2026-11-16 결정)
- 서빙 파드가 Hugging Face에서 직접 내려받지 않게 합니다. 가중치는 적재 Job이 S3에 한 번 올리고, 서빙 파드는 S3에서만 읽습니다.
- 요청 범위 밖의 기능, 불필요한 추상화, 중복 코드를 넣지 않습니다. 주석은 코드만으로 알기 어려운 이유와 제약만 씁니다.
- README와 docs는 한국어 합니다체로 씁니다.
- 각 단계가 끝나면 만든 파일, 실행한 명령, 확인 결과, 남은 TODO를 짧게 보고하고 다음 단계로 넘어가기 전에 멈춥니다.

## 디렉터리 구조

```
infra/cdk-vpc/          eks-vpc (VPC, 서브넷, NAT 게이트웨이, VPC 엔드포인트) CDK 스택
infra/terraform/        EKS, Karpenter, IAM, S3, 보안 그룹, CloudFront, WAF, Cognito. VPC는 만들지 않고 eks-vpc를 조회해서 씀
k8s/base/               네임스페이스, NodePool, EC2NodeClass, NVIDIA device plugin
k8s/gemma/              Deployment, Service, InferencePool, EPP, HTTPRoute, InferenceObjective
k8s/qwen/               위와 동일
k8s/decider/            Deployment, Service, HTTPRoute. install.sh로 이미지를 빌드하고 적용
k8s/gateway/            Gateway API CRD, GAIE CRD, llm-d-router CRD, agentgateway, Gateway, 게이트웨이 Service(내부 NLB)
k8s/sleep-controller/   업무 시간 sleep CronJob, 깨우기 API
k8s/bff/                BFF의 Graviton NodePool, Deployment, Service, Ingress(내부 ALB). install.sh로 적용
k8s/observability/      지표 수집기(Prometheus agent), Grafana 대시보드 JSON
k8s/bench/              측정 Job 전용 NodePool
jobs/model-sync/        Hugging Face에서 S3로 s5cmd 적재 Job
jobs/cache-publish/     hostPath compile 캐시를 S3에 게시하는 Job
app/bff/                BFF(EKS 파드로 실행, k8s/bff), 이미지 빌드와 사용자 생성 스크립트. 웹 검색 도구(websearch.py)는 AgentCore Web Search를 us-east-1로 부름(docs/10-web-search.md)
app/web/                확인용 페이지(React, Vite). 요청, 대화, 성능 평가, 경로 판단, 상태, API 호출, 구조, 구축 과정 보기. 한영 전환(src/i18n.js, docs/07-bff.md). 응답은 react-markdown v10과 remark-gfm으로 렌더링
bench/                  콜드 스타트(coldstart), sleep 복귀(sleep), 구간별 TTFT(ttft), SLO 하 처리량(slo), 우선순위 효과(priority) 측정 스크립트. job.py는 클러스터 안에서 돌리는 측정의 실행기
results/                측정 원시 데이터
docs/                   단계별 기록
docs/infographic/       요청 경로와 기동 흐름(08), LLM API 호출(09), 구축 단계와 아키텍처(10) 인포그래픽(aws-infographic 스킬의 infokit). 한국어판과 영어판(flow_en.py, apicall_en.py, build_steps_en.py). 웹 화면의 흐름 그림과 API 호출 보기의 값도 여기서 만듦
reference/              인포그래픽의 참조 그림(1부, 2부의 한눈에 보기와 콜드 스타트, LLM API 호출 여정)
blog/                   블로그 원고 3부작 "OpenWeight on AWS GPU"의 작업 폴더(편마다 drafts, diagrams, images, out). 1부 API 호출, 2부 구조와 Amazon EKS 최적화, 3부 구축 과정이다. aws-blog-skills 스킬로 만든다. 그림은 모두 인포그래픽 스타일이고, diagrams/infographic의 build.sh가 docs/infographic의 infokit으로 그린다. 그림 모듈에는 한국어와 영어 글이 함께 있고 build.sh는 한국어판을 만든다
source-doc/             블로그 원고의 첫 원본(md, images, zip) 사본
```

## 알려진 함정

- 공식 block FP8 체크포인트는 Ada에서 CUTLASS block-scaled FP8 GEMM(SM90 이상 필요)을 쓰지 못합니다.
- Gemma의 ModelOpt FP8 체크포인트는 lm_head와 embed_tokens 공유 문제로 vLLM 패치가 필요했던 보고가 있어 compressed-tensors FP8-dynamic을 씁니다.
- Gemma의 MTP는 별도 assistant 모델과 TRITON_ATTN 백엔드가 필요합니다. 이 구성에서는 쓰지 않습니다.
- Qwen의 MTP 헤드는 BF16이어야 하고, 양자화 ignore 목록에 `mtp.*`가 없으면 드래프트 수락이 0이 됩니다. 수락률 지표로 확인합니다.
- Qwen chat template은 thinking이 기본으로 켜져 있습니다. 요청별 `enable_thinking`으로 제어합니다.
- Qwen은 MTP의 추측 토큰 3개 때문에 요청마다 Mamba 상태 블록을 4배로 잡아, KV 캐시 2.45GiB(46블록)에서 동시에 3건만 실행합니다. prefix caching을 꺼도 같습니다. MTP를 끄면 20건까지 실행하고 S1 최대 처리량이 초당 91.2토큰에서 281.8토큰이 되지만 요청 하나는 초당 32.5토큰에서 19.2토큰으로 느려집니다(docs/08-results.md 3절).
- level 1 sleep은 가중치를 호스트 RAM에 보존합니다. g7e에서는 약 30GiB였고, L40S의 Qwen per-channel 체크포인트에서는 sleep을 한 번 거친 뒤 컨테이너 메모리가 60.4GiB였습니다(docs/03-vllm.md).
- Decider는 예열 중 첫 요청이 수 초 걸립니다. 예열 요청이 끝난 뒤 Ready가 되게 합니다.
- 공개 서빙 이미지에 든 strands-decider 버전은 태그로 알 수 없습니다. 2026-11-20 빌드(v1.0.2)까지 0.3.1.dev1이었고 v2 체크포인트(`decision_config.json`)를 읽는 모듈이 없었습니다. 이미지 설정의 레이블과 패키지 레이어로 확인합니다.
- `k8s/decider`는 `kubectl apply -k`로 직접 적용하지 않습니다. 이미지 주소의 자리(`${DECIDER_IMAGE}`)를 `k8s/decider/install.sh`가 채웁니다.
- 작업 장비가 arm64라 Decider 이미지(amd64)를 빌드하려면 amd64 에뮬레이션(binfmt)이 등록되어 있어야 합니다. 재부팅하면 등록이 사라집니다.
- CloudFront 오리진 응답 타임아웃 기본값은 30초, ALB idle timeout 기본값은 60초입니다. 배치는 CloudFront 경로로 보내지 않습니다.
- BFF가 SSE 응답을 모아서 내보내면 스트리밍이 깨집니다. 청크 단위로 그대로 흘려보냅니다.
- 게이트웨이와 EPP가 멈추면 두 모델 모두 응답하지 못합니다. CPU 노드와 복제본을 AZ별로 나눕니다.
- AWS Load Balancer Controller는 `aws-load-balancer-security-groups` 어노테이션의 이름을 보안 그룹 이름이 아닌 `Name` 태그에서 찾습니다.
- `vllm bench serve`는 GPU가 없는 노드에서 "Failed to infer device type"으로 시작하지 못합니다. 측정 파드는 `bench/slo/bench_serve.py`로 벤치마크 모듈을 직접 부릅니다.
- Qwen은 KV 캐시 2.45GiB에서 요청 하나가 28%를 고정으로 잡아 동시에 3건만 실행합니다(docs/08-results.md). 동시성을 올려도 처리량이 늘지 않고 대기만 길어집니다.
- L40S의 Gemma FP8-dynamic은 토큰 간격이 54ms여서 ITL p99 50ms 기준을 동시성 1에서도 넘습니다.
- 콜드 스타트 측정에서 GPU 노드 하나를 지우는 데 6분 30초쯤 걸립니다.
- AMP에 PromQL을 GET의 쿼리 문자열로 보내면 서명이 맞지 않아 403이 납니다. 본문(POST)으로 보냅니다.
- ALB 접근 로그 버킷의 정책에는 ELB 계정 주체만으로는 부족했고 `logdelivery.elasticloadbalancing.amazonaws.com` 서비스 주체가 필요했습니다.
- WAF 속도 제한을 넘기면 그 IP의 모든 요청이 한동안 403입니다. CloudFront 주소로 부하 측정을 할 때는 `waf_rate_limit`을 올리거나 측정 장비를 예외로 둡니다.
