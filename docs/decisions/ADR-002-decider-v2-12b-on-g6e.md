# ADR-002: Move the Decider to v2 12B on g6e.xlarge with an image built from the upstream Dockerfile

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

---

<a id="english"></a>

# English

## Status
Accepted (2026-11-24)

## Context
Strands Decider v2 was announced on 2026-11-23. Its five checkpoints are all built on Gemma 4, so the v1 model in use here (`strands-decider-2B-qwen3.5-v1-2610` on one g6.xlarge) has no v2 counterpart of the same base. The project owner decided to move to v2 and to change the Decider GPU to the g6e family.

Two facts shaped the rest. The upstream model pages recommend a GPU size for each v2 checkpoint (24 GB for E2B, 40 GB for E4B, 48 GB for 12B, 80 GB for 26B-A4B and 31B). And v2 checkpoints load only with `strands-decider` 0.4.0 or later, while the public serving image used for v1 still held 0.3.1.dev1 in its 2026-11-20 build, without the modules that read a v2 checkpoint.

## Options Considered

### Model and node

#### Option 1: 12B on g6e.xlarge
- **Pros**: The largest v2 checkpoint the upstream pages place on one 48 GB GPU. It scores higher than E4B on all five benchmarks those pages list. The node has the same GPU as the two serving nodes.
- **Cons**: 24 GB of weights to fetch at start. A single-question decision took a median of 88.6 ms, against about 70 ms for v1 on the L4.

#### Option 2: E4B on g6e.xlarge
- **Pros**: 16 GB of weights. It fits the same node with room to spare.
- **Cons**: Lower upstream scores than 12B, with a latency the upstream pages report as almost the same on an H100 (78 ms against 80 ms).

#### Option 3: E2B on the existing g6.xlarge
- **Pros**: No node change.
- **Cons**: The lowest upstream scores of the v2 sizes. It does not follow the decision to move to g6e.

### Image

#### Option A: Build the upstream Dockerfile at tag v0.4.0
- **Pros**: The path the upstream SageMaker guide gives for a package version the public image does not carry yet. The Dockerfile is used unchanged.
- **Cons**: An ECR repository and a build step to maintain. The workstation is arm64, so the build needs amd64 emulation.

#### Option B: Wait for the public image to carry 0.4.0
- **Pros**: Nothing to build.
- **Cons**: No date is known. The 2026-11-20 build came out after the 0.4.0 release and still held the older commit.

#### Option C: Put the 0.4.0 package over the public image at start
- **Pros**: No image to build.
- **Cons**: The package dependencies changed between the two versions, and the result would not be reproducible.

## Decision
Option 1 with Option A. The Decider runs `strands-decider-12B-gemma4-v2-2611` on one g6e.xlarge On-Demand node, from the image `ow-on-gpu/decider:0.4.0` built by `k8s/decider/install.sh build`. The ECR repository refuses to overwrite a tag. When the public image carries 0.4.0 or later, the Deployment goes back to it and the repository can be deleted.

## Consequences

### Positive
- Nine of the ten sample requests clear the BFF confidence threshold of 0.6, against seven with v1. The model chosen is the same for all ten.
- The BFF and `bench/decider/bench.py` are unchanged, because the response fields are the same.
- The base model is no longer uploaded or fetched.

### Negative
- `kubectl apply -k k8s/decider` no longer works. The image address holds the account ID, so `k8s/decider/install.sh` fills it in.
- A single-question decision is about 18.5 ms slower than v1. The BFF request with three questions took a median of 146.4 ms.
- The Decider did not answer for 5 minutes 40 seconds during the switch.
- The Decider node costs 1.2984 USD more per hour (g6.xlarge 0.9896, g6e.xlarge 2.2880, Seoul On-Demand, queried 2026-11-26). The estimated fixed cost of the environment goes from about 10.05 to about 11.35 USD per hour.
- The page and the infographics were updated on the same day, and the blog drafts on 2026-11-26.
- The v1 checkpoint and its base model remain in the bucket until they are deleted.

