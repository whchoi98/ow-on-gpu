---
title: "OpenWeight on AWS GPU 2부: 두 모델을 서빙하는 구조와 Amazon EKS 최적화"
date: 2026-11-15
author: "Woohyung Choi"
status: draft
---

# OpenWeight on AWS GPU 2부: 두 모델을 서빙하는 구조와 Amazon EKS 최적화

by WOO HYUNG CHOI on 15 11월 2026 in [Advanced (300)](https://aws.amazon.com/ko/blogs/tech/category/learning-levels/advanced-300/), [Amazon Elastic Kubernetes Service](https://aws.amazon.com/ko/blogs/tech/category/compute/amazon-kubernetes-service/), [Generative AI](https://aws.amazon.com/ko/blogs/tech/category/artificial-intelligence/generative-ai/)

오픈 웨이트 모델(가중치가 공개되어 내려받아 직접 실행할 수 있는 모델)을 직접 서빙하는 일은 GPU 노드에 추론 엔진을 올리는 것으로 끝나지 않습니다. 요청을 받는 입구, 모델을 고르는 라우팅, 가중치를 GPU까지 옮기는 경로, 노드를 만들고 회수하는 규칙이 함께 있어야 합니다. OpenWeight on AWS GPU(OW on GPU)는 이 구성을 Amazon Elastic Kubernetes Service(Amazon EKS)에서 처음부터 만들어 보는 시리즈입니다. 예로 드는 환경은 오픈 소스 추론 엔진 vLLM으로 Gemma 4 31B와 Qwen3.8-27B를 함께 서빙하며 코드는 [ow-on-gpu 저장소](https://github.com/whchoi98/ow-on-gpu)에 있습니다.

2부인 이 글은 그 환경의 구조를 설명합니다. 먼저 전체 구성을 6개 계층으로 나눠 구성 요소마다 맡은 일을 봅니다. 이어서 Amazon EKS 쪽에서 적용한 최적화 4가지를 측정한 값과 함께 정리합니다. Gemma 4 31B의 콜드 스타트는 394초에서 260초가 됐습니다. 배치 부하 중 상담 요청의 첫 토큰까지의 시간은 중앙값 30.9초에서 0.19초가 됐고 잠든 Qwen3.8-27B는 3.66초 만에 복귀했습니다.

1부(TODO: Part 1 링크)는 API 호출 한 건이 이 구조를 지나는 8개 단계를 따라가고 3부(TODO: Part 3 링크)는 같은 환경을 10개 단계로 구축합니다. 본문의 값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)에서 측정했고 반복 횟수는 표마다 적었습니다. 이 글은 Kubernetes와 AWS의 기본 개념을 알고 LLM 서빙을 처음 구성하는 엔지니어를 대상으로 하며, 파드와 Deployment, IAM 역할을 알고 있다면 무리 없이 읽을 수 있습니다.

그림 1은 전체 구조를 한 장에 그린 것입니다. 이 글의 각 절은 이 그림의 한 부분을 확대해 설명합니다.

![브라우저의 요청이 CloudFront, 내부 ALB, BFF, 게이트웨이를 지나 GPU 노드의 Gemma 4 31B와 Qwen3.8-27B에 이르는 경로와, Hugging Face의 체크포인트를 적재 Job이 S3 모델 버킷에 올리고 GPU 노드가 그 버킷과 이미지 레지스트리에서 가중치, compile 캐시, 컨테이너 이미지를 받는 공급 경로를 한 장에 그린 구조도. 아래쪽에는 모델 적재부터 추론 요청까지의 6개 단계, BFF의 모델 결정 순서, 구간별 측정값, 경계별 접근 제한을 정리했다](images/2026-11-15-eks-vllm-two-models-part2-fig01-architecture.png)

*그림 1. 전체 구조 한눈에 보기. 실선은 요청과 데이터, 점선은 로그인과 권한, 지표의 흐름입니다. 번호 0에서 4는 모델과 이미지가 GPU 노드에 올라가는 순서이고 5는 추론 요청입니다.*

## 1. 전체 구조 한눈에 보기

### 1.1 6개 계층과 맡은 일

환경은 서울 리전의 Amazon EKS 1.37 클러스터 하나입니다. 구성 요소가 많아 보여도 맡은 일로 묶으면 6개 계층입니다. 계층마다 바꿀 수 있는 설정과 측정할 지표가 다르므로 이 구분을 먼저 익혀 두면 뒤의 절을 읽기 쉽습니다.

| 계층 | 구성 요소 | 맡은 일 |
|---|---|---|
| 앱 | Amazon CloudFront, AWS WAF, Amazon Cognito, 내부 ALB, BFF 파드 2개 | 정적 페이지 제공, 속도 제한, 로그인 토큰 검증, 모델과 우선순위 결정, 도구 실행 |
| 게이트웨이 | agentgateway 파드 2개, 모델별 EPP | 요청 본문의 `model` 값으로 모델별 풀 선택, 노출 경로 제한, 포화 시 배치 요청 거절 |
| 서빙 | vLLM 파드 2개(Gemma 4 31B, Qwen3.8-27B), Strands Decider 2B | 추론, 요청 처리 순서 결정, 모델 판단 |
| 모델과 이미지 공급 | Amazon S3 모델 버킷, 적재 Job, 캐시 게시 Job | 가중치와 compile 캐시를 GPU 노드까지 전달 |
| 노드 관리 | Karpenter NodePool 6개, 관리형 노드 그룹 1개 | 워크로드별 노드 생성과 회수 |
| 관측 | Prometheus agent, Amazon Managed Service for Prometheus | vLLM, EPP, 게이트웨이의 지표 수집과 저장 |

*표 1. 계층별 구성 요소와 맡은 일.*

그림 1의 왼쪽은 요청 경로입니다. 요청은 Amazon CloudFront, 내부 Application Load Balancer(ALB), BFF, 게이트웨이를 차례로 지나 vLLM에 도착합니다. BFF(Backend for Frontend)는 화면과 모델 사이에서 로그인을 확인하고 요청을 어느 모델로 보낼지 정하는 서비스입니다. 게이트웨이는 BFF가 정한 모델 이름을 보고 요청을 그 모델의 vLLM 파드로 넘깁니다. 인터넷에 열린 곳은 CloudFront 하나이고 나머지는 모두 VPC 안에 있습니다.

그림의 오른쪽은 공급 경로입니다. 모델의 가중치와 컨테이너 이미지가 GPU 노드에 올라가는 길이고 번호 0에서 4의 순서로 진행됩니다. 요청 경로가 응답 속도를 정한다면 공급 경로는 새 파드가 요청을 받기까지의 시간을 정합니다.

### 1.2 두 모델의 업무 배정과 데이터 정책

모델을 둘로 나눈 기준은 업무와 데이터입니다. Gemma 4 31B는 고객 요청을, Qwen3.8-27B는 내부 업무를 맡습니다.

| 업무 | 모델 | 우선순위 |
|---|---|---|
| 상담 챗봇(함수 호출로 주문 조회) | Gemma 4 31B | interactive |
| 상품 설명 다국어 번역, 리뷰 요약 | Gemma 4 31B | batch |
| 상품 이미지 속성 추출, 문서 OCR | Qwen3.8-27B | interactive 또는 batch |
| 사내 코딩 에이전트 | Qwen3.8-27B | interactive |

*표 2. 업무와 모델 배정. interactive는 사용자가 기다리는 요청이고 batch는 나중에 처리해도 되는 요청입니다.*

데이터 정책은 한 줄입니다. 개인정보가 든 요청은 Gemma 4 31B로만 보냅니다. 주민등록번호나 카드번호처럼 형식이 정해진 정보는 BFF의 규칙이 먼저 거르고, 형식이 없는 경우의 판단은 Strands Decider 2B가 돕습니다. 이 배정이 뒤에서 볼 두 가지 설계의 근거가 됩니다. 한 모델이 대화형 요청과 배치 요청을 함께 받으므로 우선순위가 필요합니다. 내부 업무용 모델은 업무 시간 밖에 사용하지 않으므로 재울 수 있습니다.

## 2. 노드 구성

### 2.1 관리형 노드 그룹 1개와 NodePool 6개

이 절은 어떤 워크로드가 어떤 노드에 올라가는지를 설명합니다. GPU 노드는 비싸고 종류가 적어서, 무엇을 GPU 노드에 올리고 무엇을 올리지 않을지를 노드 단위로 나눠 두어야 합니다.

Karpenter는 스케줄되지 못한 파드를 보고 조건에 맞는 EC2 인스턴스를 만드는 노드 프로비저너입니다. NodePool은 Karpenter가 만들 노드의 조건(인스턴스 유형, 용량 유형, taint, 한도)을 적은 리소스입니다. EC2NodeClass는 AMI와 서브넷, 사용자 데이터 같은 AWS 쪽 설정을 적은 리소스입니다. Karpenter 자신이 실행될 노드는 Karpenter가 뜨기 전부터 필요하므로 관리형 노드 그룹으로 만듭니다.

| 노드 묶음 | 인스턴스 | 올라가는 워크로드 | 격리와 한도 |
|---|---|---|---|
| 관리형 노드 그룹 `addons` | m7g.large 2대 | Karpenter, CoreDNS, AWS Load Balancer Controller | `CriticalAddonsOnly` taint |
| NodePool `system` | c7i-flex.xlarge 2대 | 게이트웨이, EPP, 깨우기 API, Prometheus agent, 적재 Job | CPU 32개 한도 |
| NodePool `app` | c7g.large 2대 | BFF 파드 2개 | `ow-on-gpu/app` taint, CPU 8개 한도 |
| NodePool `gemma-od` | g6e.4xlarge 1대 | Gemma 4 31B | `nvidia.com/gpu` taint, GPU 1장 한도 |
| NodePool `qwen-od` | g6e.4xlarge 1대 | Qwen3.8-27B | `nvidia.com/gpu` taint, GPU 1장 한도 |
| NodePool `decider` | g6.xlarge 1대 | Strands Decider 2B | `nvidia.com/gpu` taint, GPU 1장 한도 |
| NodePool `bench` | 측정할 때만 생성 | 부하 발생기 Job | `ow-on-gpu/bench` taint, CPU 16개 한도 |

*표 3. 노드 묶음과 워크로드(인스턴스는 2026년 11월 16일 기준). Karpenter가 만드는 노드는 모두 On-Demand이고 워크로드는 VPC의 프라이빗 서브넷에 둡니다.*

게이트웨이와 EPP는 두 모델이 함께 지나는 길목이라 `system` 노드 2대를 서로 다른 가용 영역에 두고 복제본을 나눠 올렸습니다. BFF는 Graviton 노드를, 부하 발생기는 측정할 때만 뜨는 노드를 따로 사용합니다. 측정 부하가 서빙 경로의 파드와 CPU를 다투지 않게 하려는 구분입니다.

### 2.2 모델마다 한 대로 묶는 GPU NodePool

GPU NodePool은 모델마다 하나입니다. 아래는 Gemma용이고 Qwen용은 이름만 다릅니다.

```yaml
# k8s/base/nodepools.yaml에서 발췌
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

이 매니페스트에서 볼 설정은 3곳입니다.

- `limits`의 `nvidia.com/gpu: 1`은 이 NodePool이 만드는 GPU를 한 장으로 묶습니다. Karpenter 문서에 따르면 한도를 넘은 NodePool은 새 노드를 만들지 않습니다. 복제본 수를 실수로 올려도 GPU 노드가 늘지 않습니다.
- `taints`는 이 taint를 허용하지 않는 파드가 GPU 노드에 스케줄되지 않게 합니다. vLLM 파드는 같은 키의 toleration과 `karpenter.sh/nodepool` nodeSelector로 자기 NodePool을 고릅니다.
- `consolidationPolicy: WhenEmpty`는 워크로드 파드가 없는 노드만 30분 뒤에 회수합니다. 파드를 다시 띄우는 동안 노드가 남아 있어야 뒤에서 볼 웜 재시작이 됩니다.

가용 영역 조건은 두지 않아 Karpenter가 용량이 있는 영역을 고릅니다. 조회 시점에 g6e.4xlarge는 서울 리전의 가용 영역 4곳 가운데 ap-northeast-2a와 ap-northeast-2b에서만 제공됐습니다.

### 2.3 g6e.4xlarge와 FP8 체크포인트

g6e.4xlarge에는 NVIDIA L40S가 한 장 있습니다. vCPU 16개, 메모리 128GiB, 인스턴스 스토어 600GB이고 GPU 메모리는 제품 페이지 표기로 48GB입니다. vLLM의 기동 로그에 기록된 값은 44.39GiB였습니다.

GPU 세대가 체크포인트의 형식을 정합니다. FP8은 가중치를 8비트 부동소수점으로 줄인 양자화 형식입니다. L40S는 Ada 세대(compute capability 8.9)이고 vLLM 문서의 양자화 지원표에서 llm-compressor FP8은 Ada와 Hopper에서 지원됩니다. 그래서 두 모델 모두 FP8-dynamic 체크포인트를 사용했습니다.

| 모델 | 체크포인트 | 가중치 파일 | GPU에 올라간 크기 |
|---|---|---:|---:|
| Gemma 4 31B | RedHatAI/gemma-4-31B-it-FP8-dynamic | 33.27GB | 30.63GiB |
| Qwen3.8-27B | AzatAI/Qwen3.8-27B-FP8-dynamic | 36.78GB | 34.39GiB |

*표 4. 두 모델의 체크포인트. 파일 크기는 1GB = 10^9바이트 기준이고 GPU에 올라간 크기는 vLLM 로그의 `Model loading took` 값입니다.*

Qwen3.8-27B에는 가중치가 5.9GB 작은 공식 block FP8 체크포인트도 있습니다. 다만 vLLM v0.33.0 소스에서 block FP8용 CUTLASS 커널은 compute capability 9.0 이상에서만 지원됩니다. 그래서 문서가 Ada 지원을 명시한 per-channel 체크포인트를 골랐고 L40S에서 block FP8이 어떻게 동작하는지는 확인하지 않았습니다. 다른 GPU를 사용한다면 체크포인트를 고르기 전에 그 세대가 지원하는 양자화 형식부터 확인하는 것을 권고합니다.

## 3. 모델과 이미지의 공급 경로

### 3.1 S3에 한 번 올리고 S3에서만 읽는 가중치

이 절은 30GiB가 넘는 가중치가 어디에 있고 어떤 권한으로 GPU 노드에 오는지를 설명합니다. 원칙은 하나입니다. 서빙 파드는 Hugging Face에서 내려받지 않고 Amazon Simple Storage Service(Amazon S3) 버킷에서만 읽습니다. 외부 저장소의 속도와 가용성이 서빙 파드의 시작에 영향을 주지 않게 하려는 구성입니다.

적재 Job이 리비전 해시로 고정한 저장소 4개를 버킷에 한 번 올립니다. 파일을 받는 대로 `s5cmd pipe`로 올려 로컬 디스크에 쌓지 않고, 받으면서 계산한 해시를 Hugging Face가 알려 준 값과 비교합니다. 2026년 11월 14일에 객체 73개, 74.90GB(69.8GiB)를 올리는 데 전송과 검증이 491.4초 걸렸습니다. 버킷의 구조는 다음과 같이 나눴습니다.

```
s3://<bucket>/models/gemma-4-31B-it-FP8-dynamic/
s3://<bucket>/models/Qwen3.8-27B-FP8-dynamic/
s3://<bucket>/models/strands-decider-2B-qwen3.5-v1-2610/
s3://<bucket>/models/Qwen3.5-2B-Base/
s3://<bucket>/vllm-cache/v0.33.0-gemma4-31b-fp8-l40s/
s3://<bucket>/vllm-cache/v0.33.0-qwen38-27b-fp8-l40s/
```

`models/`에는 가중치가, `vllm-cache/`에는 뒤에서 설명할 compile 캐시가 들어갑니다. Decider의 저장소에는 어댑터와 헤드만 있어 기반 모델(Qwen3.5-2B-Base)을 함께 올렸습니다.

권한은 EKS Pod Identity로 줍니다. EKS Pod Identity는 AWS Identity and Access Management(IAM) 역할을 Kubernetes ServiceAccount에 연결해 파드에 임시 자격 증명을 주는 기능입니다. 역할은 읽기와 쓰기로 나눴습니다. 읽기 역할은 서빙 파드의 ServiceAccount 3개(`gemma`, `qwen`, `decider`)에, 쓰기 역할은 적재 Job과 캐시 게시 Job에만 연결했습니다. 서빙 파드는 버킷에 아무것도 올리지 못하고 매니페스트에는 자격 증명이 없습니다. 버킷까지의 트래픽은 VPC의 S3 게이트웨이 엔드포인트를 지납니다.

### 3.2 GPU 노드의 디스크와 이미지

vLLM 이미지(`vllm/vllm-openai:v0.33.0`)는 9.74GB입니다. GPU 노드의 EC2NodeClass는 이 이미지를 받을 자리와 받는 시점을 정합니다.

```yaml
# k8s/base/ec2nodeclasses.yaml에서 발췌(주석과 일부 필드 생략)
apiVersion: karpenter.k8s.aws/v1
kind: EC2NodeClass
metadata:
  name: vllm
spec:
  amiSelectorTerms:
    - alias: al2023@v20261107
  instanceStorePolicy: RAID0
  userData: |
    #!/bin/bash
    systemd-run --unit=prepull-vllm --no-block /bin/bash -c '
      until ctr --namespace k8s.io version >/dev/null 2>&1; do sleep 1; done
      ctr --namespace k8s.io images pull docker.io/vllm/vllm-openai:v0.33.0
    '
```

`amiSelectorTerms`의 별칭은 EKS 최적화 AL2023 AMI의 릴리스를 고정하고 GPU 노드에는 NVIDIA 드라이버가 든 변형이 올라옵니다. `instanceStorePolicy: RAID0`은 인스턴스 스토어를 kubelet과 containerd의 저장 공간으로 사용하게 합니다. GPU 노드에서는 559GB가 마운트됐고 이미지가 여기에 저장됐습니다. `userData`의 스크립트는 노드가 뜨는 동안 이미지를 미리 받기 시작합니다. 이 사전 pull의 효과는 다음 절에서 봅니다.

### 3.3 가중치와 compile 캐시를 받는 vLLM 파드

Gemma의 Deployment에서 공급 경로와 관련된 부분만 옮겼습니다.

```yaml
# k8s/gemma/deployment.yaml에서 발췌
      initContainers:
        - name: cache-restore
          image: vllm/vllm-openai:v0.33.0
          command: ["python3", "/scripts/cache-restore.py"]
          env:
            - name: CACHE_PREFIX
              value: vllm-cache/v0.33.0-gemma4-31b-fp8-l40s
      containers:
        - name: vllm
          image: vllm/vllm-openai:v0.33.0
          args:
            - s3://$(MODEL_BUCKET)/models/gemma-4-31B-it-FP8-dynamic
            - --load-format=runai_streamer
            - --gpu-memory-utilization=0.90
          env:
            - name: VLLM_CACHE_ROOT
              value: /vllm-cache
            - name: HF_HUB_OFFLINE
              value: "1"
      volumes:
        - name: vllm-cache
          hostPath:
            path: /var/cache/vllm
```

모델 인자가 `s3://` 경로이고 로더가 `runai_streamer`입니다. vLLM 문서에 따르면 Run:ai Model Streamer는 텐서를 동시에 읽으면서 GPU 메모리로 스트리밍하는 라이브러리입니다. 가중치를 노드의 디스크에 먼저 내려받는 단계가 없습니다. `HF_HUB_OFFLINE=1`은 설정이 틀렸을 때 파드가 조용히 Hugging Face에서 받아 오는 일을 막습니다. initContainer(초기화 컨테이너) `cache-restore`는 S3의 compile 캐시를 노드의 hostPath로 내려받습니다.

## 4. EKS 최적화 1, 콜드 스타트 4개 구간

### 4.1 구간을 나눠 측정한 결과

GPU 노드에서 서빙 파드를 새로 띄우면 요청을 받기까지 몇 분이 걸립니다. 노드를 줄였다 늘리거나 장애 뒤에 복구할 때 이 시간이 그대로 서비스 공백이 됩니다. 새 노드에서 시작하는 경우를 콜드 스타트(Cold start), 같은 노드에서 파드만 다시 띄우는 경우를 웜 재시작(Warm restart)이라고 부르겠습니다.

파드 생성부터 Ready까지의 시간을 4개 구간과 나머지(기타)로 나눴습니다. 구간마다 기다리는 대상이 다르므로 줄이는 방법도 다릅니다. 기준 구성은 최적화를 적용하기 전의 구성이고 최적화 구성이 지금 서빙에 사용하는 구성입니다.

| 구간 | 측정 근거 | 기준 구성 | 최적화 구성 | 기준 | 최적화 |
|---|---|---|---|---:|---:|
| 노드 프로비저닝 | NodeClaim 생성부터 노드의 Ready까지 | Karpenter가 g6e.4xlarge를 만듦 | 같음 | 55.0 | 71.0 |
| 이미지 pull | kubelet의 `Pulled` 이벤트 | 파드가 스케줄된 뒤 받기 시작 | 노드가 뜨는 동안 받기 시작 | 111.1 | 71.0 |
| 가중치 로드 | vLLM 로그의 `Model loading took` | Mountpoint for Amazon S3로 마운트한 경로를 기본 로더로 읽음 | `s3://` 경로를 runai_streamer로 스트리밍 | 59.6 | 19.2 |
| 엔진 초기화 | vLLM 로그의 `init engine ... took` | compile 캐시가 컨테이너 안에 생기고 파드와 함께 사라짐 | S3의 compile 캐시를 hostPath로 복원 | 95.5 | 23.7 |
| 기타 | 전체에서 위 4개 구간을 뺀 값 | | | 72.7 | 75.1 |
| 합계 | 파드 생성부터 Ready까지 | | | 394 | 260 |

*표 5. Gemma 4 31B 콜드 스타트의 구간별 시간(초, 2026년 11월 14일, 구성마다 한 번). 로더를 뺀 엔진 플래그와 모델, vLLM 버전은 두 구성이 같습니다.*

| 시나리오 | Gemma 4 31B | Qwen3.8-27B |
|---|---:|---:|
| 콜드 스타트, 기준 구성 | 394초 | 측정하지 않음 |
| 콜드 스타트, 최적화 구성 | 260초 | 290초 |
| 웜 재시작, 기준 구성 | 214초 | 측정하지 않음 |
| 웜 재시작, 최적화 구성 | 86초 | 123초 |

*표 6. 시나리오별 파드 생성부터 Ready까지의 시간(2026년 11월 14일, 시나리오마다 한 번).*

Gemma 4 31B의 콜드 스타트는 134초(34%), 웜 재시작은 128초(60%) 줄었습니다. 그림 2는 시나리오별 구간과 구간마다 적용한 조치를 함께 보여 줍니다.

![콜드 스타트의 구간 분해와 최적화를 한 장에 정리한 인포그래픽. Gemma 4 31B의 파드 생성에서 Ready까지의 시간이 콜드 스타트는 394초에서 260초로, 웜 재시작은 214초에서 86초로 줄었고, 이미지 pull은 노드 부팅 중 사전 pull로 111.1초에서 71.0초, 가중치 로드는 runai_streamer로 59.6초에서 19.2초, 엔진 초기화는 compile 캐시 복원으로 95.5초에서 23.7초가 됐음을 시나리오별 막대와 조치 표로 보여 준다](images/2026-11-15-eks-vllm-two-models-part2-fig02-cold-start.png)

*그림 2. 콜드 스타트 4개 구간과 구간별 조치. Qwen3.8-27B는 최적화 구성만 측정했습니다.*

### 4.2 구간마다 다른 3가지 조치

이미지 사전 pull은 받는 시간을 줄이지 않고 받기 시작하는 시점을 당깁니다. 기준 구성에서는 파드가 스케줄된 뒤에야 kubelet이 9.74GB 이미지를 받기 시작합니다. 최적화 구성에서는 노드의 사용자 데이터가 containerd가 뜨자마자 받기 시작하고 kubelet은 진행 중인 다운로드를 이어받습니다. kubelet이 기다린 시간은 111.1초에서 71.0초가 됐습니다. 새 노드가 자주 뜨는 환경에서 적용할 만합니다.

스트리밍 로더는 가중치 로드를 59.6초에서 19.2초로 줄였습니다(3.1배). 웜 재시작에서도 59.1초와 19.6초여서 이 구간은 노드가 새것인지와 무관했습니다. 가중치를 S3에 두고 있다면 `--load-format=runai_streamer`와 `s3://` 경로, Pod Identity 권한으로 적용합니다. Run:ai Model Streamer가 boto3의 자격 증명을 사용하도록 `RUNAI_STREAMER_NO_BOTO3_SESSION=0`을 함께 설정했습니다.

compile 캐시는 엔진 초기화를 95.5초에서 23.7초로 줄였습니다. vLLM은 요청을 받기 전에 `torch.compile`을 끝내므로 컴파일 시간이 시작 시간에 그대로 들어갑니다. 차이의 대부분이 이 컴파일입니다(61.0초에서 0.9초). 캐시는 두 곳에 둡니다. 노드의 hostPath에 두면 같은 노드에서 파드가 다시 뜰 때 남아 있고, S3에 게시해 두면 새 노드에서 initContainer가 복원합니다. Gemma 4 31B의 캐시는 객체 522개, 90.8MB였고 복원에 3.3초가 걸렸습니다.

캐시를 운영할 때 지킬 규칙이 하나 있습니다. S3 prefix 이름에 vLLM 버전, 모델, 정밀도, GPU를 넣고 하나라도 바뀌면 새 prefix로 다시 게시합니다. 2026년 11월 15일에 Qwen의 플래그 하나를 바꿔 띄웠을 때 기존 캐시가 맞지 않아 compile에 62.6초가 걸렸습니다.

최적화 뒤에 남은 것은 노드 프로비저닝과 기타이고 260초 가운데 146.1초입니다. 노드 프로비저닝은 같은 날에도 55초에서 118초까지 달랐습니다. 이 글의 값을 예상치로 사용하기보다 같은 근거(NodeClaim과 파드의 시각, kubelet의 `Pulled` 이벤트, vLLM 로그 두 줄)로 직접 측정하는 것을 권고합니다.

## 5. EKS 최적화 2, GPU 메모리와 동시 실행

### 5.1 가중치를 빼고 남는 KV 캐시

파드가 Ready가 된 뒤에는 GPU 한 장이 요청을 동시에 몇 건 실행하는지가 용량을 정합니다. 그 수를 정하는 것이 KV 캐시입니다. KV 캐시(Key-Value cache)는 이미 처리한 토큰의 계산 결과를 GPU 메모리에 보관해 다음 토큰을 만들 때 다시 계산하지 않게 하는 공간입니다. 실행 중인 요청마다 자리를 차지하므로 KV 캐시가 차면 다음 요청은 기다립니다.

vLLM은 `--gpu-memory-utilization`으로 정한 비율만큼 GPU 메모리를 사용하고 가중치와 실행에 필요한 메모리를 뺀 나머지를 KV 캐시로 미리 잡습니다.

```
KV 캐시 메모리 = GPU 메모리 × gpu-memory-utilization - 가중치와 비 torch 메모리 - 활성값 최대

Gemma: 44.39 × 0.90 - 31.13 - 3.45 = 5.37 GiB
Qwen:  44.39 × 0.90 - 34.74 - 2.76 = 2.45 GiB
```

48GB GPU에 30GiB대 체크포인트를 올리면 KV 캐시로 남는 메모리는 한 자릿수 GiB입니다. Qwen3.8-27B는 처음 값인 0.85에서 KV 캐시가 0.24GiB만 남아 엔진이 시작하지 못했고 0.90으로 올려서야 시작했습니다. 가중치가 GPU 메모리의 대부분을 차지하는 구성에서는 이 값이 시작 성공 여부까지 정합니다.

### 5.2 Gemma 4 31B는 KV 캐시에 들어가는 만큼 실행

이 환경의 SLO(서비스 수준 목표)는 두 가지입니다. TTFT(Time To First Token)는 요청을 보내고 첫 토큰을 받기까지의 시간이고 p99가 500ms 이하여야 합니다. ITL(Inter-Token Latency)은 스트리밍으로 오는 응답 조각 사이의 간격이고 p99가 50ms 이하여야 합니다. 부하는 게이트웨이를 거치지 않고 vLLM Service에 직접 보냈고 동시성을 1에서 64까지 7단계로 올렸습니다.

| 워크로드 | 입력, 출력 토큰 | 동시 실행 한도 | 최대 출력 처리량 | TTFT p99 500ms 이하인 최대 동시성 |
|---|---|---:|---:|---:|
| S1 짧은 채팅 | 256, 128 | 45건 | 447.0 tok/s | 8 |
| S2 요약과 생성 | 1,024, 256 | 12건 | 164.7 tok/s | 1 |
| S3 분류 | 512, 16 | 24건 | 114.7 tok/s | 4 |
| S4 장문 RAG | 4,096, 256 | 7건 | 81.8 tok/s | 없음 |

*표 7. Gemma 4 31B의 워크로드별 결과(2026년 11월 14일, 랜덤 토큰 프롬프트, 단계마다 한 번). 동시 실행 한도는 동시성 64에서 엔진이 실제로 실행한 요청 수입니다.*

요청이 길수록 한 건이 KV 캐시를 많이 차지해 동시에 실행되는 수가 줄어듭니다. 한도에 닿은 뒤에는 동시성을 올려도 처리량이 늘지 않고 TTFT만 길어집니다. S2는 동시성 16, 32, 64에서 처리량이 163.6, 164.7, 164.0 tok/s로 같았고 TTFT p99는 19초, 38초, 91초로 늘었습니다.

ITL은 부하와 무관하게 기준을 넘었습니다. 요청을 하나씩 보낸 동시성 1에서도 ITL p99가 57.6ms에서 58.6ms였고 중앙값이 54.0ms였습니다. 토큰 하나를 만드는 54ms는 L40S에서 이 체크포인트가 내는 속도입니다. 부하를 줄여서 나아지는 것은 TTFT이고 ITL 기준을 지키려면 GPU나 체크포인트를 바꾸거나 기준을 다시 정해야 합니다.

### 5.3 Qwen3.8-27B의 동시 3건 한도와 MTP

Qwen3.8-27B는 부하를 올려도 요청을 동시에 3건만 실행했습니다. 원인은 MTP(Multi-Token Prediction)입니다. MTP는 모델의 예측 헤드로 다음 토큰 여러 개를 미리 추측하고 본 모델이 한 번에 검증해 요청 하나의 속도를 올리는 방식입니다. vLLM v0.33.0 소스의 블록 계산에 따르면 추측 토큰 3개가 요청마다 잡는 상태 블록을 4배로 늘립니다. 요청 하나가 13블록을 잡고 KV 캐시 2.45GiB는 46블록이어서 3건에서 멈춥니다. MTP를 끄면 요청 하나가 4블록을 잡습니다.

| 항목 | MTP 켬(추측 토큰 3개) | MTP 끔 |
|---|---:|---:|
| 요청당 KV 캐시 블록 | 13 | 4 |
| KV 캐시 | 2.45GiB, 46블록 | 4.0GiB, 82블록 |
| 동시 실행 한도 | 3건 | 20건 |
| 요청 하나의 생성 속도(동시성 1) | 32.5 tok/s | 19.2 tok/s |
| 최대 출력 처리량 | 91.2 tok/s | 281.8 tok/s |
| TTFT p99 500ms 이하인 최대 동시성 | 2 | 8 |

*표 8. Qwen3.8-27B, S1에서 MTP를 켠 구성(2026년 11월 14일)과 끈 구성(2026년 11월 15일). 랜덤 토큰 프롬프트, 각각 한 번 측정.*

MTP는 요청 하나의 속도를 1.7배로 올리는 대신 동시 실행 수를 3으로 묶습니다. 그래서 선택 기준은 동시에 겹치는 요청 수입니다. 요청이 3건을 넘지 않는 업무라면 켜는 쪽이, 사내 코딩 에이전트처럼 4건 이상 겹치는 업무라면 끄는 쪽이 유리합니다. 랜덤 토큰 프롬프트로 한 번 측정한 값이므로 실제 워크로드에서는 추측이 맞는 비율에 따라 속도 차이가 달라집니다.

![L40S의 GPU 메모리 배분과 동시 실행 결과를 4칸으로 정리한 인포그래픽. SLO는 TTFT p99 500ms 이하와 ITL p99 50ms 이하이고, 가중치와 활성값을 빼면 KV 캐시는 Gemma 4 31B에 5.37GiB, Qwen3.8-27B에 2.45GiB가 남으며, S1에서 Gemma는 동시성 64에서 45건을 실행해 447.0 tok/s까지 늘고 Qwen은 MTP를 켠 구성에서 3건에 묶여 85.0에서 91.2 tok/s에 머물고, MTP를 끄면 동시 실행 한도가 20건이 되는 대신 요청 하나의 속도가 32.5에서 19.2 tok/s로 줄어든다](images/2026-11-15-eks-vllm-two-models-part2-fig03-gpu-memory-concurrency.png)

*그림 3. GPU 메모리 배분과 동시 실행. 3번 칸의 막대는 S1 짧은 채팅의 출력 처리량이고 분홍색 막대는 동시 실행 한도에 닿은 단계입니다.*

용량을 볼 때는 기동 로그의 KV 캐시 크기만 보지 않는 것을 권고합니다. 엔진 지표의 실행 중 요청 수(`vllm:num_requests_running`)와 KV 캐시 사용률(`vllm:kv_cache_usage_perc`)을 함께 봅니다. Qwen의 한도는 로그의 토큰 수로는 알 수 없었고 이 두 지표에서 드러났습니다.

## 6. 게이트웨이 계층

### 6.1 InferencePool, EPP, agentgateway

게이트웨이 계층은 요청을 모델에 맞는 vLLM 파드로 넘기는 층입니다. 모델이 둘이므로 엔드포인트도 둘로 나눌 수 있지만, 이 환경은 엔드포인트를 하나로 두고 게이트웨이가 요청마다 모델을 가립니다. 클라이언트와 BFF는 주소 하나만 알면 되고 모델을 늘릴 때는 경로 규칙만 더합니다.

[Gateway API Inference Extension](https://gateway-api-inference-extension.sigs.k8s.io/)(GAIE)은 Kubernetes Gateway API에 추론 워크로드용 리소스를 더하는 프로젝트입니다. InferencePool은 같은 모델을 서빙하는 파드의 묶음이고 HTTPRoute의 백엔드가 됩니다. EPP(Endpoint Picker)는 풀 안에서 요청을 받을 파드를 고르는 구성 요소입니다. agentgateway는 이 리소스를 읽어 실제로 트래픽을 넘기는 게이트웨이 구현체입니다.

| 구성 요소 | 버전 | 이 환경에서 하는 일 |
|---|---|---|
| Gateway API CRD | v1.6.3 | Gateway, HTTPRoute |
| GAIE CRD | v1.6.2 | InferencePool |
| llm-d-router | v1.0.0 | 풀마다 EPP 2개, InferenceObjective |
| agentgateway | v1.7.0 | 게이트웨이 파드 2개, 본문 기반 라우팅 |
| AWS Load Balancer Controller | v3.6.3 | 게이트웨이 앞의 내부 NLB, BFF 앞의 내부 ALB |

*표 9. 게이트웨이 계층의 구성 요소와 버전(2026년 11월 14일 기준).*

[GAIE v1.6.0 릴리스 노트](https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/tag/v1.6.0)에 따르면 이 버전부터 EPP와 InferenceObjective가 llm-d 프로젝트로 옮겨졌습니다. 그래서 InferencePool CRD만 GAIE에서 설치하고 EPP와 InferenceObjective는 llm-d-router에서 설치했습니다. 이 환경은 풀마다 vLLM 파드가 하나라서 EPP가 고를 대상이 하나뿐이고 EPP의 스케줄링 시간은 요청당 0.03ms였습니다. 여기서 EPP가 실제로 하는 일은 풀이 포화했는지 판단해 우선순위가 낮은 요청을 거절하는 것입니다.

### 6.2 본문의 model 값으로 고르는 풀

OpenAI 호환 API에서 모델 이름은 URL이 아닌 요청 본문에 있습니다. 경로와 헤더로 백엔드를 고르는 HTTPRoute만으로는 두 모델을 가를 수 없으므로 라우팅 전에 본문의 `model` 값을 헤더로 옮깁니다. [agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)에 따르면 이 일은 `AgentgatewayPolicy` 하나로 처리합니다.

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

HTTPRoute는 이 헤더와 경로가 모두 정확히 맞는 요청만 풀로 보냅니다. 등록한 경로는 `/v1/chat/completions`와 `/v1/models` 둘이고 경로 일치 방식은 `Exact`입니다. Qwen 파드의 8000 포트에는 추론 API와 함께 `/sleep`, `/wake_up` 같은 관리 엔드포인트가 열려 있습니다. 등록한 경로만 통과시키므로 이 엔드포인트로 가는 요청은 게이트웨이에서 404로 끝납니다. 클라이언트가 헤더를 직접 넣어도 본문의 값이 덮어쓰므로 헤더를 위조해 다른 풀을 고를 수도 없습니다.

게이트웨이와 EPP가 멈추면 두 모델 모두 응답하지 못합니다. 그래서 게이트웨이 파드 2개를 서로 다른 가용 영역에 두었습니다. `topologySpreadConstraints`만으로는 분산이 걸리지 않았고 `minDomains: 2`와 `matchLabelKeys: [pod-template-hash]`를 함께 두자 두 파드가 다른 영역에 배치됐습니다. EPP는 풀마다 2개이고 리더 하나가 요청을 처리합니다.

게이트웨이로 들어오는 길은 둘입니다. BFF는 클러스터 안의 Service를 직접 호출하고 배치 작업은 게이트웨이 앞의 내부 Network Load Balancer(NLB)로 들어옵니다. 두 길 모두 같은 라우팅 규칙을 지납니다. 2026년 11월 15일에 요청을 하나씩 보낸 측정에서 게이트웨이 구간의 중앙값은 Gemma 4 31B 9.7ms, Qwen3.8-27B 8.4ms였습니다(모델마다 20건).

## 7. EKS 최적화 3, 두 층의 우선순위

Gemma 4 31B는 사용자가 기다리는 상담 요청과 나중에 처리해도 되는 번역, 요약 요청을 함께 받습니다. 배치 요청이 KV 캐시를 채우고 있으면 상담 요청은 그 뒤에서 기다립니다. 이 구성에서 우선순위를 지정하는 곳은 두 군데입니다.

- 게이트웨이: `InferenceObjective`에 priority를 정의하고 요청은 `x-llm-d-inference-objective` 헤더로 그 이름을 고릅니다. [llm-d의 flow control 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md)에 따르면 기본 상태에서는 풀이 포화했을 때 priority가 0보다 낮은 요청을 HTTP 429로 거절합니다.
- 엔진: vLLM을 `--scheduling-policy=priority`로 실행하고 요청 본문의 `priority`로 지정합니다. [vLLM의 스케줄러 설정 문서](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)에 따르면 값이 작을수록 먼저 처리합니다.

두 값은 방향이 반대입니다. 상담 요청은 게이트웨이에서 priority 10인 objective를, 엔진에서는 `priority` 0을 받습니다. 배치 요청은 각각 -1과 10입니다. 클라이언트는 이 값을 몰라도 됩니다. BFF가 업무 종류에 따라 헤더와 본문의 값을 함께 채웁니다.

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

어느 쪽이 효과가 있는지 4가지 경우로 나눠 측정했습니다. 배치 요청 32개를 끊임없이 보내 KV 캐시를 채운 상태에서 상담 요청을 1.5초마다 하나씩 60건 보냈습니다.

| 경우 | 상담 TTFT p50 | p90 | 배치 429 거절 | 엔진의 대기 요청 수(평균) |
|---|---:|---:|---:|---:|
| 우선순위 없음 | 30,895ms | 39,154ms | 0건 | 31.0 |
| 게이트웨이만 | 11,183ms | 23,081ms | 1,907건 | 15.3 |
| 엔진만 | 190ms | 1,244ms | 0건 | 17.9 |
| 둘 다 | 193ms | 1,030ms | 1,988건 | 9.3 |

*표 10. 배치 부하 중 상담 요청의 TTFT와 배치 처리 결과(Gemma 4 31B, 2026년 11월 14일, 경우마다 90초씩 한 번). 요청은 모두 게이트웨이를 거쳤습니다.*

![상담 요청과 배치 요청이 게이트웨이와 엔진에서 다뤄지는 방식을 나타낸 도식. 게이트웨이는 풀이 포화하면 priority가 -1인 배치 요청을 429로 거절하고 엔진은 priority 값이 작은 상담 요청을 대기열 맨 앞에 두며, 상담 요청의 TTFT 중앙값은 우선순위가 없으면 30.9초, 게이트웨이만 지정하면 11.2초, 엔진만 지정하거나 둘 다 지정하면 0.19초이다](images/2026-11-15-eks-vllm-two-models-part2-fig04-priority-layers.png)

*그림 4. 우선순위가 작동하는 두 층. 대기열에 그린 요청의 수는 설명용이고 TTFT와 429 거절 건수, 엔진의 대기 요청 수는 표 10의 값입니다.*

상담 요청의 대기를 없앤 것은 엔진 우선순위입니다. TTFT 중앙값이 30.9초에서 0.19초가 됐습니다. 게이트웨이는 배치 요청을 거절해 엔진의 대기열을 줄였지만 이미 엔진에 들어간 배치 요청 뒤에서 기다리는 것은 그대로여서 11.2초였습니다. 배치의 출력 처리량은 4가지 경우 모두 초당 159토큰에서 176토큰이었습니다. 우선순위는 처리 순서를 바꾸고 전체 처리량은 바꾸지 않습니다.

한 모델이 대화형 요청과 배치 요청을 함께 받는다면 엔진 우선순위부터 켜는 것을 권고합니다. 적용할 때 볼 점이 두 가지 있습니다. 배치 클라이언트는 429를 받으므로 재시도 간격을 늘리는 처리가 필요합니다. 엔진 우선순위를 켜도 p90은 1.2초였습니다. 이 측정은 Gemma 4 31B로만 했습니다.

## 8. EKS 최적화 4, Qwen3.8-27B의 sleep과 깨우기

내부 업무용인 Qwen3.8-27B는 업무 시간 밖에는 요청이 거의 없습니다. 파드를 내리면 다시 띄우는 데 2분 넘게 걸리므로 내리지 않고 재웁니다. vLLM의 sleep mode는 파드를 그대로 둔 채 모델을 GPU에서 내리는 기능입니다. [vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)에 따르면 level 1 sleep은 가중치를 호스트 메모리로 옮기고 KV 캐시를 비웁니다. 이 환경에서 GPU 메모리 사용량은 40,899MiB에서 2,299MiB로 줄었습니다.

| 다시 요청을 받는 방법 | 걸린 시간 | 남아 있는 것 |
|---|---:|---|
| sleep에서 복귀 | 3.66초 | 노드, 파드, 호스트 메모리의 가중치 |
| 웜 재시작(같은 노드에서 파드를 다시 띄움) | 123초 | 노드, 이미지, 노드의 compile 캐시 |
| 콜드 스타트(새 노드) | 290초 | S3의 가중치와 compile 캐시 |

*표 11. Qwen3.8-27B가 다시 요청을 받기까지의 시간(2026년 11월 14일). 복귀는 같은 파드에서 5회 반복한 값의 최대이고 나머지는 한 번 측정한 값입니다.*

구성은 표 12와 같습니다.

| 객체 | 내용 |
|---|---|
| CronJob `qwen-sleep` | 평일 19:00(Asia/Seoul)에 `/sleep?level=1&mode=wait` 호출 |
| CronJob `qwen-wake` | 평일 08:30(Asia/Seoul)에 깨우기 API 호출 |
| Deployment `qwen-wake-api` | `POST /wake`만 제공. 잠들어 있으면 `/wake_up` 호출. 복제본 2개 |
| Service `vllm-qwen-admin` | 관리 요청용 헤드리스 Service. NotReady 파드의 주소도 돌려줌 |
| NetworkPolicy 2개 | Qwen의 8000 포트와 깨우기 API의 8080 포트에 정해진 파드만 허용 |

*표 12. Qwen3.8-27B의 sleep 운영 구성.*

![Qwen3.8-27B를 평일 19:00에 재우고 08:30에 깨우는 일정과, 잠든 동안 들어온 요청을 BFF가 깨우기 API로 먼저 깨운 뒤 게이트웨이로 보내는 흐름을 나타낸 도식. sleep 중 GPU 메모리 사용량은 40,899MiB에서 2,299MiB로 줄고 복귀는 3.66초이며 잠든 Qwen에 보낸 요청은 첫 내용까지 4.06초가 걸렸다](images/2026-11-15-eks-vllm-two-models-part2-fig05-sleep-wake.png)

*그림 5. Qwen3.8-27B의 sleep과 깨우기. 위는 평일 하루의 일정(Asia/Seoul)이고 아래는 잠든 동안 들어온 요청의 흐름과 잠든 파드를 일반 Service에서 빼는 방법입니다.*

구성할 때 놓치기 쉬운 설정이 3가지 있습니다.

- 재울 때는 `mode=wait`를 줍니다. 진행 중인 요청이 끝난 뒤에 잠듭니다. 기본값 `abort`는 진행 중인 요청을 중단합니다.
- readinessProbe는 `/health`가 아닌 `/is_sleeping`을 확인합니다. `/health`는 잠든 동안에도 200을 돌려주므로 그대로 두면 잠든 파드가 요청을 받습니다.
- 관리 엔드포인트는 `VLLM_SERVER_DEV_MODE=1`로 열립니다. 게이트웨이의 경로 규칙에 등록하지 않고 NetworkPolicy로 닿을 수 있는 파드를 제한했습니다.

잠든 동안 요청이 오면 BFF가 깨웁니다. BFF는 Qwen으로 갈 요청마다 깨우기 API를 먼저 호출합니다. 2026년 11월 15일에 잠든 Qwen에 요청을 한 번 보냈을 때 첫 내용까지 4.06초가 걸렸습니다. 깨어 있을 때 이 호출은 중앙값 12.8ms였습니다(20건).

sleep을 적용하기 전에 확인할 조건이 두 가지 있습니다. sleep은 노드를 그대로 두므로 노드 요금은 줄지 않고 줄어드는 것은 GPU 메모리 사용량입니다. 요금을 줄이려면 노드를 회수해야 하고 그때는 콜드 스타트 290초를 받아들여야 합니다. 또 가중치가 호스트 메모리에 남으므로 노드의 시스템 메모리가 넉넉해야 합니다. sleep을 한 번 거친 뒤 컨테이너 메모리는 60.4GiB였고 g6e.4xlarge의 메모리는 128GiB입니다.

## 9. Decider 2B와 Web Search가 놓인 자리

구조도에는 추론 모델 말고도 요청을 돕는 구성 요소가 둘 있습니다. 어디에 놓였는지만 정리하고 요청마다의 동작은 1부(TODO: Part 1 링크)에서 다룹니다.

[Strands Decider](https://github.com/strands-labs/strands-decider) 2B는 요청을 읽고 어느 모델이 받아야 할지 판단하는 작은 모델입니다. g6.xlarge 노드 한 대에서 실행하고 게이트웨이의 `/decide` 경로로 호출합니다. InferencePool을 사용하지 않고 HTTPRoute가 Service로 바로 보냅니다. 어댑터와 기반 모델은 두 추론 모델과 같은 S3 버킷에서 받습니다. BFF는 규칙으로 모델이 정해지지 않는 요청만 Decider 2B에 묻습니다. BFF가 측정한 판단 왕복은 139.4ms에서 150.0ms였습니다(2026년 11월 15일, 4건).

[Amazon Bedrock AgentCore Web Search](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)는 BFF가 실행하는 도구입니다. 추론은 그대로 두 모델이 하고 검색만 이 API가 합니다. 그래서 게이트웨이와 vLLM의 구성은 바꾸지 않았습니다. 이 API는 서울 리전에서 제공되지 않아 us-east-1을 호출합니다. 검색어가 리전 밖으로 나가므로 민감 정보가 있는 요청에는 도구를 넣지 않습니다. 권한은 BFF 파드의 ServiceAccount에 연결한 역할 하나이고 `bedrock-agentcore:InvokeWebSearch`만 허용합니다.

## 10. 접근 제한과 권한

구성 요소 사이의 경계마다 허용하는 출발지를 정했습니다. 인터넷에서 닿는 곳은 CloudFront뿐이고 안쪽으로 갈수록 허용 대상이 좁아집니다.

| 대상 | 허용하는 출발지 | 수단 |
|---|---|---|
| CloudFront | IP당 5분 300회까지. `/v1/*` 요청은 BFF가 Amazon Cognito 액세스 토큰을 검증 | AWS WAF 속도 기반 규칙, 토큰 검증 |
| 내부 ALB(80) | CloudFront VPC origin의 보안 그룹 | 보안 그룹 |
| BFF 파드(8080) | 내부 ALB에 연결된 백엔드 보안 그룹 | 보안 그룹 |
| 게이트웨이 내부 NLB(80) | 배치 클라이언트의 보안 그룹 | 보안 그룹 |
| 깨우기 API 파드(8080) | BFF 파드, 깨우기 CronJob의 파드 | NetworkPolicy |
| Qwen 파드(8000) | 게이트웨이, EPP, 깨우기 API, 지표 수집기, `ow-on-gpu/qwen-admin` 라벨이 있는 관리용 파드 | NetworkPolicy |

*표 13. 경계별 접근 제한.*

내부 ALB는 [CloudFront VPC origins](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)로 연결했습니다. 프라이빗 서브넷의 ALB를 CloudFront의 오리진으로 사용하는 기능이어서 ALB를 인터넷에 내놓지 않아도 됩니다. ALB 자체는 AWS Load Balancer Controller가 BFF의 Ingress에서 만듭니다.

NetworkPolicy에는 선행 조건이 있습니다. Amazon VPC CNI 애드온의 구성 값에 `enableNetworkPolicy: "true"`를 넣어야 하고, 이 값을 넣기 전에는 정책을 만들어도 적용되지 않았습니다.

AWS 권한은 모두 EKS Pod Identity로 주고 파드의 일마다 역할을 나눴습니다.

| ServiceAccount | 허용하는 것 |
|---|---|
| `inference`의 `gemma`, `qwen`, `decider` | 모델 버킷의 `models/`와 `vllm-cache/` 읽기 |
| `model-jobs`의 `model-sync`, `cache-publish` | 같은 경로에 쓰기 |
| `app`의 `bff` | `bedrock-agentcore:InvokeWebSearch` |
| `monitoring`의 지표 수집기 | Amazon Managed Service for Prometheus에 원격 쓰기 |

*표 14. EKS Pod Identity로 연결한 역할. 앞의 이름은 네임스페이스입니다.*

로그인은 Amazon Cognito 사용자 풀이 맡고 가입은 막았습니다. 인증은 BFF에서 하므로 토큰 없는 요청도 BFF까지는 도달해 401을 받습니다. 그 앞에서 막는 장치는 AWS WAF의 속도 기반 규칙입니다. 2026년 11월 14일에 정적 페이지에 0.5초 동안 400번을 요청하자 400번이 모두 통과했고 첫 403은 25.6초 뒤에 나왔습니다. [AWS WAF 문서](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)에 따르면 속도 기반 규칙은 정밀한 요청 수 제한용이 아닙니다. 짧은 시간에 몰린 요청은 한도보다 많이 통과한다는 점을 전제로 사용해야 합니다.

남아 있는 틈도 적어 둡니다. 클러스터 안의 파드는 게이트웨이의 Service에 로그인 토큰 없이 추론 요청을 보낼 수 있습니다. Gemma 파드의 8000 포트에는 NetworkPolicy를 걸지 않았고 CloudFront와 내부 ALB 사이는 VPC 안에서 HTTP로 통신합니다. 클러스터를 여러 팀이 함께 사용한다면 이 3곳부터 좁히는 것을 권고합니다.

## 11. 관측과 고정 비용

지표는 Prometheus agent 하나가 수집해 Amazon Managed Service for Prometheus로 보냅니다. agent 모드는 저장과 조회 없이 수집과 원격 쓰기만 하는 실행 방식입니다. 수집 대상은 vLLM 파드 2개(5초 주기), EPP 파드 4개, 게이트웨이 파드 2개(15초 주기)입니다. 이 글의 최적화를 운영하면서 볼 지표는 다음 5가지입니다.

| 볼 것 | 지표 | 관련 절 |
|---|---|---|
| 첫 토큰까지의 시간 | `vllm:time_to_first_token_seconds` | 우선순위, 동시 실행 |
| 토큰 간격 | `vllm:inter_token_latency_seconds` | 동시 실행 |
| 실행 중, 대기 중 요청 수 | `vllm:num_requests_running`, `vllm:num_requests_waiting` | 동시 실행, 우선순위 |
| KV 캐시 사용률 | `vllm:kv_cache_usage_perc` | 동시 실행 |
| MTP 수락률 | `vllm:spec_decode_num_accepted_tokens_total` ÷ `vllm:spec_decode_num_draft_tokens_total` | MTP |

*표 15. 모델별로 나눠 보는 지표. 이름은 vLLM v0.33.0 파드의 `/metrics`에서 확인했습니다.*

모든 구성 요소가 실행 중일 때의 고정 비용은 2026년 11월 15일 기준 시간당 약 10.05 USD로 추정됩니다. 그 가운데 앱 계층은 0.1857 USD입니다(내부 ALB 0.0225 USD, c7g.large 2대 0.1632 USD). 약 1.8%입니다. 사용량에 따라 부과되는 ALB 처리 단위, CloudFront 전송량, AWS WAF, Amazon Cognito 요금은 포함하지 않았습니다. GPU 노드는 실행 중인 동안 요금이 발생합니다. 서빙 파드를 0으로 줄이면 NodePool의 설정에 따라 30분 뒤 Karpenter가 빈 GPU 노드를 회수합니다.

## 12. 마치며

이 글의 구조를 여러분의 환경에 옮길 때 그대로 둘 것과 다시 정할 것을 나눠 정리합니다.

그대로 가져갈 만한 것은 3가지이고 모델과 GPU가 달라도 적용됩니다.

- 모델마다 NodePool을 두고 GPU 한도를 거는 구성
- 가중치를 S3에 한 번 올리고 서빙 파드는 EKS Pod Identity 권한으로 S3에서만 읽는 공급 경로
- 시작 시간을 4개 구간으로 나눠 측정하는 방법

모델이나 GPU가 다르면 다시 정할 것이 있습니다. 체크포인트의 양자화 형식은 GPU 세대가 지원하는 것으로 고릅니다. `--gpu-memory-utilization`은 기동 로그의 KV 캐시 크기를 보고 정합니다. compile 캐시는 구성이 바뀔 때마다 새 prefix로 게시합니다.

트래픽에 따라 정할 것도 있습니다. 동시에 겹치는 요청이 3건을 넘으면 MTP를 끄는 쪽을 검토합니다. 한 모델이 대화형 요청과 배치 요청을 함께 받으면 엔진 우선순위를 켭니다. 정해진 시간에만 사용하는 모델은 sleep으로 3.66초 복귀를 얻을지, 노드를 회수해 요금을 줄이고 콜드 스타트를 받아들일지를 고릅니다.

1부(TODO: Part 1 링크)는 이 구조 위에서 API 호출 한 건이 지나는 8개 단계를 따라가고 3부(TODO: Part 3 링크)는 이 환경을 처음부터 구축하는 순서를 다룹니다. 이 글의 구조도와 표가 여러분의 GPU 서빙 환경을 설계하는 데 실질적인 참고가 되기를 바랍니다.

## 참고 자료

- [Learn how EKS Pod Identity grants pods access to AWS services – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Accelerate model loading on Amazon EKS – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/ml-inference-fast-model-loading.html)
- [Use EKS-optimized accelerated Linux AMIs for GPU instances – Amazon EKS 사용 설명서](https://docs.aws.amazon.com/eks/latest/userguide/ml-eks-optimized-ami.html)
- [Amazon EC2 G6e Instances – 제품 페이지](https://aws.amazon.com/ko/ec2/instance-types/g6e/)
- [Restrict access with VPC origins – Amazon CloudFront Developer Guide](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-vpc-origins.html)
- [Rate-based rule caveats in AWS WAF – AWS WAF Developer Guide](https://docs.aws.amazon.com/waf/latest/developerguide/waf-rule-statement-type-rate-based-caveats.html)
- [Search the web using Amazon Bedrock AgentCore Web Search – Amazon Bedrock AgentCore Developer Guide](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/web-search-api.html)
- [Set up ingestion from an existing Prometheus server in Kubernetes on EC2 – Amazon Managed Service for Prometheus User Guide](https://docs.aws.amazon.com/prometheus/latest/userguide/AMP-onboard-ingest-metrics-existing-Prometheus.html)
- [NodePools – Karpenter 문서](https://karpenter.sh/docs/concepts/nodepools/)
- [NodeClasses – Karpenter 문서](https://karpenter.sh/docs/concepts/nodeclasses/)
- [Restrict Pod network traffic with Kubernetes network policies – Amazon EKS User Guide](https://docs.aws.amazon.com/eks/latest/userguide/cni-network-policy-configure.html)
- [Loading models with Run:ai Model Streamer – vLLM 문서](https://docs.vllm.ai/en/latest/models/extensions/runai_model_streamer/)
- [torch.compile integration – vLLM 문서](https://docs.vllm.ai/en/latest/design/torch_compile/)
- [Quantization – vLLM 문서](https://docs.vllm.ai/en/latest/features/quantization/)
- [Sleep Mode – vLLM 문서](https://docs.vllm.ai/en/latest/features/sleep_mode/)
- [Production Metrics – vLLM 문서 (v0.33.0)](https://docs.vllm.ai/en/v0.33.0/usage/metrics/)
- [MTP (Multi-Token Prediction) – vLLM 문서 (v0.33.0)](https://docs.vllm.ai/en/v0.33.0/features/speculative_decoding/mtp/)
- [vllm.config.scheduler – vLLM API 문서](https://docs.vllm.ai/en/latest/api/vllm/config/scheduler/)
- [single_type_kv_cache_manager.py – vLLM v0.33.0 소스](https://github.com/vllm-project/vllm/blob/v0.33.0/vllm/v1/core/single_type_kv_cache_manager.py)
- [Introduction – Gateway API Inference Extension 문서](https://gateway-api-inference-extension.sigs.k8s.io/)
- [Release v1.6.0 – Gateway API Inference Extension 릴리스 노트](https://github.com/kubernetes-sigs/gateway-api-inference-extension/releases/tag/v1.6.0)
- [Flow Control – llm-d v1.0.0 문서](https://github.com/llm-d/llm-d/blob/v1.0.0/docs/architecture/router/flow-control.md)
- [Multiple inference pools – agentgateway 문서](https://agentgateway.dev/docs/kubernetes/latest/documentation/llm/inference/multiple-inference-pools/)
- [strands-decider – GitHub 저장소](https://github.com/strands-labs/strands-decider)
- [ow-on-gpu – GitHub 저장소](https://github.com/whchoi98/ow-on-gpu)

*본문의 측정값은 2026년 11월 14일과 15일에 서울 리전(ap-northeast-2)의 한 환경에서 측정한 값이며 반복 횟수는 표마다 적었습니다. 금액은 2026년 11월 15일 기준 서울 리전의 On-Demand 가격으로 계산한 세전 USD 추정치입니다. 인스턴스 유형, 체크포인트, 버전, 워크로드, 측정 시점에 따라 결과는 달라질 수 있습니다.*

## 저자 소개

**최우형 (Woohyung Choi)** 님은 AWS Korea의 Principal Solutions Architect로, 국내 주요 엔터프라이즈 및 디지털 기업의 클라우드 전환과 아키텍처 현대화를 지원하고 있습니다. 특히 클라우드 네이티브 아키텍처와 Agentic AI 분야에 전문성을 가지고 있으며, 고객이 Amazon Bedrock을 비롯한 AWS의 생성형 AI 및 Agentic AI 기술을 안정적이고 비용 효율적으로 도입하고 확장할 수 있도록 아키텍처 설계와 기술 자문을 제공하고 있습니다.

컨테이너, 네트워킹, 비용 최적화를 비롯한 클라우드 핵심 기술부터 Agentic AI를 활용한 업무 혁신과 지능형 시스템 구축까지 폭넓은 영역에서 AWS 아키텍처 모범 사례를 제시하고 있습니다. 이를 통해 고객의 복잡한 기술적 과제를 해결하고, AI와 클라우드를 기반으로 지속 가능한 기술 전략을 수립하고 실행할 수 있도록 기술 리더십을 발휘하고 있습니다.
