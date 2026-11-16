---
title: "파드 생성에서 Ready까지 394초를 260초로 – Amazon EKS에서 vLLM 콜드 스타트를 구간별로 줄이기 (1부)"
date: 2026-11-15
author: "Woohyung Choi"
status: draft
---

# 파드 생성에서 Ready까지 394초를 260초로 – Amazon EKS에서 vLLM 콜드 스타트를 구간별로 줄이기 (1부)

by WOO HYUNG CHOI on 15 11월 2026 in [Advanced (300)](https://aws.amazon.com/ko/blogs/tech/category/learning-levels/advanced-300/), [Amazon Elastic Kubernetes Service](https://aws.amazon.com/ko/blogs/tech/category/compute/amazon-kubernetes-service/), [Generative AI](https://aws.amazon.com/ko/blogs/tech/category/artificial-intelligence/generative-ai/)

GPU 노드에서 LLM 서빙 파드를 새로 띄우면 요청을 받기까지 몇 분이 걸립니다. 노드가 준비되면 9.7GB 컨테이너 이미지를 받고 30GiB가 넘는 가중치를 GPU 메모리에 올립니다. 그 뒤 엔진이 연산 그래프를 컴파일해야 파드가 Ready가 됩니다. 이 글은 그 시간을 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화의 네 구간으로 나눠 잰 뒤 구간마다 다른 방법으로 줄인 기록입니다. 대상은 Amazon Elastic Kubernetes Service(Amazon EKS)에서 vLLM으로 서빙하는 Gemma 4 31B입니다. 새 노드에서 시작하는 콜드 스타트(Cold start)는 기준 구성 394초에서 최적화 구성 260초가 됐습니다. 같은 노드에서 파드만 다시 띄우는 웜 재시작(Warm restart)은 214초에서 86초가 됐습니다. 모든 값은 2026년 11월 14일 서울 리전(ap-northeast-2)에서 시나리오마다 한 번 잰 것이어서 반복했을 때의 편차는 담겨 있지 않습니다.

이 글은 "Amazon EKS에서 vLLM으로 두 모델 서빙하기" 시리즈의 1부입니다. 2부(TODO: Part 2 링크)는 같은 환경의 처리량과 SLO(서비스 수준 목표)를, 3부(TODO: Part 3 링크)는 게이트웨이와 모델 라우팅, 앱 계층을 다룹니다. 이 글은 Amazon EKS에서 GPU 워크로드를 운영하는 플랫폼 엔지니어를 대상으로 하며, Kubernetes와 LLM 서빙의 기본 개념을 알고 있다면 무리 없이 읽을 수 있습니다.

## 1. 전체 구성과 콜드 스타트의 네 구간

### 1.1 시리즈에서 다루는 구성

환경은 서울 리전의 Amazon EKS 1.37 클러스터 하나입니다. Gemma 4 31B와 Qwen3.8-27B가 각각 NVIDIA L40S(g6e.4xlarge) 한 장을 사용합니다. Strands Decider 2B는 요청을 어느 모델로 보낼지 판단을 돕는 모델이고 g6.xlarge 한 대에서 실행됩니다. GPU 노드 세 대는 모두 On-Demand이고 Karpenter가 만듭니다.

![서울 리전 VPC 안의 Amazon EKS 클러스터에서 Karpenter가 만든 g6e.4xlarge 노드 두 대가 Gemma 4 31B와 Qwen3.8-27B를 하나씩 서빙하고 적재 Job이 Hugging Face의 체크포인트를 Amazon S3 버킷에 올리면 서빙 파드가 EKS Pod Identity 권한으로 그 버킷에서 가중치와 compile 캐시를 읽으며 컨테이너 이미지는 노드가 뜰 때 미리 받는 전체 구성도](images/2026-11-15-eks-vllm-two-models-part1-fig01-series-architecture.png)

*그림 1. 시리즈에서 다루는 전체 구성. 요청 경로는 간략히 표시했고 가중치와 compile 캐시, 컨테이너 이미지가 GPU 노드에 올라가는 경로를 자세히 그렸습니다. 게이트웨이와 앱 계층의 구성 요소는 3부에서 다룹니다.*

요청은 Amazon CloudFront와 내부 ALB(Application Load Balancer)를 지나 BFF(Backend for Frontend)에 도착합니다. BFF는 같은 클러스터의 파드이고 게이트웨이를 클러스터 안의 Service로 호출합니다. 게이트웨이는 요청을 모델에 맞는 vLLM 파드로 넘깁니다. 이 경로는 3부에서 다루고 이 글은 모델과 이미지가 GPU 노드에 올라가는 쪽을 다룹니다.

서빙 파드는 Hugging Face에서 가중치를 내려받지 않습니다. 적재 Job이 체크포인트를 Amazon Simple Storage Service(Amazon S3) 버킷에 한 번 올리고 서빙 파드는 그 버킷의 `models/`와 `vllm-cache/`만 읽습니다. 권한은 EKS Pod Identity로 주고 버킷까지의 트래픽은 VPC의 S3 게이트웨이 엔드포인트를 지납니다.

### 1.2 버전 조합

모든 구성 요소는 2026년 11월 14일 기준 최신 버전을 사용하되 서로의 지원 범위 안에서 맞췄습니다.

| 구성 요소 | 버전 | 맞춘 근거 |
|---|---|---|
| Amazon EKS | 1.37 | 서울 리전의 최신이자 기본 버전 |
| GPU 노드 AMI | EKS 최적화 AL2023 NVIDIA 1.37.1-20261107 (NVIDIA 드라이버 580.178.04) | amazon-eks-ami v20261107 릴리스 |
| Karpenter | v1.15.2 | 호환표에서 Kubernetes 1.37은 Karpenter 1.15 계열 |
| EKS Pod Identity Agent | v1.4.1-eksbuild.3 | Kubernetes 1.37 기준 애드온의 최신 버전 |
| NVIDIA device plugin | v0.20.1 | 정적 매니페스트를 사용 |
| vLLM | v0.33.0 (`vllm/vllm-openai:v0.33.0`, linux/amd64 9.74GB) | 이미지가 CUDA 13.0.2 기반이고 대응 드라이버 브랜치가 R580 |
| Mountpoint for Amazon S3 CSI 드라이버 | v2.9.2-eksbuild.1 | 기준 구성의 측정에만 사용 |

*표 1. 이 글에서 다루는 구성 요소의 버전(2026년 11월 14일 확인).*

vLLM 이미지와 GPU 드라이버의 조합은 따로 확인했습니다. EKS 사용 설명서에 따르면 CUDA 13 이상에는 NVIDIA 580 드라이버가 필요합니다. EKS 최적화 AL2023 NVIDIA AMI는 노드의 GPU에 맞는 드라이버를 첫 부팅 때 고릅니다. L40S 노드에는 580.178.04가 올라왔습니다.

g6e.4xlarge의 사양은 vCPU 16개, 메모리 128GiB, L40S 한 장, 인스턴스 스토어 600GB입니다. GPU 메모리는 제품 페이지 표기로 48GB이고 `describe-instance-types`의 값은 45,776MiB(44.7GiB)입니다. 조회 시점에 이 인스턴스는 서울 리전의 가용 영역 네 곳 가운데 ap-northeast-2a와 ap-northeast-2b에서만 제공됐습니다.

### 1.3 네 구간과 두 가지 구성

파드 생성에서 Ready까지의 시간은 네 구간과 나머지(기타)로 나눕니다. 구간마다 기다리는 대상이 다르므로 줄이는 방법도 다릅니다.

![파드 생성에서 Ready까지를 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화의 네 구간으로 나누고 구간마다 측정 근거와 기준 구성, 최적화 구성의 동작을 나란히 적은 단계 그림. 이미지 pull은 노드의 사전 pull로, 가중치 로드는 runai_streamer로, 엔진 초기화는 S3에서 복원한 compile 캐시로 줄인다](images/2026-11-15-eks-vllm-two-models-part1-fig02-cold-start-stages.png)

*그림 2. 콜드 스타트의 네 구간과 구간별 측정 근거, 두 구성의 차이. 웜 재시작에서는 노드와 이미지가 이미 있으므로 가중치 로드와 엔진 초기화, 기타만 남습니다.*

기준 구성은 최적화를 적용하기 전의 구성입니다. 모델 버킷을 Mountpoint for Amazon S3로 마운트해 vLLM 기본 로더로 읽고 compile 캐시를 컨테이너 안에 둡니다. 노드는 이미지를 미리 받지 않습니다. 최적화 구성은 지금 서빙에 사용하는 구성입니다.

| 구간 | 기준 구성 | 최적화 구성 |
|---|---|---|
| 노드 프로비저닝 | Karpenter가 g6e.4xlarge On-Demand 노드를 만듦 | 같음 |
| 이미지 pull | 파드가 스케줄된 뒤 kubelet이 받기 시작 | 노드가 뜨는 동안 사용자 데이터의 유닛이 먼저 받기 시작 |
| 가중치 로드 | Mountpoint for Amazon S3로 마운트한 경로를 vLLM 기본 로더로 읽음 | `s3://` 경로를 runai_streamer로 읽어 GPU 메모리로 스트리밍 |
| 엔진 초기화 | compile 캐시가 컨테이너 안에 생기고 파드와 함께 사라짐 | S3의 compile 캐시를 initContainer가 노드의 hostPath로 복원 |

*표 2. 구간별로 본 기준 구성과 최적화 구성의 차이. 모델, vLLM 버전, 로더를 뺀 엔진 플래그는 두 구성이 같습니다.*

노드 프로비저닝은 두 구성이 같으므로 줄일 대상은 나머지 세 구간입니다. 이미지 pull은 노드 설정에서, 가중치 로드는 로더에서, 엔진 초기화는 캐시에서 줄입니다. 아래에서 이 순서로 구성을 설명하고 마지막에 구간별 측정 결과를 봅니다.

## 2. Karpenter로 만드는 GPU 노드

### 2.1 모델마다 한 대로 묶는 NodePool

NodePool은 모델마다 하나씩 두었습니다(`gemma-od`, `qwen-od`, `decider`). 아래는 Gemma용입니다. Qwen용은 이름만 다르고 Decider용은 인스턴스 유형과 EC2NodeClass가 다릅니다.

```yaml
apiVersion: karpenter.sh/v1
kind: NodePool
metadata:
  name: gemma-od
spec:
  template:
    spec:
      nodeClassRef:
        group: karpenter.k8s.aws
        kind: EC2NodeClass
        name: vllm
      requirements:
        - key: node.kubernetes.io/instance-type
          operator: In
          values: ["g6e.4xlarge"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["on-demand"]
      taints:
        - key: nvidia.com/gpu
          value: "true"
          effect: NoSchedule
  limits:
    nvidia.com/gpu: 1
  disruption:
    consolidationPolicy: WhenEmpty
    consolidateAfter: 30m
```

`limits`의 `nvidia.com/gpu: 1`은 이 NodePool이 만드는 GPU를 한 장으로 묶습니다. Karpenter 문서에 따르면 한도를 넘은 NodePool은 노드가 종료될 때까지 새 노드를 만들지 않습니다. 복제본 수를 실수로 올려도 GPU 노드가 의도와 다르게 늘지 않게 하려는 값입니다.

`taints`를 두면 이 taint를 허용하지 않는 파드는 GPU 노드에 스케줄되지 않습니다. vLLM 파드는 같은 키의 toleration과 `karpenter.sh/nodepool` nodeSelector로 자기 NodePool을 고릅니다. 가용 영역 조건은 두지 않아 Karpenter가 용량이 있는 영역을 고릅니다. g6e.4xlarge가 실제로 뜰 수 있는 곳은 앞에서 본 두 영역입니다.

`consolidationPolicy: WhenEmpty`는 워크로드 파드가 없는 노드만 회수 대상으로 삼습니다. `consolidateAfter`를 30분으로 둔 데에는 측정 사정이 들어 있습니다. 웜 재시작을 재려면 파드를 지우고 다시 만드는 사이에 노드가 남아 있어야 합니다. 반대로 회수를 아예 끄면 작업을 잊었을 때 GPU 노드가 계속 남습니다.

### 2.2 인스턴스 스토어와 이미지 사전 pull

Gemma와 Qwen의 노드는 EC2NodeClass `vllm`을 사용합니다. 저장소의 매니페스트에서 주석만 뺀 것입니다.

```yaml
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: vllm
spec:
  role: KarpenterNodeRole-ow-on-gpu
  amiSelectorTerms:
    - alias: al2023@v20261107
  subnetSelectorTerms:
    - tags:
        karpenter.sh/discovery: ow-on-gpu
  securityGroupSelectorTerms:
    - tags:
        karpenter.sh/discovery: ow-on-gpu
  instanceStorePolicy: RAID0
  userData: |
    MIME-Version: 1.0
    Content-Type: multipart/mixed; boundary="BOUNDARY"

    --BOUNDARY
    Content-Type: text/x-shellscript; charset="us-ascii"

    #!/bin/bash
    systemd-run --unit=prepull-vllm --no-block /bin/bash -c '
      until ctr --namespace k8s.io version >/dev/null 2>&1; do sleep 1; done
      ctr --namespace k8s.io images pull docker.io/vllm/vllm-openai:v0.33.0
    '
    --BOUNDARY--
```

`amiSelectorTerms`의 별칭은 EKS 최적화 AL2023 AMI의 릴리스를 고정합니다. 별칭을 사용하면 Karpenter가 인스턴스에 맞는 변형을 고르므로 GPU 노드에는 NVIDIA 변형 AMI가 올라옵니다. 이 AMI에는 NVIDIA 드라이버와 container toolkit이 들어 있고 NVIDIA device plugin은 들어 있지 않습니다. 그래서 device plugin v0.20.1의 정적 매니페스트를 설치했고 nodeSelector를 더해 NVIDIA GPU 노드에만 뜨게 했습니다.

`instanceStorePolicy: RAID0`은 인스턴스 스토어를 RAID0으로 묶어 kubelet과 containerd의 저장 공간으로 사용하게 합니다. AL2023에서는 Karpenter가 만든 NodeConfig가 디스크를 구성하고 `/mnt/k8s-disks/0`에 마운트합니다. GPU 노드에서는 559GB가 그 경로에 마운트됐고 컨테이너 이미지가 여기에 저장됐습니다. 루트 볼륨은 20GB입니다.

`userData`의 스크립트가 이미지 사전 pull을 맡습니다. 사용자 스크립트는 containerd가 뜨기 전에 실행될 수 있습니다. 그래서 containerd를 기다렸다가 이미지를 받는 일회성 systemd 유닛으로 일을 넘겼습니다. 유닛은 노드 등록을 막지 않고 kubelet과 나란히 진행되며 kubelet이 보는 `k8s.io` 네임스페이스에 이미지를 받습니다.

처음 만든 GPU 노드에서 이 동작을 확인했습니다. 사전 pull은 containerd가 뜬 직후에 시작해 9.1GiB를 108.7초에 받았습니다(85.5MiB/s). kubelet의 pull은 진행 중인 다운로드를 이어받아 사전 pull이 끝난 1초 뒤에 끝났고 kubelet이 기록한 pull 시간은 45.0초였습니다. 사전 pull은 이미지를 받는 시간을 줄이지 않습니다. 받기 시작하는 시점을 파드 스케줄 뒤에서 노드 부팅 중으로 당깁니다.

### 2.3 EKS Pod Identity로 주는 S3 권한

서빙 파드와 Job이 S3에 접근하는 권한은 EKS Pod Identity로 줍니다. EKS Pod Identity는 AWS Identity and Access Management(IAM) 역할을 네임스페이스의 ServiceAccount에 연결하는 기능이고 OIDC 자격 증명 공급자가 필요 없습니다. 노드마다 DaemonSet으로 실행되는 Pod Identity Agent가 같은 노드의 파드에 임시 자격 증명을 전달합니다. 아래는 Terraform 정의에서 신뢰 정책과 읽기 전용 쪽만 옮긴 것입니다.

```hcl
# karpenter.tf (발췌)
locals {
  pod_identity_trust = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

# storage.tf (발췌)
locals {
  model_object_arns = [
    "${aws_s3_bucket.models.arn}/models/*",
    "${aws_s3_bucket.models.arn}/vllm-cache/*",
  ]

  model_reader_service_accounts = ["gemma", "qwen", "decider"]
  model_writer_service_accounts = ["model-sync", "cache-publish"]
}

resource "aws_iam_role" "model_reader" {
  name               = "${var.cluster_name}-model-reader"
  assume_role_policy = local.pod_identity_trust
}

resource "aws_eks_pod_identity_association" "model_reader" {
  for_each = toset(local.model_reader_service_accounts)

  cluster_name    = aws_eks_cluster.this.name
  namespace       = "inference"
  service_account = each.key
  role_arn        = aws_iam_role.model_reader.arn
}
```

역할은 둘로 나눴습니다. 읽기 역할은 `models/`와 `vllm-cache/`의 `s3:GetObject`와 버킷 목록 조회만 허용합니다. 이 역할을 `inference` 네임스페이스의 서빙 파드용 ServiceAccount 세 개(`gemma`, `qwen`, `decider`)에 연결했습니다. 쓰기 역할은 `model-jobs` 네임스페이스의 적재 Job과 캐시 게시 Job에만 연결했습니다. 서빙 파드는 버킷에 아무것도 올리지 못합니다.

자격 증명을 받는 쪽에서는 두 가지를 손봤습니다. Run:ai Model Streamer의 S3 클라이언트는 기본값에서 AWS C++ SDK의 자격 증명 공급자 체인을 사용하고 boto3 세션을 만들지 않습니다. 그래서 `RUNAI_STREAMER_NO_BOTO3_SESSION=0`으로 boto3가 받은 자격 증명을 넘기게 했습니다. vLLM 이미지 안의 boto3가 Pod Identity로 자격 증명을 받아 버킷을 나열하는 것은 배포 전에 확인했습니다. 기본값으로 두었을 때의 동작은 따로 기록하지 않았습니다. 적재 Job이 사용하는 s5cmd 2.3.0은 AWS SDK가 Pod Identity를 지원하지 않습니다. 이 경우에는 스크립트가 Pod Identity Agent에서 임시 자격 증명을 받아 s5cmd에 넘깁니다.

## 3. 체크포인트 선택과 S3 적재

### 3.1 L40S에서 FP8 체크포인트를 고른 이유

L40S는 Ada 세대 GPU이고 compute capability가 8.9입니다. vLLM 문서의 양자화 지원표에서 llm-compressor FP8(W8A8)은 Ada(SM 8.9)와 Hopper(SM 9.0)에서 지원됩니다. 두 모델 모두 이 형식의 FP8-dynamic 체크포인트를 사용했습니다. 가중치는 채널별 정적 FP8이고 활성값은 토큰별 동적 FP8입니다.

| 모델 | 체크포인트 (리비전) | 가중치 파일 | GPU에 올라간 크기 |
|---|---|---|---|
| Gemma 4 31B | RedHatAI/gemma-4-31B-it-FP8-dynamic (`d4ab4f57`) | safetensors 2개, 33.27GB | 30.63GiB |
| Qwen3.8-27B | AzatAI/Qwen3.8-27B-FP8-dynamic (`10c68ff4`) | safetensors 3개, 36.78GB (MTP 헤드 0.85GB 포함) | 34.39GiB |

*표 3. 두 모델의 체크포인트. 파일 크기는 1GB = 10^9바이트 기준이고 GPU에 올라간 크기는 vLLM 로그의 `Model loading took` 값입니다.*

Qwen3.8-27B에는 FP8 체크포인트가 두 가지 있습니다. 공식 저장소(Qwen/Qwen3.8-27B-FP8)는 블록 크기 128로 양자화한 block FP8이고 가중치가 30.87GB로 5.9GB 작습니다. 다만 vLLM v0.33.0 소스에서 CUTLASS block FP8 커널은 compute capability 9.0 이상에서만 지원됩니다. 같은 Ada 세대인 RTX 6000 Ada에서 이 체크포인트가 Marlin FP8 커널로 내려갔다는 보고가 vLLM 이슈에 있습니다. L40S에서 실제로 어떤 커널을 고르는지와 성능 차이는 확인하지 못했습니다.

그래서 문서가 Ada 지원을 명시한 per-channel 체크포인트를 골랐습니다. 두 모델 모두 기동 로그에서 `CutlassFP8ScaledMMLinearKernel`이 선택됐습니다. 대가는 GPU 메모리입니다. 가중치가 큰 만큼 KV 캐시(Key-Value cache)에 남는 메모리가 줄어들고 이 차이는 뒤에서 설명할 `--gpu-memory-utilization` 설정에서 다시 나옵니다.

AzatAI 저장소는 개인 조직이 올린 것이어서 적재할 때 리비전 해시로 고정했습니다. 파일은 safetensors뿐이라 pickle 실행 위험은 없습니다.

### 3.2 Hugging Face에서 S3로 올리는 적재 Job

적재 Job은 리비전 해시로 고정한 저장소 네 개를 버킷의 `models/` 아래에 올립니다. Decider의 저장소에는 LoRA 어댑터와 헤드만 있어서 기반 모델(Qwen/Qwen3.5-2B-Base)을 함께 올렸습니다. compile 캐시까지 더한 버킷의 구조입니다.

```
s3://<bucket>/models/gemma-4-31B-it-FP8-dynamic/
s3://<bucket>/models/Qwen3.8-27B-FP8-dynamic/
s3://<bucket>/models/strands-decider-2B-qwen3.5-v1-2610/
s3://<bucket>/models/Qwen3.5-2B-Base/
s3://<bucket>/vllm-cache/v0.33.0-gemma4-31b-fp8-l40s/
s3://<bucket>/vllm-cache/v0.33.0-qwen38-27b-fp8-l40s/
```

Job은 파일을 받는 대로 `s5cmd pipe`로 S3에 올리므로 가중치를 로컬 디스크에 쌓지 않습니다. 파일 8개를 동시에 처리하고 파일마다 64MiB 파트 4개를 병렬로 올립니다. 받으면서 해시를 계산해 Hugging Face가 알려 준 값과 비교합니다(LFS 파일은 sha256, 나머지는 git blob sha1). 끝나면 S3의 객체 목록을 기대값과 비교하고 경로나 크기가 다르면 Job이 실패합니다. 다시 실행하면 같은 크기로 이미 올라간 파일은 건너뜁니다. Job은 CPU 노드(`system` NodePool)에서 실행됩니다.

| 저장소 | 객체 수 | 크기 |
|---|---:|---:|
| RedHatAI/gemma-4-31B-it-FP8-dynamic | 18 | 33.30GB |
| AzatAI/Qwen3.8-27B-FP8-dynamic | 14 | 36.80GB |
| StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 | 29 | 0.23GB |
| Qwen/Qwen3.5-2B-Base | 12 | 4.57GB |
| 합계 | 73 | 74.90GB |

*표 4. 적재 Job이 올린 저장소(2026년 11월 14일). 1GB = 10^9바이트.*

Job은 시작부터 완료까지 9분 8초가 걸렸고 그중 전송과 검증이 491.4초였습니다. 재시도는 없었습니다. 전체 시간을 정한 것은 Qwen의 19.98GB 파일로, 40.7MB/s로 490초가 걸렸습니다. Gemma의 26.89GB 파일은 213.4MB/s로 126초 만에 끝났습니다. 내려받는 속도는 저장소에 따라 다섯 배쯤 달랐습니다. 적재 뒤에 S3 객체 세 개를 다시 받아 sha256을 Hugging Face의 값과 대조했고 모두 일치했습니다.

## 4. vLLM 배포

Gemma의 Deployment에서 시작 시간과 관련된 부분만 옮겼습니다. ServiceAccount, 리소스 요청, readinessProbe와 livenessProbe, 일부 환경 변수와 볼륨은 줄였습니다.

```yaml
    spec:
      serviceAccountName: gemma
      nodeSelector:
        karpenter.sh/nodepool: gemma-od
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      initContainers:
        - name: cache-restore
          image: vllm/vllm-openai:v0.33.0
          command: ["python3", "/scripts/cache-restore.py"]
          env:
            - name: CACHE_PREFIX
              value: vllm-cache/v0.33.0-gemma4-31b-fp8-l40s
          volumeMounts:
            - name: vllm-cache
              mountPath: /vllm-cache
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.33.0
          args:
            - s3://$(MODEL_BUCKET)/models/gemma-4-31B-it-FP8-dynamic
            - --served-model-name=gemma-4-31b
            - --load-format=runai_streamer
            - --language-model-only
            - --max-model-len=16384
            - --kv-cache-dtype=fp8
            - --gpu-memory-utilization=0.90
            - --enable-prefix-caching
            - --scheduling-policy=priority
            - --enable-auto-tool-choice
            - --tool-call-parser=gemma4
            - --reasoning-parser=gemma4
          env:
            - name: MODEL_BUCKET
              valueFrom:
                configMapKeyRef: {name: platform, key: MODEL_BUCKET}
            - name: VLLM_CACHE_ROOT
              value: /vllm-cache
            - name: RUNAI_STREAMER_NO_BOTO3_SESSION
              value: "0"
            - name: HF_HUB_OFFLINE
              value: "1"
          startupProbe:
            httpGet: {path: /health, port: http}
            periodSeconds: 1
            failureThreshold: 1800
          volumeMounts:
            - name: vllm-cache
              mountPath: /vllm-cache
      volumes:
        - name: vllm-cache
          hostPath:
            path: /var/cache/vllm
            type: DirectoryOrCreate
```

### 4.1 runai_streamer로 S3에서 직접 읽는 가중치

vLLM 문서에 따르면 Run:ai Model Streamer는 텐서를 동시에 읽으면서 GPU 메모리로 스트리밍하는 라이브러리입니다. `--load-format=runai_streamer`를 주고 모델 인자에 `s3://` 경로를 적으면 safetensors 파일을 S3에서 바로 읽습니다. 가중치를 노드의 디스크에 먼저 내려받는 단계가 없고 설정과 토크나이저 파일만 로컬 캐시로 받습니다. 이미지에는 runai-model-streamer 0.17.1이 들어 있었습니다.

`HF_HUB_OFFLINE=1`은 서빙 파드가 Hugging Face에서 내려받으려 하면 실패하게 만듭니다. 설정이 틀렸을 때 조용히 외부에서 받아 오는 일을 막으려는 값입니다.

로더의 동시성과 청크 크기는 기본값으로 두었습니다. EKS 사용 설명서에는 모델 크기에 맞춰 `--model-loader-extra-config`의 `concurrency`와 `RUNAI_STREAMER_CHUNK_BYTESIZE`를 조정하는 방법이 있습니다. 조정했을 때의 값은 재지 않았습니다.

### 4.2 compile 캐시의 게시와 복원

vLLM은 요청을 받기 전에 모든 컴파일을 끝냅니다. 그래서 `torch.compile`에 걸리는 시간은 그대로 시작 시간에 들어갑니다. 컴파일 결과는 캐시 루트 아래 `torch_compile_cache/`에 저장됩니다. vLLM 문서에 따르면 이 디렉터리를 통째로 배포 환경에 복사해 컴파일 시간을 줄일 수 있습니다. 이 방법을 따라 캐시를 두 곳에 두었습니다.

노드에는 hostPath(`/var/cache/vllm`)를 두고 `VLLM_CACHE_ROOT`로 vLLM이 그 경로에 캐시를 저장하게 했습니다. 파드가 다시 떠도 노드가 같으면 캐시가 남습니다. EKS 사용 설명서는 이 hostPath를 인스턴스 스토어의 마운트 지점 아래에 두는 것을 권장합니다. 이 환경은 위 경로를 사용했고 경로에 따른 차이는 재지 않았습니다.

S3에는 새 노드를 위한 사본을 둡니다. 모델이 한 번 기동해 캐시가 생기면 캐시 게시 Job이 노드의 캐시 디렉터리를 S3 prefix로 올립니다. Job은 podAffinity로 vLLM 파드와 같은 노드에 스케줄되고 GPU를 요청하지 않습니다. 이미지는 노드에 이미 있는 vLLM 이미지를 사용합니다. 새 노드에서는 vLLM 파드의 initContainer(초기화 컨테이너) `cache-restore`가 그 prefix를 hostPath로 내려받습니다. 같은 크기로 이미 있는 파일은 건너뛰고 prefix가 비어 있으면 아무것도 하지 않고 끝납니다.

| 모델 | S3 prefix | 객체 수 | 크기 | 새 노드에서 복원한 시간 |
|---|---|---:|---:|---:|
| Gemma 4 31B | `vllm-cache/v0.33.0-gemma4-31b-fp8-l40s/` | 522 | 90.8MB | 3.3초 |
| Qwen3.8-27B | `vllm-cache/v0.33.0-qwen38-27b-fp8-l40s/` | 2,056 | 216.7MB | 10초 |

*표 5. S3에 게시한 compile 캐시와 콜드 스타트 측정에서 initContainer가 복원한 시간.*

prefix 이름에는 vLLM 버전, 모델, 정밀도, GPU를 넣었습니다. vLLM은 관련 설정과 PyTorch 설정, 모델의 forward 코드로 캐시 디렉터리를 정하므로 이 가운데 하나가 바뀌면 캐시가 맞지 않습니다. 2026년 11월 15일에 Qwen의 prefix caching을 끈 구성을 띄웠을 때가 그 경우였고 compile에 62.6초가 걸렸습니다. EKS 사용 설명서에 따르면 GPU 유형, 모델, PyTorch 버전이 다른 캐시는 구분해 저장해야 합니다. 구성을 바꾸면 새 prefix로 다시 게시합니다.

### 4.3 gpu-memory-utilization과 KV 캐시

`--gpu-memory-utilization`은 vLLM이 GPU 메모리의 얼마까지를 사용할지 정합니다. 가중치와 추론 중의 활성값이 차지하는 몫을 빼고 남은 메모리가 KV 캐시가 되므로 가중치가 큰 체크포인트일수록 이 값에 민감합니다.

| 항목 | Gemma 4 31B | Qwen3.8-27B |
|---|---:|---:|
| `--gpu-memory-utilization` | 0.90 | 0.90 |
| 목표 메모리 (전체 44.39GiB 기준) | 39.95GiB | 39.95GiB |
| 가중치와 비 torch 메모리 | 31.13GiB | 34.74GiB |
| 활성값 최대 | 3.45GiB | 2.76GiB |
| CUDA graph | 0.35GiB | 0.58GiB |
| KV 캐시 메모리 | 5.37GiB | 2.46GiB |
| KV 캐시 크기 | 34,052 토큰 | 42,780 토큰 |
| `--max-model-len` 길이 요청으로 환산 | 2.08개 (16,384 토큰) | 1.31개 (32,768 토큰) |

*표 6. 기동 로그에 기록된 GPU 메모리 배분(2026년 11월 14일 첫 기동, 한 번).*

Gemma는 0.90으로 첫 시도에 시작됐습니다. Qwen은 처음 값인 0.85로는 엔진이 시작하지 못했습니다. 가중치가 34.39GiB를 차지해 KV 캐시에 0.24GiB만 남았습니다. vLLM은 최대 길이(32,768 토큰) 요청 하나에 KV 캐시 1.87GiB가 필요하다는 오류를 냈습니다. 남은 메모리가 이 정도면 `--max-model-len`을 줄여서는 해결되지 않습니다. 0.90으로 올리자 sleep mode를 켠 채로 시작됐고 KV 캐시 2.46GiB를 얻었습니다.

두 모델 모두 KV 캐시가 작습니다. 이 크기가 동시에 처리하는 요청 수와 처리량을 어떻게 정하는지는 2부(TODO: Part 2 링크)에서 다룹니다.

### 4.4 그 밖의 플래그와 프로브

엔진 플래그는 시작 시간보다 서빙 동작을 정하지만 시작 실패의 원인이 되는 것이 있어 함께 적습니다.

| 설정 | 적용 대상 | 이유 |
|---|---|---|
| `--language-model-only` | Gemma | 멀티모달 입력 한도를 0으로 두고 언어 모델만 사용. 체크포인트 카드의 평가 재현 명령에도 있는 플래그 |
| `--max-num-seqs=32` | Qwen | 하이브리드 모델은 이 값이 Mamba 캐시 블록 수보다 크면 엔진이 시작하지 못함 |
| `--kv-cache-dtype=fp8` | 둘 다 | KV 캐시를 FP8로 저장해 GPU 메모리 사용을 줄임 |
| `--scheduling-policy=priority` | 둘 다 | 요청 본문의 `priority`로 처리 순서를 정함(3부) |
| `--speculative-config` (MTP, 추측 토큰 3개) | Qwen | 모델의 MTP 헤드로 speculative decoding(2부) |
| `--enable-sleep-mode`, `VLLM_SERVER_DEV_MODE=1` | Qwen | `/sleep`, `/wake_up`, `/is_sleeping` 엔드포인트를 등록(3부) |
| `startupProbe` 주기 1초, 실패 허용 1,800회 | 둘 다 | Ready 시각을 1초 단위로 잡고 최대 30분을 기다림 |
| `progressDeadlineSeconds: 1800` | 둘 다 | 기본값 600초는 콜드 스타트보다 짧을 수 있음 |
| `strategy: Recreate` | 둘 다 | GPU 한 장을 파드 하나가 사용하므로 기존 파드를 먼저 내림 |

*표 7. 시작 시간이나 시작 성공 여부에 영향을 주는 설정. 괄호 안은 그 동작을 다루는 편입니다.*

Qwen의 readinessProbe는 `/health`가 아닌 `/is_sleeping`을 확인합니다. `/health`는 sleep 중에도 200을 돌려주므로 잠든 파드가 트래픽을 받지 않게 하려면 sleep 상태를 직접 봐야 합니다.

## 5. 콜드 스타트 구간 분해 결과

### 5.1 측정 방법

측정 스크립트는 시나리오의 시작 상태를 만든 뒤 새 파드가 Ready가 될 때까지 기다리고 Kubernetes 객체의 시각과 vLLM 로그에서 구간을 뽑습니다. 콜드 시나리오는 서빙을 0으로 줄이고 그 모델의 GPU 노드를 지운 뒤 다시 1로 올립니다. 웜 재시작 시나리오는 같은 노드에서 파드만 지워 다시 만들게 합니다.

| 구간 | 근거 |
|---|---|
| 전체 | 파드 생성 시각부터 파드의 Ready 전환 시각까지 |
| 노드 프로비저닝 | NodeClaim 생성 시각부터 노드의 Ready 전환 시각까지 |
| 이미지 pull | kubelet의 `Pulled` 이벤트에 적힌 시간. 이미지가 이미 있으면 0 |
| 가중치 로드 | vLLM 로그의 `Model loading took` |
| 엔진 초기화 | vLLM 로그의 `init engine (profile, create kv cache, warmup model) took` |
| 기타 | 전체에서 위 네 구간을 뺀 값 |

*표 8. 구간별 측정 근거. Kubernetes의 시각은 1초 단위여서 전체 시간과 노드 프로비저닝에는 최대 1초의 오차가 있습니다.*

기준 구성의 Mountpoint 볼륨은 `max-threads 96`과 `maximum-throughput-gbps 20`(g6e.4xlarge의 네트워크 대역폭)으로 마운트했습니다. 이미지 사전 pull이 없는 조건은 EC2NodeClass만 다른 별도 NodePool로 만들었습니다.

가중치 로드의 표식은 `Model loading took`으로 통일했습니다. v0.33.0은 스트리밍 로더 경로에서 `Loading weights took`을 남기지 않기 때문입니다. 기준 구성에는 두 줄이 모두 있고 값은 55.9초와 59.6초였습니다.

### 5.2 시나리오별 전체 시간

Qwen3.8-27B의 기준 구성은 재지 않았습니다.

| 시나리오 | Gemma 4 31B | Qwen3.8-27B |
|---|---:|---:|
| 콜드, 기준 구성 | 394초 | 재지 않음 |
| 콜드, 최적화 구성 | 260초 | 290초 |
| 웜 재시작, 기준 구성 | 214초 | 재지 않음 |
| 웜 재시작, 최적화 구성 | 86초 | 123초 |

*표 9. 파드 생성에서 Ready까지의 시간(g6e.4xlarge, vLLM v0.33.0, 2026년 11월 14일 서울 리전, 시나리오마다 한 번).*

![Gemma 4 31B의 파드 생성에서 Ready까지의 시간은 콜드 스타트가 기준 구성 394초에서 최적화 구성 260초로, 웜 재시작이 214초에서 86초로 줄었고 Qwen3.8-27B는 최적화 구성만 재서 콜드 스타트 290초, 웜 재시작 123초였음을 보여 주는 막대 그래프](images/2026-11-15-eks-vllm-two-models-part1-fig03-scenario-totals.png)

*그림 3. 시나리오별 파드 생성에서 Ready까지의 시간(초). Qwen3.8-27B는 최적화 구성만 쟀습니다.*

Gemma의 콜드 스타트는 134초(34%), 웜 재시작은 128초(60%) 줄었습니다. 줄어든 시간은 비슷하고 웜 재시작에는 노드 프로비저닝과 이미지 pull이 없어서 비율이 더 큽니다.

### 5.3 Gemma 4 31B의 구간별 결과

웜 재시작에서는 노드와 이미지가 이미 있으므로 앞의 두 구간이 0입니다.

| 구간 | 콜드, 기준 | 콜드, 최적화 | 웜 재시작, 기준 | 웜 재시작, 최적화 |
|---|---:|---:|---:|---:|
| 노드 프로비저닝 | 55.0 | 71.0 | 0 | 0 |
| 이미지 pull | 111.1 | 71.0 | 0 | 0 |
| 가중치 로드 | 59.6 | 19.2 | 59.1 | 19.6 |
| 엔진 초기화 | 95.5 | 23.7 | 95.6 | 23.7 |
| (그중 torch.compile) | 61.0 | 0.9 | 60.8 | 0.9 |
| 기타 | 72.7 | 75.1 | 59.3 | 42.7 |
| 합계 | 394 | 260 | 214 | 86 |

*표 10. Gemma 4 31B의 구간별 시간(초, 시나리오마다 한 번). 합계는 1초 단위로 잰 전체 시간이고 torch.compile은 엔진 초기화에 포함된 값입니다.*

![Gemma 4 31B 콜드 스타트의 구간별 시간을 기준 구성과 최적화 구성으로 견준 막대 그래프. 노드 프로비저닝 55.0초와 71.0초, 이미지 pull 111.1초와 71.0초, 가중치 로드 59.6초와 19.2초, 엔진 초기화 95.5초와 23.7초, 기타 72.7초와 75.1초로, 줄어든 구간은 이미지 pull과 가중치 로드, 엔진 초기화다](images/2026-11-15-eks-vllm-two-models-part1-fig04-cold-start-segments.png)

*그림 4. Gemma 4 31B 콜드 스타트의 구간별 시간(초). 기준 구성 합계 394초, 최적화 구성 합계 260초.*

가중치 로드는 Mountpoint로 읽으면 59.6초, 스트리밍 로더로 읽으면 19.2초였습니다(3.1배). 웜 재시작에서도 59.1초와 19.6초여서 이 구간은 노드가 새것인지와 무관했습니다.

엔진 초기화는 95.5초에서 23.7초가 됐고 차이의 대부분은 `torch.compile`입니다(61.0초에서 0.9초). 새 노드에서 initContainer가 S3의 캐시 522개를 3.3초에 복원했고 캐시가 적중했습니다. 남은 23.7초에는 CUDA graph 캡처가 들어 있습니다. 로그에 기록된 캡처 시간은 7초와 10초였습니다.

이미지 pull은 kubelet 기준으로 111.1초에서 71.0초가 됐습니다. 사전 pull이 노드가 뜨는 동안 먼저 시작하므로 kubelet이 기다린 시간이 줄었습니다. 그래도 71.0초는 기타를 빼면 최적화 구성에서 노드 프로비저닝과 함께 가장 긴 구간입니다.

노드 프로비저닝은 55.0초와 71.0초였습니다. 두 구성의 EC2NodeClass에서 다른 것은 사용자 데이터의 사전 pull 유닛뿐입니다. 한 번씩 잰 값이라 16초의 차이가 사전 pull의 영향인지 그날의 편차인지는 가르지 못합니다. 같은 날 처음 만든 GPU 노드는 118초가 걸렸습니다. 이 구간을 뺀 나머지만 보면 339초에서 189초로 44% 줄었습니다.

기타는 콜드 스타트에서 줄지 않았습니다(72.7초와 75.1초). 여기에는 스케줄링 대기, 컨테이너 생성, vLLM 프로세스가 가중치 로드에 들어가기 전의 시간, 엔진 초기화 뒤 API 서버가 뜨는 시간이 들어갑니다. 웜 재시작에서는 59.3초에서 42.7초로 줄었는데 어느 단계가 줄었는지는 나눠 보지 못했습니다.

Gemma의 최적화 구성에서는 기타가 가장 긴 구간입니다. 웜 재시작 최적화 구성에서 컨테이너 시작부터 Ready까지는 82초였고 그중 가중치 로드와 엔진 초기화가 43.3초였습니다. 나머지 39초쯤은 두 표식 바깥의 시간이어서 기타가 86초의 절반을 차지합니다.

### 5.4 Qwen3.8-27B의 구간별 결과

Qwen3.8-27B는 최적화 구성의 두 시나리오만 쟀습니다.

| 구간 | 콜드, 최적화 | 웜 재시작, 최적화 |
|---|---:|---:|
| 노드 프로비저닝 | 63.0 | 0 |
| 이미지 pull | 77.5 | 0 |
| 가중치 로드 | 34.9 | 35.4 |
| 엔진 초기화 | 42.5 | 41.8 |
| (그중 torch.compile) | 0.8 | 0.9 |
| 기타 | 72.1 | 45.8 |
| 합계 | 290 | 123 |

*표 11. Qwen3.8-27B의 구간별 시간(초, 최적화 구성, 시나리오마다 한 번).*

Qwen은 가중치가 34.39GiB로 더 커서 가중치 로드가 34.9초로 Gemma의 19.2초보다 깁니다. compile 캐시는 2,056개를 복원하는 데 10초가 걸렸고 compile은 0.8초에 끝났습니다. 엔진 초기화가 Gemma보다 긴 42.5초인 이유는 따로 분석하지 않았습니다.

### 5.5 sleep 복귀와의 비교

파드를 다시 띄우지 않는 방법도 있습니다. vLLM의 level 1 sleep은 가중치를 호스트 메모리로 옮기고 KV 캐시를 버려 GPU 메모리를 비웁니다. 웜 재시작으로 새로 뜬 Qwen 파드에서 복귀를 두 번 쟀을 때 깨우기 API가 응답하기까지 3.70초와 3.67초였습니다. 같은 파드의 웜 재시작은 123초, 콜드 스타트는 290초였습니다. 다만 sleep은 노드와 파드를 그대로 두므로 노드를 회수하지는 못합니다. 진입 시간도 파드가 뜬 뒤 첫 번째는 31.71초, 두 번째는 2.98초로 달랐습니다. sleep을 일정에 맞춰 운영하는 구성은 3부(TODO: Part 3 링크)에서 다룹니다.

## 6. 확인하지 못한 것

모든 시나리오는 한 번씩 쟀습니다. 반복했을 때의 편차는 재지 않았고 특히 노드 프로비저닝은 같은 날에도 55초에서 118초까지 달랐습니다. 이 글의 값을 다른 환경의 예상치로 사용하기보다 같은 방법으로 직접 재는 것을 권고합니다.

Qwen3.8-27B의 기준 구성은 재지 않았으므로 Qwen에서 줄어든 폭은 알 수 없습니다. 기타 구간은 전체에서 네 구간을 뺀 값이라 안쪽을 더 나누지 못했습니다. 로더의 동시성 조정, hostPath의 위치, block FP8 체크포인트의 커널과 성능도 확인하지 않았습니다.

측정 조건으로 적어 둘 것도 있습니다. 콜드 시나리오마다 이전 GPU 노드를 지우는 데 6분 30초쯤 걸렸고 이 시간은 시작 시간에 넣지 않았습니다. GPU 노드에는 Amazon GuardDuty 에이전트가 함께 떠 있었고 기준 구성에서는 Mountpoint 파드가 새 노드에 함께 떴습니다. 네 시나리오 모두 컨테이너 재시작은 없었습니다.

## 7. 마치며

콜드 스타트 394초를 260초로 줄인 것은 한 가지 설정이 아닙니다. 구간을 나눠 보니 이미지 pull은 노드의 사용자 데이터에서, 가중치 로드는 로더에서, 엔진 초기화는 compile 캐시에서 따로 줄었습니다. 가중치 로드는 59.6초에서 19.2초, 엔진 초기화는 95.5초에서 23.7초, 이미지 pull은 111.1초에서 71.0초가 됐습니다. 노드 프로비저닝과 기타는 그대로 남았고 최적화 구성에서는 이 두 구간이 260초 가운데 146.1초입니다.

같은 방법을 적용하려면 먼저 구간별로 재는 것을 권고합니다. NodeClaim과 파드의 시각, kubelet의 `Pulled` 이벤트, vLLM 로그의 두 줄이면 네 구간이 나오고 어느 구간이 긴지에 따라 손댈 곳이 달라집니다. 가중치를 S3에 두고 있다면 스트리밍 로더와 Pod Identity를, 새 노드가 자주 뜬다면 compile 캐시의 S3 게시와 이미지 사전 pull을 먼저 검토할 만합니다.

2부(TODO: Part 2 링크)에서는 이렇게 띄운 두 모델이 L40S 한 장에서 동시에 몇 건을 처리하는지를 SLO 기준으로 잽니다. 이 글의 구간별 측정 방법과 표가 여러분의 GPU 서빙 환경에서 시작 시간을 검토하는 데 실질적인 참고가 되기를 바랍니다.

## 참고 자료

- [Learn how EKS Pod Identity grants pods access to AWS services – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Assign an IAM role to a Kubernetes service account – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-association.html)
- [Accelerate model loading on Amazon EKS – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-fast-model-loading.html)
- [Use EKS-optimized accelerated Linux AMIs for GPU instances – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/ml-eks-optimized-ami.html)
- [Access Amazon S3 objects with Mountpoint for Amazon S3 CSI driver – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/s3-csi.html)
- [Amazon EC2 G6e Instances – 제품 페이지](https://aws.amazon.com/ko/ec2/instance-types/g6e/)
- [NodePools – Karpenter 문서](https://karpenter.sh/docs/concepts/nodepools/)
- [NodeClasses – Karpenter 문서](https://karpenter.sh/docs/concepts/nodeclasses/)
- [Loading models with Run:ai Model Streamer – vLLM 문서](https://docs.vllm.ai/en/latest/models/extensions/runai_model_streamer/)
- [torch.compile integration – vLLM 문서](https://docs.vllm.ai/en/latest/design/torch_compile/)
- [Quantization – vLLM 문서](https://docs.vllm.ai/en/latest/features/quantization/)
- [Sleep Mode – vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)
- [scaled_mm_entry.cu (v0.33.0) – vLLM 소스](https://github.com/vllm-project/vllm/blob/v0.33.0/csrc/quantization/w8a8/cutlass/scaled_mm_entry.cu)
- [cutlass_scaled_mm_supports_block_fp8 excludes SM89 (Ada Lovelace) despite native FP8 tensor core support – vLLM 이슈 #58241](https://github.com/vllm-project/vllm/issues/58241)
- [Using Model Streamer – Run:ai Model Streamer 문서](https://github.com/dsx-ai-factory/model-streamer/blob/master/docs/src/usage.md)
- [RedHatAI/gemma-4-31B-it-FP8-dynamic – Hugging Face 모델 카드](https://huggingface.co/RedHatAI/gemma-4-31B-it-FP8-dynamic)
- [AzatAI/Qwen3.8-27B-FP8-dynamic – Hugging Face 모델 카드](https://huggingface.co/AzatAI/Qwen3.8-27B-FP8-dynamic)
- [Qwen/Qwen3.8-27B-FP8 – Hugging Face 모델 카드](https://huggingface.co/Qwen/Qwen3.8-27B-FP8)

*본문의 시간과 크기는 2026년 11월 14일(compile 캐시가 맞지 않은 사례 한 건은 11월 15일) 서울 리전의 g6e.4xlarge에서 vLLM v0.33.0으로 시나리오마다 한 번 잰 값입니다. 인스턴스 유형, 체크포인트, 버전, 측정 시점에 따라 결과는 달라질 수 있습니다.*

## 저자 소개

**최우형 (Woohyung Choi)** 님은 AWS Korea의 Principal Solutions Architect로, 국내 주요 엔터프라이즈 및 디지털 기업의 클라우드 전환과 아키텍처 현대화를 지원하고 있습니다. 특히 클라우드 네이티브 아키텍처와 Agentic AI 분야에 전문성을 가지고 있으며, 고객이 Amazon Bedrock을 비롯한 AWS의 생성형 AI 및 Agentic AI 기술을 안정적이고 비용 효율적으로 도입하고 확장할 수 있도록 아키텍처 설계와 기술 자문을 제공하고 있습니다.

컨테이너, 네트워킹, 비용 최적화를 비롯한 클라우드 핵심 기술부터 Agentic AI를 활용한 업무 혁신과 지능형 시스템 구축까지 폭넓은 영역에서 AWS 아키텍처 모범 사례를 제시하고 있습니다. 이를 통해 고객의 복잡한 기술적 과제를 해결하고, AI와 클라우드를 기반으로 지속 가능한 기술 전략을 수립하고 실행할 수 있도록 기술 리더십을 발휘하고 있습니다.