## References
- `docs/05-decider.md`
- `results/2026-11-24-decider-v2/`, `results/2026-11-24-model-sync/`
- [Introducing Strands Decider v2](https://strandsagents.com/blog/introducing-strands-decider-v2/)
- `AGENT.md`, confirmed decisions

---

<a id="korean"></a>

# 한국어

## 상태
채택 (2026-11-24)

## 배경
Strands Decider v2가 2026-11-23에 발표됐습니다. v2 체크포인트 다섯 개는 모두 Gemma 4 기반이어서, 이 환경이 쓰던 v1 모델(`strands-decider-2B-qwen3.5-v1-2610`, g6.xlarge 1대)과 같은 기반의 v2 모델이 없습니다. 프로젝트 소유자가 v2로 옮기고 Decider의 GPU를 g6e 계열로 바꾸기로 했습니다.

나머지는 두 가지 사실에서 정해졌습니다. 업스트림 모델 문서는 v2 체크포인트마다 GPU 크기를 권합니다(E2B 24GB, E4B 40GB, 12B 48GB, 26B-A4B와 31B 80GB). 그리고 v2 체크포인트는 `strands-decider` 0.4.0 이상에서만 읽히는데, v1에서 쓴 공개 서빙 이미지는 2026-11-20 빌드에도 0.3.1.dev1이 들어 있었고 v2 체크포인트를 읽는 모듈이 없었습니다.

## 검토한 옵션

### 모델과 노드

#### 옵션 1: g6e.xlarge에 12B
- **장점**: 업스트림 문서가 48GB GPU 한 장에 두는 가장 큰 v2 체크포인트입니다. 그 문서의 벤치마크 다섯 개 모두에서 E4B보다 점수가 높습니다. 서빙 노드 두 대와 GPU가 같습니다.
- **단점**: 시작할 때 가중치 24GB를 받아야 합니다. 질문 하나의 판단은 중앙값 88.6ms로, L4의 v1(약 70ms)보다 느립니다.

#### 옵션 2: g6e.xlarge에 E4B
- **장점**: 가중치가 16GB입니다. 같은 노드에 여유 있게 들어갑니다.
- **단점**: 업스트림 점수가 12B보다 낮고, 업스트림 문서의 H100 지연은 거의 같습니다(78ms와 80ms).

#### 옵션 3: 기존 g6.xlarge에 E2B
- **장점**: 노드를 바꾸지 않습니다.
- **단점**: v2 크기 가운데 업스트림 점수가 가장 낮습니다. g6e로 바꾸기로 한 결정과 맞지 않습니다.

### 이미지

#### 옵션 A: 업스트림 v0.4.0 태그의 Dockerfile로 빌드
- **장점**: 공개 이미지에 아직 없는 패키지 버전이 필요할 때 업스트림 SageMaker 가이드가 안내하는 방법입니다. Dockerfile을 고치지 않고 씁니다.
- **단점**: ECR 저장소와 빌드 단계를 관리해야 합니다. 작업 장비가 arm64라 빌드에 amd64 에뮬레이션이 필요합니다.

#### 옵션 B: 공개 이미지가 0.4.0을 담을 때까지 기다림
- **장점**: 빌드할 것이 없습니다.
- **단점**: 시점을 알 수 없습니다. 2026-11-20 빌드는 0.4.0 릴리스 뒤에 나왔는데도 이전 커밋을 담고 있었습니다.

#### 옵션 C: 공개 이미지 위에 0.4.0 패키지를 시작할 때 덮어씀
- **장점**: 이미지를 빌드하지 않습니다.
- **단점**: 두 버전 사이에 패키지 의존성이 바뀌었고, 결과를 다시 만들기 어렵습니다.

## 결정
옵션 1과 옵션 A입니다. Decider는 g6e.xlarge On-Demand 노드 1대에서 `strands-decider-12B-gemma4-v2-2611`을 실행하고, 이미지는 `k8s/decider/install.sh build`가 만든 `ow-on-gpu/decider:0.4.0`입니다. ECR 저장소는 같은 태그를 덮어쓰지 못하게 했습니다. 공개 이미지가 0.4.0 이상을 담으면 Deployment를 그 이미지로 되돌리고 저장소를 지울 수 있습니다.

## 영향

### 긍정적
- 예시 요청 10건 중 9건이 BFF의 신뢰도 기준 0.6을 넘습니다. v1은 7건이었습니다. 고른 모델은 10건 모두 같습니다.
- 응답 필드가 같아서 BFF와 `bench/decider/bench.py`를 고치지 않았습니다.
- 기반 모델을 올리거나 받지 않습니다.

### 부정적
- `kubectl apply -k k8s/decider`로 적용할 수 없습니다. 이미지 주소에 계정 ID가 들어가서 `k8s/decider/install.sh`가 채웁니다.
- 질문 하나의 판단이 v1보다 약 18.5ms 느립니다. 질문 세 개를 담은 BFF의 요청은 중앙값 146.4ms였습니다.
- 교체하는 5분 40초 동안 Decider가 응답하지 않았습니다.
- Decider 노드의 가격이 시간당 1.2984 USD 늘었습니다(g6.xlarge 0.9896, g6e.xlarge 2.2880, 서울 리전 On-Demand, 2026-11-26 조회). 환경 전체의 고정 비용 추정은 시간당 약 10.05 USD에서 약 11.35 USD가 됩니다.
- 화면과 인포그래픽은 같은 날 고쳤고 블로그 원고는 2026-11-26에 고쳤습니다.
- v1 체크포인트와 그 기반 모델은 지울 때까지 버킷에 남습니다.

## 참고 자료
- `docs/05-decider.md`
- `results/2026-11-24-decider-v2/`, `results/2026-11-24-model-sync/`
- [Introducing Strands Decider v2](https://strandsagents.com/blog/introducing-strands-decider-v2/)
- `AGENT.md`의 확정된 결정
