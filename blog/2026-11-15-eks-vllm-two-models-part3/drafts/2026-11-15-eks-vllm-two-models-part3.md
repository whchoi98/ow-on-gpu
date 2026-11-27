---
title: "OpenWeight on AWS GPU 3부: 10개 단계로 따라 하는 구축 과정"
date: 2026-11-15
author: "Woohyung Choi"
status: draft
---

# OpenWeight on AWS GPU 3부: 10개 단계로 따라 하는 구축 과정

by WOO HYUNG CHOI on 15 11월 2026 in [Advanced (300)](https://aws.amazon.com/ko/blogs/tech/category/learning-levels/advanced-300/), [Amazon Elastic Kubernetes Service](https://aws.amazon.com/ko/blogs/tech/category/compute/amazon-kubernetes-service/), [Generative AI](https://aws.amazon.com/ko/blogs/tech/category/artificial-intelligence/generative-ai/)

이 글은 시리즈 "OpenWeight on AWS GPU(OW on GPU)"의 3부입니다. 이 시리즈는 오픈 웨이트 모델을 AWS의 GPU 인스턴스에서 직접 서빙하는 방법을 다룹니다. 오픈 웨이트 모델은 가중치가 공개되어 내려받아 직접 실행할 수 있는 모델입니다. 예제 환경은 Amazon Elastic Kubernetes Service(Amazon EKS)에서 오픈 소스 추론 엔진 vLLM으로 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙합니다. 1부(TODO: Part 1 링크)는 API 호출 한 건이 지나는 8개 단계를 따라갔습니다. 2부(TODO: Part 2 링크)는 두 모델을 서빙하는 구조와 Amazon EKS 최적화를 설명했습니다.

3부는 이 환경을 처음부터 만드는 순서입니다. VPC를 만드는 것에서 시작해 로그인한 브라우저에 두 모델의 답이 스트리밍될 때까지를 10개 단계(0단계에서 9단계)로 나눴습니다. 단계마다 만드는 것, 명령, 확인 방법, 측정한 값, 막히기 쉬운 곳을 같은 순서로 적었습니다. 코드와 매니페스트는 공개 저장소 [ow-on-gpu](https://github.com/whchoi98/ow-on-gpu)에 있으므로 저장소를 열어 두고 읽는 것을 권고합니다. 본문의 값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)에서 측정했고 측정 횟수는 표에 적었습니다. 5단계 Strands Decider 12B의 값은 2026년 11월 24일에 측정했습니다. 이 글은 Kubernetes와 AWS의 기본 개념(파드, Deployment, VPC, IAM)을 알고 LLM 서빙 환경을 처음 구축하는 엔지니어를 대상으로 합니다.

그림 1은 완성된 환경의 구성 요소마다 그것을 만드는 단계의 번호를 붙인 구조도입니다. 아래쪽 카드 10개가 이 글에서 따라갈 단계입니다.

![완성된 환경의 구조도에 구성 요소를 만든 단계의 번호를 붙인 그림. 요청 경로의 CloudFront, 내부 ALB, BFF, Cognito, S3 페이지는 7단계, 게이트웨이는 4단계, Decider 12B는 5단계, 깨우기 API는 6단계, GPU 노드의 Gemma 4 31B와 Qwen3.8-27B, compile 캐시는 3단계, S3 모델 버킷과 Pod Identity, Karpenter NodePool은 1단계, 모델 적재 Job은 2단계, AMP는 8단계에 만들고 아래쪽에 0단계에서 9단계의 이름과 도구를 카드로 정리했다.](images/2026-11-15-eks-vllm-two-models-part3-fig01-build-map.png)

*그림 1. 구축 단계와 아키텍처. 원 안의 번호는 그 구성 요소를 만든 단계이고 파란 글자는 사용한 도구입니다. 웹 검색은 8단계 뒤에 BFF의 도구로 더해 +로 표시했습니다.*

## 1. 완성된 환경과 준비물

### 1.1 완성된 환경

0단계에서 8단계까지 마치면 로그인 페이지에서 요청을 보내고 두 모델의 답을 토큰 단위로 받습니다. 요청은 Amazon CloudFront, 내부 Application Load Balancer(ALB), BFF(Backend for Frontend), 게이트웨이를 차례로 지납니다. 그 끝에 GPU 노드의 vLLM 파드가 있습니다. BFF는 로그인 토큰을 검증하고 요청을 어느 모델로 보낼지 정하는 앱입니다. 이 경로가 요청 한 건을 처리하는 과정은 1부에, 구성 요소를 이렇게 둔 이유는 2부에 있습니다.

모든 구성 요소가 실행 중일 때 클러스터의 노드는 9대입니다.

| 노드 그룹 또는 NodePool | 인스턴스 | 대수 | 실행하는 것 |
|---|---|---:|---|
| addons (관리형 노드 그룹) | m7g.large | 2 | Karpenter, CoreDNS, AWS Load Balancer Controller |
| system | c7i-flex.xlarge | 2 | 게이트웨이 계층, 지표 수집기 |
| app | c7g.large | 2 | BFF 파드 2개 |
| gemma-od, qwen-od | g6e.4xlarge (NVIDIA L40S 1장) | 2 | Gemma 4 31B, Qwen3.8-27B |
| decider | g6e.xlarge (NVIDIA L40S 1장) | 1 | Strands Decider 12B |

*표 1. 완성된 환경의 노드 9대(2026년 11월 26일 확인). addons를 뺀 노드는 Karpenter가 NodePool의 조건에 맞춰 만듭니다.*

### 1.2 준비물과 작업 규칙

시작하기 전에 계정의 할당량, 명령줄 도구, 비용을 확인합니다.

| 준비물 | 내용 |
|---|---|
| AWS 계정 | 서울 리전에서 g6e.4xlarge 2대와 g6e.xlarge 1대를 실행할 수 있는 G 계열 On-Demand 할당량(36 vCPU) |
| 명령줄 도구 | AWS CLI, kubectl, Helm, Terraform 1.14 이상, Docker, Node.js와 npm |
| 저장소의 훅과 시험이 사용하는 도구 | jq, python3, Bash 4 이상 |
| 작업 장비 | arm64와 amd64 이미지를 만들 수 있는 장비. BFF 이미지는 arm64, Decider 12B 이미지는 amd64입니다 |
| 비용 | 모든 구성 요소가 실행 중일 때 시간당 약 11.35 USD |

*표 2. 준비물. 비용은 고정 비용의 세전 USD 추정치입니다. 2026년 11월 15일의 추정값 약 10.05 USD에 11월 24일에 바꾼 Decider 노드의 가격 차이(시간당 1.2984 USD)를 더했고 사용량에 따라 부과되는 요금은 포함하지 않았습니다.*

GPU 노드는 실행 중인 동안 과금됩니다. 실습을 멈출 때 지우는 순서는 9단계에 적었습니다. 모든 단계는 저장소의 `AGENT.md`에 적힌 작업 규칙을 따릅니다.

- AWS 리소스를 만들거나 바꾸기 전에 `terraform plan` 또는 `kubectl diff`의 결과를 먼저 읽고 적용합니다.
- CRD 필드, Helm values, vLLM 플래그는 설치한 버전에서 확인합니다. `kubectl explain`, `helm show values`, 이미지 안의 `vllm serve --help`를 사용합니다.
- 자격 증명은 코드와 매니페스트에 넣지 않습니다. AWS 권한은 EKS Pod Identity로 연결한 IAM 역할로만 부여합니다. EKS Pod Identity는 파드의 ServiceAccount에 IAM 역할을 연결하는 Amazon EKS 기능입니다.
- 환경마다 다른 값이 든 파일 5개는 저장소에 없고 자리 표시만 든 `*.example`이 있습니다.

### 1.3 저장소 준비

```bash
git clone https://github.com/whchoi98/ow-on-gpu.git
cd ow-on-gpu
bash scripts/setup.sh
bash tests/run-all.sh
```

`scripts/setup.sh`는 AWS 리소스를 만들지 않습니다. 도구 확인, git 훅 설치, `*.example` 파일 복사, 확인용 페이지의 의존성 설치만 합니다. 복사된 파일의 자리 표시는 표 3의 값으로 바꿉니다. Terraform 출력에서 읽는 값은 1단계를 적용한 뒤에 채웁니다.

| 파일 | 채울 값 |
|---|---|
| `infra/terraform/terraform.tfvars` | EKS API에 접근을 허용할 작업 장비의 공인 IP |
| `k8s/base/params.yaml`, `jobs/model-sync/params.env`, `bench/coldstart/k8s/storage-s3.yaml` | 모델 버킷 이름. `terraform -chdir=infra/terraform output -raw model_bucket` |
| `k8s/observability/prometheus.yml` | Prometheus 워크스페이스 ID. `terraform -chdir=infra/terraform output -raw amp_workspace_id` |

*표 3. 환경마다 다른 값이 든 파일 5개와 채울 값.*

## 2. 구축 순서 한눈에 보기

도구는 맡는 범위가 나뉘어 있습니다. AWS CDK는 VPC를 만듭니다. Terraform은 그 VPC를 조회해 Amazon EKS와 계정 수준의 리소스를 만듭니다. kubectl과 Helm은 클러스터 안의 리소스를 적용합니다. 그림 2의 위쪽은 도구마다 어느 단계에서 무엇을 적용하는지입니다. 아래쪽은 순서가 가장 까다로운 7단계와 모든 단계에 공통인 적용 규칙입니다.

![도구와 적용 순서를 정리한 그림. AWS CDK는 1단계에 VPC를, Terraform은 1단계에 EKS와 Karpenter, 모델 버킷, 역할을, 5단계에 Decider 이미지의 ECR 저장소를, 7단계에 CloudFront와 WAF, Cognito, S3 페이지를, 8단계에 AMP 워크스페이스를 만들고 kubectl과 Helm은 1단계부터 8단계까지 클러스터 안의 리소스를 적용한다. 7단계는 ECR 저장소 생성, 이미지와 페이지 빌드, Terraform 적용, install.sh 적용, Terraform 재적용, 사용자 생성의 순서이고 모든 단계는 차이 확인, 검토, 적용, 확인의 순서를 따른다.](images/2026-11-15-eks-vllm-two-models-part3-fig02-tools-and-order.png)

*그림 2. 도구와 적용 순서. 9단계의 점선 칸은 아직 실행하지 않은 계획입니다.*

| 단계 | 만드는 것 | 도구 | 코드 |
|---|---|---|---|
| 0 | 버전 조합, 체크포인트, 할당량 확인 (리소스 없음) | AWS CLI | - |
| 1 | VPC, EKS, Karpenter, 모델 버킷, NodePool | AWS CDK, Terraform, kubectl | `infra/cdk-vpc`, `infra/terraform`, `k8s/base` |
| 2 | Amazon S3에 모델 3종 적재 | kubectl (Job) | `jobs/model-sync` |
| 3 | vLLM 파드 2개, compile 캐시 게시 | kubectl | `k8s/gemma`, `k8s/qwen`, `jobs/cache-publish` |
| 4 | 게이트웨이 계층 | Helm, kubectl | `k8s/gateway` |
| 5 | Strands Decider 12B | Terraform, Docker, kubectl | `k8s/decider`, `infra/terraform` |
| 6 | sleep 컨트롤러 | kubectl | `k8s/sleep-controller` |
| 7 | CloudFront, AWS WAF, Amazon Cognito, 내부 ALB, BFF | Terraform, kubectl, Docker | `app/bff`, `app/web`, `k8s/bff`, `infra/terraform` |
| 8 | 지표 수집과 측정 | kubectl, Python | `k8s/observability`, `bench` |
| 9 | 정리 (아직 실행하지 않음) | 계획만 있음 | - |

*표 4. 10개 단계와 코드의 위치. 단계 번호는 그림 1의 원 안의 번호와 같습니다.*

단계의 순서는 의존 관계를 따릅니다. 뒤 단계의 스크립트는 앞 단계의 Terraform 출력을 읽습니다. 서빙 파드는 2단계가 Amazon S3에 올린 객체만 읽습니다. 아래부터는 단계마다 만드는 것, 명령, 확인 방법과 측정한 값, 막히기 쉬운 곳의 순서로 적습니다.

## 3. 기반을 만드는 0단계에서 2단계

### 3.1 0단계 사전 확인

이 단계에서는 리소스를 만들지 않습니다. 버전 조합, 체크포인트, 서비스 할당량을 읽기 전용 조회로 확인합니다. 체크포인트는 학습된 가중치를 저장한 파일 묶음입니다. 확인한 내용은 `docs/00-versions.md`에 있습니다.

```bash
aws service-quotas list-service-quotas --service-code ec2 --region ap-northeast-2
```

AZ별 제공 여부는 `aws ec2 describe-instance-type-offerings --location-type availability-zone`으로 조회했습니다.

| 확인한 것 | 값 |
|---|---|
| 버전 조합 | EKS 1.37, Karpenter v1.15.2, AWS Load Balancer Controller v3.6.3, Gateway API CRD v1.6.3, GAIE CRD v1.6.2, llm-d-router v1.0.0, agentgateway v1.7.0, vLLM v0.33.0 |
| 체크포인트 | Gemma 4 31B는 `RedHatAI/gemma-4-31B-it-FP8-dynamic`(33.30GB), Qwen3.8-27B는 `AzatAI/Qwen3.8-27B-FP8-dynamic`(36.80GB) |
| G 계열 On-Demand 할당량 | 이 계정은 768 vCPU. 이 구성에 필요한 양은 36 vCPU |
| AZ별 제공 | g6e.4xlarge와 g6e.xlarge는 2a와 2b |

*표 5. 0단계에서 확인한 값(2026년 11월 14일 조회, g6e.xlarge의 AZ는 11월 24일 조회). 크기는 저장소 파일 크기의 합이고 1GB는 10^9바이트입니다.*

막히기 쉬운 곳입니다.

- 최신 버전끼리도 지원 범위가 어긋납니다. Gateway API CRD는 최신 v1.7.0이 agentgateway 1.7.x의 지원 범위(1.4에서 1.6) 밖이어서 v1.6.3을 사용했습니다.
- 체크포인트는 GPU에 맞춰 고릅니다. L40S(Ada 세대)에는 vLLM 문서가 지원을 명시한 FP8 체크포인트를 골랐습니다. FP8은 가중치를 8비트 부동소수점으로 줄인 양자화 형식입니다. Qwen3.8-27B의 공식 block FP8은 CUTLASS 커널이 SM 9.0 이상에서만 지원되는데 L40S는 SM 8.9입니다. 그래서 per-channel FP8-dynamic을 사용했습니다.

### 3.2 1단계 네트워크와 EKS 기반

VPC는 AWS CDK 스택 `EksVpcStack`으로 만듭니다. 대역은 10.200.0.0/16이고 4개 AZ에 Public, Private, Isolated 서브넷을 두며 워크로드는 Private 서브넷에서 실행합니다. Terraform은 이 VPC를 조회해 EKS 1.37 클러스터, 애드온, Karpenter, AWS Load Balancer Controller, 모델 버킷, IAM 역할을 만듭니다. Karpenter는 대기 중인 파드의 요구에 맞는 노드를 만드는 오토스케일러입니다. NodePool은 Karpenter가 만들 노드의 조건을 적은 리소스입니다. `k8s/base`는 네임스페이스, NodePool 4개(gemma-od, qwen-od, decider, system), EC2NodeClass, NVIDIA device plugin을 적용합니다.

```bash
(cd infra/cdk-vpc && npx cdk deploy)
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
# 아래 명령은 kubeconfig를 만드는 명령을 출력합니다. 출력된 명령을 확인한 뒤 실행합니다
terraform -chdir=infra/terraform output -raw update_kubeconfig
export KUBECONFIG=$PWD/infra/terraform/.kubeconfig
kubectl apply -k k8s/base
```

| 확인할 것 | 결과 |
|---|---|
| `terraform validate`, `kubectl apply --dry-run=server` | 두 검사가 통과 |
| `kubectl get nodes` | 클러스터에 연결됨. 애드온용 관리형 노드 그룹은 m7g.large 2대 |
| VPC | 10.200.0.0/16, AZ 4개 |
| GPU 노드 | 이 단계에서는 없음. 3단계와 5단계에서 파드가 생길 때 Karpenter가 만듦 |

*표 6. 1단계의 확인 항목.*

막히기 쉬운 곳입니다.

- `kubectl apply -k k8s/base` 전에 `k8s/base/params.yaml`의 모델 버킷 이름을 Terraform 출력으로 채웁니다.
- GPU NodePool에는 taint를 두고 NodePool마다 GPU를 1장까지만 허용합니다. 노드가 의도하지 않게 늘어나는 것을 막는 설정입니다.
- EC2NodeClass는 NVIDIA 드라이버가 든 EKS 최적화 AMI를 사용합니다. userData로 vLLM 이미지를 미리 받고 로컬 NVMe를 인스턴스 스토어로 사용합니다.
- kubectl은 프로젝트 전용 kubeconfig로 실행합니다. 공유 장비의 기본 컨텍스트를 바꾸지 않기 위해서입니다.

### 3.3 2단계 모델 적재

적재 Job이 Hugging Face의 저장소 3개를 Amazon S3의 모델 버킷에 올립니다. Gemma 4 31B, Qwen3.8-27B, 5단계에서 배포할 Strands Decider 12B입니다. Decider 12B의 체크포인트는 가중치를 모두 담고 있어 기반 모델을 따로 올리지 않습니다. Job은 한 번만 실행하고 그 뒤로 서빙 파드는 Amazon S3에서만 읽습니다. 파일을 받는 대로 `s5cmd pipe`로 올려 가중치를 로컬 디스크에 쌓지 않습니다. 파일은 8개를 동시에 처리합니다.

```bash
kubectl apply -k jobs/model-sync
kubectl -n model-jobs logs -f job/model-sync
kubectl -n model-jobs wait --for=condition=complete job/model-sync --timeout=60m
```

| 확인할 것 | 첫 적재 (2026년 11월 14일) | Decider 12B 추가 (2026년 11월 24일) |
|---|---|---|
| Job 로그의 `verified` 줄 | 객체 수와 크기가 기대값과 일치 | 객체 수와 크기가 기대값과 일치 |
| Job 로그의 `summary` 줄 | 객체 73개, 74.90GB | 객체 13개, 23.97GB. 이미 있는 32개는 건너뜀 |
| 전송과 검증에 걸린 시간 | 491.4초 | 314.9초 |
| Job 시작부터 완료까지 | 9분 8초 | 6분 35초 |

*표 7. 2단계의 확인 항목과 측정한 값(1회씩). 첫 적재의 값에는 당시 사용하던 Decider v1과 그 기반 모델이 들어 있습니다. 지금의 저장소 3개를 합치면 객체 45개, 94.07GB입니다.*

막히기 쉬운 곳입니다.

- `jobs/model-sync/params.env`의 `BUCKET`은 Terraform 출력 `model_bucket`과 같아야 합니다.
- 다시 실행하려면 `kubectl -n model-jobs delete job model-sync`로 Job을 지우고 적용합니다. Job의 파드 템플릿은 바꿀 수 없기 때문입니다. Job을 지우면 로그도 사라지므로 먼저 저장합니다.
- 저장소는 리비전 해시로 고정했습니다. Job은 받으면서 계산한 해시를 Hugging Face가 알려 준 값과 비교합니다. 끝나면 S3의 객체 목록을 기대값과 비교하고 다르면 실패합니다.

## 4. 모델을 서빙하는 3단계에서 6단계

### 4.1 3단계 vLLM 배포

Gemma 4 31B와 Qwen3.8-27B를 g6e.4xlarge 노드에 한 대씩 배포합니다. 이 단계에서 GPU 노드 2대가 뜹니다. 가중치는 `runai_streamer` 로더로 Amazon S3에서 직접 읽습니다. initContainer는 S3의 compile 캐시를 노드의 hostPath로 내려받습니다. compile 캐시는 vLLM이 엔진을 초기화할 때 만드는 `torch.compile` 결과물입니다. 첫 기동 뒤에는 캐시 게시 Job이 이 캐시를 S3에 올려 다음 기동이 사용하게 합니다.

```bash
kubectl diff -k k8s/gemma
kubectl apply -k k8s/gemma
kubectl apply -k k8s/qwen
kubectl apply -k jobs/cache-publish
```

확인은 네임스페이스 `inference`에 있는 vLLM 파드(`vllm-gemma`, `vllm-qwen`)의 로그에서 합니다. 가중치 로드와 엔진 초기화가 끝나면 아래 두 줄이 나옵니다. Gemma 4 31B의 첫 기동에서 나온 값입니다.

```text
Model loading took 30.63 GiB memory and 19.106861 seconds
init engine (profile, create kv cache, warmup model) took 95.84 s (compilation: 61.03 s)
```

| 항목 | Gemma 4 31B | Qwen3.8-27B |
|---|---|---|
| 가중치 로드 | 19.1초 | 34.3초 |
| 가중치가 차지한 GPU 메모리 | 30.63GiB | 34.39GiB |
| KV 캐시 | 5.37GiB (34,052토큰) | 2.46GiB (42,780토큰) |
| 엔진 초기화 | 95.84초 (compile 캐시 없음) | 57.85초 (compile 캐시 적중) |
| 게시한 compile 캐시 | 객체 522개, 90.8MB | 객체 2,056개, 216.7MB |

*표 8. 3단계에서 측정한 값(2026년 11월 14일, 첫 기동 1회). KV 캐시는 처리 중인 요청의 토큰별 중간 계산 결과를 담는 GPU 메모리입니다. Qwen3.8-27B의 2.46GiB는 이 첫 기동 로그의 값이고 2부의 처리량 측정 때 로그에는 2.45GiB로 기록됐습니다.*

막히기 쉬운 곳입니다.

- 플래그는 이미지 안에서 `vllm serve --help`로 확인한 뒤 사용합니다. v0.33.0 이미지에 이 구성의 플래그 14개가 모두 있었습니다.
- Qwen3.8-27B는 `--gpu-memory-utilization` 0.85에서 KV 캐시에 0.24GiB만 남아 시작하지 못했고 0.90에서 시작했습니다. `--max-num-seqs`도 기본값 1024에서는 엔진이 시작하지 못해 32로 두었습니다.
- Qwen3.8-27B의 readinessProbe는 `/is_sleeping`을 확인합니다. `/health`는 잠든 동안에도 200을 반환하기 때문입니다.
- compile 캐시의 S3 prefix에는 vLLM 버전, 모델, 정밀도, GPU 아키텍처를 넣습니다. 구성이 하나라도 바뀌면 새 prefix로 게시합니다.

### 4.2 4단계 GAIE와 게이트웨이

요청 본문의 `model` 값으로 모델별 파드 묶음을 고르는 게이트웨이 계층을 설치합니다. Gateway API Inference Extension(GAIE)은 추론 요청을 모델 서버 파드의 묶음인 InferencePool로 보내는 Gateway API 확장입니다. EPP(Endpoint Picker)는 풀 안에서 요청을 보낼 파드를 고릅니다. 게이트웨이 구현체는 agentgateway입니다. agentgateway가 본문의 `model` 값을 헤더로 옮기고 HTTPRoute가 그 헤더로 풀을 고릅니다.

```bash
k8s/gateway/install.sh render | kubectl diff -f -
k8s/gateway/install.sh apply
```

`apply`는 CRD, agentgateway, 모델별 EPP와 InferencePool, Gateway를 순서대로 적용하고 72초 걸렸습니다. 표 9는 클러스터 안의 임시 파드에서 게이트웨이의 Service로 요청을 보낸 결과입니다.

| 확인할 것 | 결과 |
|---|---|
| `/v1/chat/completions`, `model`이 `gemma-4-31b` | 200, Gemma 4 31B가 응답 |
| `/v1/chat/completions`, `model`이 `qwen38-27b` | 200, Qwen3.8-27B가 응답 |
| 등록하지 않은 `model` 값 | 404 |
| `POST /sleep?level=1` | 404 |
| Gateway, HTTPRoute, InferencePool의 상태 | `Accepted=True`, `ResolvedRefs=True` |

*표 9. 4단계의 확인 항목(2026년 11월 14일, 요청마다 1회).*

막히기 쉬운 곳입니다.

- HTTPRoute에는 `/v1/chat/completions`와 `/v1/models`만 등록합니다. `/sleep`과 `/wake_up` 같은 관리 경로는 게이트웨이로 노출되지 않습니다.
- EPP는 풀마다 2개지만 리더 하나만 요청을 처리합니다. 대기 복제본이 NotReady로 보이는 것은 설계된 동작입니다.
- 게이트웨이 파드 2개를 AZ 두 곳에 나누려면 `topologySpreadConstraints`에 `minDomains: 2`와 `matchLabelKeys: [pod-template-hash]`를 함께 둬야 했습니다.
- 게이트웨이의 내부 Network Load Balancer(NLB)는 클러스터 밖의 배치 클라이언트용입니다. BFF는 게이트웨이의 Service를 직접 호출합니다.

### 4.3 5단계 Strands Decider 12B

Strands Decider 12B(이하 Decider 12B)는 요청을 읽고 어느 모델이 맡을지 판단하는 모델입니다. BFF는 규칙과 업무 종류로 모델이 정해지지 않은 요청만 Decider 12B에 묻습니다. g6e.xlarge 노드에 파드 하나로 배포합니다. 게이트웨이의 HTTPRoute가 `POST /decide`를 Decider 12B의 `/v1/systemone`으로 경로를 바꿔 보냅니다. InferencePool은 사용하지 않습니다. 이 환경은 2026년 11월 24일에 Decider를 v1의 2B 모델(g6.xlarge)에서 [Strands Decider v2](https://strandsagents.com/blog/introducing-strands-decider-v2/)의 12B 모델로 바꿨고 아래는 v2의 절차와 측정값입니다.

서빙 이미지는 직접 빌드합니다. v2의 체크포인트는 strands-decider 0.4.0 이상에서만 읽히는데 저장소가 안내하는 공개 서빙 이미지는 2026년 11월 20일 빌드까지 0.3.1.dev1을 담고 있었습니다. 그래서 strands-decider 저장소 v0.4.0 태그의 `deploy/sagemaker/Dockerfile`을 수정 없이 빌드합니다. 빌드한 이미지는 Amazon Elastic Container Registry(Amazon ECR)에 올립니다.

```bash
terraform -chdir=infra/terraform apply -target=aws_ecr_repository.decider
k8s/decider/install.sh build
k8s/decider/install.sh diff
k8s/decider/install.sh apply
```

| 확인할 것 | 결과와 측정한 값 |
|---|---|
| 이미지 빌드 (arm64 장비에서 amd64 에뮬레이션) | 8분 25초, 압축 크기 3.72GB |
| `/health` 응답 | `model`이 `strands-decider-12B-gemma4-v2-2611`, `device`가 `cuda:0` |
| 컨테이너 시작부터 Ready | 43초 (가중치 적재와 예열 포함) |
| 노드가 새로 뜰 때 적용부터 Ready | 5분 33초 (노드 83초, 모델 받기 101초, 이미지 pull 90.5초) |
| 판단 1회, 게이트웨이 `/decide` 경유 | 중앙값 89.7ms에서 90.6ms (판단 종류마다 50회) |
| GPU 메모리 | L40S의 46,068MiB 가운데 23,725MiB 사용 |

*표 10. 5단계의 확인 항목과 측정한 값(2026년 11월 24일, 1회).*

막히기 쉬운 곳입니다.

- 공개 서빙 이미지에 든 strands-decider의 버전은 태그로 알 수 없습니다. 이미지 설정의 레이블과 패키지 레이어로 확인했습니다. 공개 이미지가 0.4.0 이상을 담으면 그 이미지를 사용하고 빌드 단계를 생략할 수 있습니다.
- 작업 장비가 arm64이면 amd64 에뮬레이션(binfmt)을 등록한 뒤 빌드합니다. `install.sh build`는 `docker buildx build --platform linux/amd64`를 실행합니다. 장비를 재부팅하면 등록이 사라집니다.
- `kubectl apply -k k8s/decider`로 직접 적용하지 않습니다. 이미지 주소에 계정 ID가 들어가므로 매니페스트의 `${DECIDER_IMAGE}` 자리를 `install.sh`가 Terraform 출력으로 채웁니다.
- 예열이 끝날 때까지 `/health`가 실패하므로 파드는 예열 뒤에 Ready가 됩니다.
- `HF_HUB_OFFLINE=1`로 Hugging Face 접근을 막았습니다. 가중치는 initContainer가 Amazon S3에서 받습니다.
- 이 서버에는 인증이 없습니다. ClusterIP Service와 게이트웨이의 `/decide`로만 닿게 둡니다.

### 4.4 6단계 sleep 컨트롤러

업무 시간 밖에 Qwen3.8-27B를 재우고 필요할 때 깨우는 구성입니다. vLLM의 sleep mode는 파드를 내리지 않고 GPU 메모리를 비우는 기능입니다. level 1 sleep은 가중치를 호스트 메모리에 둡니다. CronJob 2개가 평일 19:00에 재우고 08:30에 깨웁니다(Asia/Seoul). 깨우기 API는 `POST /wake`만 제공합니다. BFF가 Qwen3.8-27B로 갈 요청 앞에서 이 API를 호출합니다.

```bash
kubectl apply -k k8s/sleep-controller
```

| 확인할 것 | 결과와 측정한 값 |
|---|---|
| sleep 진입 (`/sleep` 응답까지) | 2.98초 |
| 복귀 (깨우기 API 응답까지) | 3.66초 |
| 깨우기 응답 뒤 게이트웨이 요청이 성공하기까지 | 1.34초에서 1.40초 |
| 잠든 동안 게이트웨이로 보낸 Qwen3.8-27B 요청 | 503 |
| 라벨 없는 파드에서 Qwen3.8-27B의 8000 포트와 깨우기 API로 보낸 요청 | 차단 |

*표 11. 6단계의 확인 항목과 측정한 값(2026년 11월 14일, 시간은 5회 측정의 범위).*

막히기 쉬운 곳입니다.

- NetworkPolicy는 Amazon VPC CNI 애드온의 `enableNetworkPolicy`를 켜야 적용됩니다. 기본값은 꺼짐이어서 그 전에는 정책을 만들어도 적용되지 않습니다. 설정은 `infra/terraform/eks.tf`에 있습니다.
- 재울 때는 `/sleep?level=1&mode=wait`를 호출합니다. 기본값 `abort`는 진행 중인 요청을 끊습니다.
- 잠든 파드는 NotReady가 되어 일반 Service에서 빠집니다. 관리 요청은 NotReady 파드의 주소도 반환하는 헤드리스 Service `vllm-qwen-admin`으로 보냅니다.
- 파드가 뜬 뒤 첫 sleep은 31.71초 걸렸고 그 뒤로는 2.98초였습니다. sleep을 한 번 거친 뒤 컨테이너 메모리는 60.4GiB였습니다.

## 5. 사용자 경로와 관측을 만드는 7단계와 8단계

### 5.1 7단계 앱 계층

사용자가 닿는 앞단을 만듭니다. CloudFront와 AWS WAF, Amazon Cognito 사용자 풀, 확인용 페이지를 담는 S3 버킷, BFF 파드, 내부 ALB입니다. BFF는 네임스페이스 `app`의 파드 2개이고 Karpenter NodePool `app`이 만든 Graviton 노드(c7g.large) 2대에서 실행합니다. 웹 검색 도구도 BFF에 들어 있습니다. BFF의 IAM 역할에는 Amazon Bedrock AgentCore Web Search(이하 Web Search)를 호출하는 권한 하나만 있습니다. 호출 리전은 us-east-1입니다. 서울 리전에는 이 API가 없기 때문입니다.

내부 ALB는 Terraform이 아닌 AWS Load Balancer Controller가 Ingress에서 만듭니다. 그래서 그림 2의 아래쪽처럼 Terraform, `k8s/bff/install.sh`, Terraform의 순서로 적용합니다.

```bash
terraform -chdir=infra/terraform apply -target=aws_ecr_repository.bff
app/bff/build.sh
app/web/build.sh
terraform -chdir=infra/terraform plan
terraform -chdir=infra/terraform apply
k8s/bff/install.sh diff
k8s/bff/install.sh apply
terraform -chdir=infra/terraform apply
app/bff/create-user.sh <이메일>
```

순서마다 이유가 있습니다. ECR 저장소가 있어야 `app/bff/build.sh`가 이미지를 올립니다. 이 스크립트는 arm64 이미지를 만들고 이미지 안에서 BFF 시험을 실행한 뒤 태그를 `infra/terraform/bff.auto.tfvars`에 적습니다. 가운데 `terraform apply`는 BFF의 역할과 Pod Identity 연결을 만듭니다. 파드가 만들어질 때 이 연결이 없으면 자격 증명이 주입되지 않아 웹 검색이 실패합니다. `k8s/bff/install.sh apply`가 NodePool, 파드, Ingress를 적용하면 컨트롤러가 내부 ALB를 만듭니다. 마지막 `terraform apply`는 그 ALB를 태그로 조회해 CloudFront의 VPC origin에 연결합니다.

| 확인할 것 | 결과와 측정한 값 |
|---|---|
| `kubectl -n app rollout status deploy/bff --timeout=300s` | 파드 2개가 Ready |
| 토큰 없는 `POST /v1/chat/completions` | 401 |
| 로그인 토큰으로 보낸 상담 요청 | 200, 내용 이벤트 53개가 중앙값 53.5ms 간격으로 도착 |
| CloudFront VPC origin 생성 | 9분 18초 |
| 앱 계층의 고정 비용 | 시간당 0.1857 USD (내부 ALB 0.0225, c7g.large 2대 0.1632) |

*표 12. 7단계의 확인 항목과 측정한 값(2026년 11월 15일, 요청마다 1회). 금액은 세전 USD이고 사용량에 따라 부과되는 요금은 포함하지 않았습니다.*

막히기 쉬운 곳입니다.

- 스트리밍에 맞춰 타임아웃을 늘렸습니다. CloudFront 오리진 응답 타임아웃은 60초(기본 30초), ALB 유휴 제한 시간은 120초(기본 60초)입니다.
- BFF는 응답을 모으지 않고 받은 Chunk(한 번에 전송되는 응답 단위)를 그대로 전달합니다. 모아서 내보내면 스트리밍이 깨집니다.
- 가입은 막아 두었고 사용자는 `create-user.sh`로만 만듭니다. 비밀번호는 프롬프트나 환경 변수 `USER_PASSWORD`로 받아 Amazon Cognito에만 저장합니다.
- `k8s/bff/install.sh`는 자기 디렉터리로 옮겨 가 실행하므로 `KUBECONFIG`를 절대 경로로 지정합니다.

### 5.2 8단계 관측과 측정

지표를 Amazon Managed Service for Prometheus(AMP)로 모으고 측정 스크립트를 실행합니다. agent 모드의 Prometheus v3.16.0 하나가 vLLM 파드 2개, EPP 파드 4개, 게이트웨이 파드 2개를 수집해 AMP로 보냅니다. 측정은 콜드 스타트의 구간 분해, 구간별 첫 내용까지의 시간, SLO(서비스 수준 목표) 하 처리량, 우선순위 효과의 4가지이고 스크립트는 `bench/` 아래에 있습니다. 부하 발생기는 측정 전용 NodePool `bench`에서 Job으로 실행합니다.

```bash
kubectl apply -k k8s/observability
python3 bench/coldstart/measure.py --model gemma --scenario cold-optimized --out results/2026-11-14-coldstart
python3 bench/job.py --name slo-gemma --service-account gemma --out results/2026-11-14-slo/gemma \
  --env MODEL_NAME=gemma-4-31b --env MODEL_DIR=gemma-4-31B-it-FP8-dynamic \
  --env BASE_URL=http://vllm-gemma.inference.svc:8000 -- bash /bench/run-bench.sh
```

적용 전에 `k8s/observability/prometheus.yml`의 워크스페이스 ID를 Terraform 출력 `amp_workspace_id`로 채웁니다.

| 확인할 것 | 결과와 측정한 값 |
|---|---|
| 수집 대상 8개 | 모두 `up` |
| 대시보드 `k8s/observability/dashboards/serving.json`의 쿼리 27개 | 모두 값이 나옴 |
| Gemma 4 31B의 콜드 스타트 | 394초에서 260초 (기준 구성과 최적화 구성, 1회씩) |
| 사용자가 본 첫 내용까지의 시간 | Gemma 4 31B 81.9ms, Qwen3.8-27B 177.5ms (20건의 중앙값) |
| 배치 부하 중 상담 요청의 첫 토큰까지의 시간 | 30.9초에서 0.19초 (우선순위 없음과 엔진 우선순위, 60건의 중앙값) |

*표 13. 8단계의 확인 항목과 측정한 값(2026년 11월 14일, 첫 내용까지의 시간은 11월 15일). 값의 뜻과 원인은 1부와 2부에서 설명했습니다.*

막히기 쉬운 곳입니다.

- EPP의 `/metrics`는 토큰 없이는 401입니다. 수집기의 ServiceAccount 토큰과 ClusterRole `ow-on-gpu-metrics-reader`로 수집합니다. Qwen3.8-27B의 NetworkPolicy에도 수집기를 허용하는 항목을 더합니다.
- `vllm bench serve`는 GPU가 없는 노드에서 "Failed to infer device type"으로 시작하지 못합니다. 측정 파드는 `bench/slo/bench_serve.py`로 같은 벤치마크 모듈을 직접 호출합니다.
- 평일 19:00부터 08:30까지는 Qwen3.8-27B가 잠들어 있습니다. 그 시간대에 측정하려면 CronJob `qwen-sleep`을 suspend합니다.
- CloudFront 주소로 부하를 걸 때는 Terraform 변수 `waf_rate_limit`을 올리거나 측정 장비를 예외로 둡니다.

## 6. 전체 동작 확인

8단계까지 마쳤다면 노드 목록, 사이트 주소, 인증, 모델까지의 경로를 차례로 확인합니다.

```bash
export KUBECONFIG=$PWD/infra/terraform/.kubeconfig
kubectl get nodes -L node.kubernetes.io/instance-type,karpenter.sh/nodepool
terraform -chdir=infra/terraform output -raw app_url
python bench/bff/lang_check_live.py "$(terraform -chdir=infra/terraform output -raw app_url)"
kubectl -n app exec -i <bff-pod> -- python - < bench/bff/lang_check_in_pod.py
```

노드 목록에는 표 1의 9대가 보입니다. 세 번째 명령이 출력하는 `https://<cloudfront-domain>` 주소를 열고 7단계에서 만든 사용자로 로그인한 뒤 요청을 보냅니다. 응답 헤더 `x-bff-model`, `x-bff-decision`, `x-bff-search`, `x-bff-timing`이 그 요청의 모델, 결정 근거, 웹 검색 여부, BFF 안의 구간 시간을 알려 줍니다. 헤더를 읽는 방법은 1부에 있습니다.

나머지 두 명령은 비밀번호 없이 실행하는 확인입니다. `lang_check_live.py`는 토큰 없는 요청이 401로 돌아오는지와 페이지 오류를 봅니다. `lang_check_in_pod.py`는 BFF 파드 안에서 같은 앱을 토큰 검증기만 바꿔 띄우고 요청을 실제 모델까지 보냅니다. 그림 3은 단계마다 확인한 것과 측정한 값을 한 장에 모은 확인표입니다.

![1단계에서 8단계까지의 확인 방법, 측정한 값, 막히기 쉬운 곳을 정리한 확인표. 모델 적재는 첫 적재 객체 73개와 491초, vLLM 배포는 가중치 로드 19.1초와 34.3초, 게이트웨이 설치는 72초, Decider 12B는 컨테이너 시작부터 Ready까지 43초, sleep 복귀는 3.66초, 앱 계층의 이벤트 간격은 중앙값 53.5ms, 관측 단계의 첫 내용은 81.9ms와 177.5ms이고 완성된 환경은 노드 9대에 시간당 고정 비용이 약 11.35 USD이다.](images/2026-11-15-eks-vllm-two-models-part3-fig03-step-checks.png)

*그림 3. 단계별 확인표. 횟수를 적지 않은 값은 한 번 측정한 값입니다.*

## 7. 자주 막히는 곳

표 14는 이 환경을 만들면서 실제로 겪은 증상입니다. 오류 문구로 찾을 수 있게 증상을 먼저 적었습니다.

| 증상 | 원인 | 조치 | 단계 |
|---|---|---|---|
| `terraform plan`이 `helm_release.karpenter`에서 실패 | `-target` 없이 전체를 plan하면 레지스트리 로그인에서 실패 | 변경 범위를 `-target`으로 좁힘 | 7 |
| Qwen3.8-27B 엔진이 시작하지 못하고 컨테이너가 다시 시작됨 | `--gpu-memory-utilization` 0.85에서 KV 캐시에 0.24GiB만 남음 | 0.90으로 올림 | 3 |
| 보안 그룹 교체가 `couldn't find all security groups`로 실패 | AWS Load Balancer Controller가 어노테이션의 이름을 `Name` 태그에서 찾음 | Terraform의 보안 그룹에 `Name` 태그를 붙임 | 7 |
| 배치 요청이 429로 거절됨 | batch의 priority가 -1이어서 풀이 포화되면 대기하지 않고 거절됨 | 배치 클라이언트의 재시도 간격을 늘림 | 4 |
| 공개 서빙 이미지에 Decider v2 체크포인트를 읽는 모듈이 없음 | 2026년 11월 20일 빌드까지 strands-decider 0.3.1.dev1이 들어 있음 | 저장소 v0.4.0 태그의 Dockerfile로 이미지를 빌드 | 5 |
| 게이트웨이로 보낸 Qwen3.8-27B 요청이 503 | Qwen3.8-27B가 잠들어 엔드포인트에서 빠짐 | 깨우기 API를 먼저 호출. BFF는 이 순서로 호출함 | 6 |
| NetworkPolicy를 만들어도 차단되지 않음 | VPC CNI의 `enableNetworkPolicy`가 꺼져 있음 | 애드온 설정에서 켬 | 6 |
| `k8s/bff/install.sh`가 `localhost:8080`에 연결하려다 실패 | `KUBECONFIG`가 상대 경로 | 절대 경로로 지정 | 7 |
| `kubectl diff`에 작성하지 않은 줄이 보임 | 서버 dry-run이라 클러스터의 웹훅이 더하는 줄까지 보임 | 적용하지 않고 무엇이 더하는지 먼저 확인 | 모든 단계 |
| CloudFront 주소의 요청이 모두 403 | AWS WAF 속도 제한(IP당 5분 300회)을 넘김 | 한동안 기다리거나 `waf_rate_limit`을 올림 | 7, 8 |
| AMP에 보낸 쿼리가 403 | PromQL을 GET의 쿼리 문자열로 보내면 서명이 맞지 않음 | 본문(POST)으로 보냄 | 8 |

*표 14. 증상별 원인과 조치. 단계는 그 증상을 만나는 단계입니다.*

## 8. 9단계 정리 계획

정리는 아직 실행하지 않았습니다. 아래는 계획한 순서이고 실행 결과가 아닙니다.

1. GPU 노드가 먼저 사라지도록 Deployment와 NodePool을 지웁니다.
2. `terraform destroy`를 실행합니다.
3. S3의 `models`와 `vllm-cache` prefix는 기본으로 남깁니다. 별도 플래그를 줬을 때만 지웁니다.
4. 남은 EC2, NLB, ALB, CloudFront 리소스를 조회해 확인합니다.
5. VPC는 CDK 스택이므로 따로 지웁니다.

지울 때 지킬 규칙이 하나 있습니다. 서로 참조하는 보안 그룹은 참조하는 쪽의 규칙을 먼저 고친 뒤 지웁니다. 순서가 반대면 삭제가 `DependencyViolation`으로 실패합니다.

## 9. 마치며

10개 단계를 한 번에 끝까지 갈 필요는 없습니다. 각 단계는 그 단계의 확인을 마친 뒤 다음 단계로 넘어갔으므로, 어느 단계에서 멈춰도 그때까지 만든 것은 표 15처럼 동작했습니다.

| 여기까지 만들면 | 사용할 수 있는 것 | 더하지 않은 것 |
|---|---|---|
| 3단계 | 클러스터 안에서 모델별 Service의 OpenAI 호환 API | 하나의 엔드포인트, 로그인, 지표 |
| 4단계 | 게이트웨이 하나에 `model` 값만 바꿔 두 모델을 호출 | 모델을 대신 골라 주는 계층, 로그인 |
| 5단계와 6단계 | 모델 판단을 맡는 Decider 12B, Qwen3.8-27B의 sleep과 깨우기 | 사용자가 닿는 경로 |
| 7단계 | 로그인한 브라우저에서 CloudFront 주소로 받는 스트리밍 응답 | 지표와 대시보드 |
| 8단계 | 지표 대시보드와 측정 스크립트 | 정리 |

*표 15. 단계별로 사용할 수 있는 것. 각 단계가 끝난 시점에 그 단계의 확인 항목으로 본 범위입니다.*

처음이라면 3단계에서 `k8s/gemma`만 적용해 모델 하나가 응답하는 것부터 확인하는 것을 권고합니다. 이때는 Gemma 4 31B 파드 하나만 GPU를 요청하므로 Karpenter가 만드는 GPU 노드도 `gemma-od` NodePool의 한 대입니다. 두 모델을 하나의 엔드포인트로 묶을 필요가 생기면 4단계를, 사용자에게 공개할 때 7단계를 더합니다.

확인하지 못한 것도 있습니다. 9단계는 실행하지 않았습니다. 측정은 대부분 한 번씩이어서 반복했을 때의 편차도 확인하지 않았습니다. EPP와 게이트웨이 파드가 내려갔을 때의 동작도 시험하지 않았습니다. 이 글의 단계와 확인표가 여러분의 Amazon EKS 기반 LLM 서빙 환경 구축에 실질적인 참고가 되기를 바랍니다.

## 참고 자료

- [ow-on-gpu – GitHub 저장소](https://github.com/whchoi98/ow-on-gpu)
- [Learn how EKS Pod Identity grants pods access to AWS services – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Assign an IAM role to a Kubernetes service account – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html)
- [Use EKS-optimized accelerated Linux AMIs for GPU instances – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/ml-eks-optimized-ami.html)
- [Restrict Pod network traffic with Kubernetes network policies – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html)
- [Amazon EC2 G6e Instances – 제품 페이지](https://aws.amazon.com/ko/ec2/instance-types/g6e/)
- [NodePools – Karpenter 문서](https://karpenter.sh/docs/concepts/nodepools/)
- [NodeClasses – Karpenter 문서](https://karpenter.sh/docs/concepts/nodeclasses/)
- [vllm serve – vLLM CLI 레퍼런스 (v0.33.0)](https://docs.vllm.ai/en/v0.33.0/cli/serve/)
- [Loading models with Run:ai Model Streamer – vLLM 문서](https://docs.vllm.ai/en/latest/models/extensions/runai_model_streamer/)
- [torch.compile integration – vLLM 문서](https://docs.vllm.ai/en/latest/design/torch_compile/)
- [Quantization – vLLM 문서](https://docs.vllm.ai/en/latest/features/quantization/)
- [Sleep Mode – vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)
- [RedHatAI/gemma-4-31B-it-FP8-dynamic – Hugging Face 모델 카드](https://huggingface.co/RedHatAI/gemma-4-31B-it-FP8-dynamic)
- [AzatAI/Qwen3.8-27B-FP8-dynamic – Hugging Face 모델 카드](https://huggingface.co/AzatAI/Qwen3.8-27B-FP8-dynamic)
- [Introduction – Gateway API Inference Extension 문서](https://gateway-api-inference-extension.sigs.k8s.io/)
- [InferencePool – Gateway API Inference Extension API 문서](https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/)
- [Inference routing – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/inference-routing/)
- [Multiple inference pools – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)
- [strands-decider – GitHub 저장소](https://github.com/strands-labs/strands-decider)
- [Restrict access with VPC origins – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Origin settings – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/DownloadDistValuesOrigin.html)
- [Rate-based rule caveats in AWS WAF – AWS WAF Developer Guide](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)
- [Ingress annotations – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/guide/ingress/annotations/)
- [Security Groups for Load Balancers – AWS Load Balancer Controller 문서](https://kubernetes-sigs.github.io/aws-load-balancer-controller/latest/deploy/security_groups/)
- [Search the web using Amazon Bedrock AgentCore Web Search – Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)
- [Set up ingestion from an existing Prometheus server in Kubernetes on EC2 – Amazon Managed Service for Prometheus User Guide](https://docs.aws.amazon.com/prometheus/latest/userguide/AMP-onboard-ingest-metrics-existing-Prometheus.html)
- [Prometheus Agent Mode – Prometheus 문서](https://prometheus.io/docs/prometheus/latest/prometheus_agent/)

*본문의 값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)의 한 환경에서 측정한 값이며 측정 횟수는 표마다 적었습니다. 5단계 Decider 12B의 값은 2026년 11월 24일에 측정했습니다. 금액은 2026년 11월 15일에 확인한 공개 단가에 11월 26일에 확인한 g6.xlarge와 g6e.xlarge의 단가 차이를 반영한 시간당 세전 USD 추정치입니다. 최종 금액은 사용량과 요금 변경에 따라 달라질 수 있습니다. 9단계(정리)는 실행하지 않은 계획입니다.*

## 저자 소개

**최우형 (Woohyung Choi)** 님은 AWS Korea의 Principal Solutions Architect로, 국내 주요 엔터프라이즈 및 디지털 기업의 클라우드 전환과 아키텍처 현대화를 지원하고 있습니다. 특히 클라우드 네이티브 아키텍처와 Agentic AI 분야에 전문성을 가지고 있으며, 고객이 Amazon Bedrock을 비롯한 AWS의 생성형 AI 및 Agentic AI 기술을 안정적이고 비용 효율적으로 도입하고 확장할 수 있도록 아키텍처 설계와 기술 자문을 제공하고 있습니다.

컨테이너, 네트워킹, 비용 최적화를 비롯한 클라우드 핵심 기술부터 Agentic AI를 활용한 업무 혁신과 지능형 시스템 구축까지 폭넓은 영역에서 AWS 아키텍처 모범 사례를 제시하고 있습니다. 이를 통해 고객의 복잡한 기술적 과제를 해결하고, AI와 클라우드를 기반으로 지속 가능한 기술 전략을 수립하고 실행할 수 있도록 기술 리더십을 발휘하고 있습니다.
