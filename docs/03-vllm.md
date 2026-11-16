# 3단계. vLLM 배포

2026-11-14에 Gemma와 Qwen을 g6e.4xlarge(L40S) On-Demand 노드에 한 대씩 배포했습니다. 아래 값은 모두 이날의 파드 로그와 명령 출력에서 뽑은 것이고, 원시 자료는 `results/2026-11-14-vllm-first-start/`에 있습니다. 각 항목은 한 번 실행한 결과입니다. 콜드 스타트 분해와 반복 측정은 8단계에서 합니다.

## 요약

| 항목 | Gemma 4 31B | Qwen3.8-27B |
|---|---|---|
| 체크포인트 | RedHatAI/gemma-4-31B-it-FP8-dynamic | AzatAI/Qwen3.8-27B-FP8-dynamic |
| `--gpu-memory-utilization` | 0.90으로 시작됨 | 0.85는 시작 실패, 0.90으로 시작됨 |
| 가중치 로드 시간 | 19.1초 | 34.3초 |
| 가중치가 차지한 GPU 메모리 | 30.63GiB | 34.39GiB |
| 엔진 초기화 시간 | 95.84초 (컴파일 61.03초 포함) | 57.85초 (컴파일 0.96초, 캐시 적중) |
| KV 캐시 메모리 | 5.37GiB | 2.46GiB |
| KV 캐시 크기 | 34,052 토큰 | 42,780 토큰 |
| 최대 길이 요청 기준 동시 처리 | 16,384 토큰 요청 2.08개 | 32,768 토큰 요청 1.31개 |
| 파드 생성부터 Ready까지 | 168초 | 약 135초 |

- 두 값 모두 노드가 이미 떠 있고 이미지가 받아진 상태에서 잰 것입니다. Gemma는 compile 캐시가 없는 첫 기동이고, Qwen은 앞선 실패 시도가 hostPath에 남긴 compile 캐시를 쓴 기동입니다. 두 모델의 Ready 시간을 서로 비교할 수 없습니다.
- Qwen의 Ready 시각은 Deployment가 Available이 된 시각으로 잡았습니다. 직후의 sleep 시험이 파드의 Ready 전이 시각을 덮어썼기 때문입니다.

## 이미지 안에서 확인한 것

배포 전에 GPU 노드에서 `vllm/vllm-openai:v0.33.0`을 실행해 확인했습니다(`image-check.log`).

- 버전: vllm 0.33.0, torch 2.14.0+cu130, transformers 5.20.2, compressed-tensors 0.17.0, runai-model-streamer 0.17.1, boto3 1.43.123, Python 3.12.3.
- GPU: NVIDIA L40S, 46,068MiB, 드라이버 580.178.04, compute capability 8.9.
- `vllm serve --help=all`에 AGENT.md의 플래그 14개가 모두 있습니다. `--kv-cache-dtype`의 값에 `fp8`이, `--tool-call-parser`의 값에 `gemma4`와 `qwen3_coder`가 있습니다.
- boto3가 EKS Pod Identity로 자격 증명을 받아(`container-role`) 모델 버킷을 나열했습니다.

## 노드와 이미지

- Gemma 노드는 NodeClaim 생성 118초 뒤에 Ready가 됐습니다(10:31:13Z에서 10:33:11Z).
- EC2NodeClass의 사전 pull은 동작했습니다. containerd가 뜬 직후 시작해 9.1GiB를 108.7초에 받았고(85.5MiB/s), kubelet의 pull은 진행 중인 다운로드를 이어받아 사전 pull이 끝난 1초 뒤에 끝났습니다(kubelet 기준 45.0초).
- Qwen 노드에서는 kubelet 기준 pull이 71.4초였습니다.
- 로컬 NVMe는 RAID0으로 묶여 `/mnt/k8s-disks/0`(559GB)에 마운트됐고 이미지가 여기에 저장됩니다. 루트 볼륨은 20GB입니다.

## Gemma

`--gpu-memory-utilization=0.90`으로 첫 시도에 시작됐습니다. 0.85로 낮출 필요가 없었습니다.

| 구간 | 값 | 로그 |
|---|---|---|
| compile 캐시 복원 | 0.24초, 객체 0개(캐시 없음) | initContainer |
| 가중치 로드 | 19.1초, 30.63GiB | `Model loading took 30.63 GiB memory and 19.106861 seconds` |
| torch.compile | 61.03초 | `[backbone] torch.compile took 61.03 s in total` |
| CUDA graph 캡처 | 15초와 11초 | `Graph capturing finished in 15 secs`, `in 11 secs` |
| 엔진 초기화 전체 | 95.84초 | `init engine (profile, create kv cache, warmup model) took 95.84 s (compilation: 61.03 s)` |

GPU 메모리는 다음과 같이 나뉩니다(`Free memory on device` 줄).

- 시작 시 여유 43.87GiB(전체 44.39GiB), 0.90의 목표는 39.95GiB입니다.
- 가중치와 비 torch 메모리 31.13GiB, 활성값 최대 3.45GiB, CUDA graph 0.35GiB.
- KV 캐시에 5.37GiB가 남아 34,052 토큰을 담습니다. 16,384 토큰 요청으로는 2.08개 분량입니다.
- 기동 후 `nvidia-smi`의 사용량은 38,895MiB입니다.

그 밖의 관찰입니다.

- 어텐션 백엔드는 TRITON_ATTN입니다. 로그는 "Gemma4 model has heterogeneous head dimensions ... FA4 not available, forcing TRITON_ATTN backend"입니다.
- 응답 확인: 한국어 질문에 정상 응답했고, `get_order` 도구 호출이 `{"order_id": "A-1024"}`로 나왔습니다. 응답 끝에 `<turn|>`이 붙지 않았습니다. 본문 `priority` 필드도 받습니다(`gemma-smoke.txt`).

## Qwen

### 0.85에서는 시작하지 못했습니다

AGENT.md의 시작값(`--gpu-memory-utilization=0.85`)으로는 엔진이 시작하지 못했습니다(`qwen-0.85-failed.log`).

- 가중치가 34.39GiB를 차지해 KV 캐시에 0.24GiB만 남았습니다.
- 오류는 "To serve at least one request with the model's max seq len (32768), (1.87 GiB KV cache is needed, which is larger than the available KV cache memory (0.18 GiB)"입니다.
- 남은 메모리가 0.18GiB라서 `--max-model-len`을 줄이는 것만으로는 해결되지 않습니다.
- 컨테이너가 두 번 다시 시작된 뒤 Deployment를 0으로 줄여 반복을 멈췄습니다. 첫 번째 컨테이너의 로그는 남지 않아, compile 캐시가 없는 상태의 컴파일 시간은 기록하지 못했습니다.

### 0.90에서 시작됐습니다

`--gpu-memory-utilization=0.90`으로 올리자 sleep mode를 켠 채로 시작됐습니다(`qwen-0.90.log`). AGENT.md에는 g7e에서 sleep mode와 0.90 조합이 시작에 실패했다고 적혀 있는데, L40S에서는 시작됩니다.

| 구간 | 값 | 로그 |
|---|---|---|
| 가중치 로드 | 34.3초, 34.39GiB | `Model loading took 34.39 GiB memory and 34.302296 seconds` |
| torch.compile | 0.90초와 0.06초(캐시 적중) | `[backbone] torch.compile took 0.90 s`, `[eagle_head] ... 0.06 s` |
| CUDA graph 캡처 | 11초와 12초 | `Graph capturing finished in 11 secs`, `in 12 secs` |
| 엔진 초기화 전체 | 57.85초 | `init engine (profile, create kv cache, warmup model) took 57.85 s (compilation: 0.96 s)` |

- GPU 메모리: 가중치와 비 torch 메모리 34.74GiB, 활성값 최대 2.76GiB, CUDA graph 0.58GiB.
- KV 캐시에 2.46GiB가 남아 42,780 토큰을 담습니다. 32,768 토큰 요청으로는 1.31개 분량입니다. 로그는 GPU를 끝까지 쓰면 KV 캐시를 5.65GiB까지 늘릴 수 있다고 안내합니다.
- FP8 커널은 `CutlassFP8ScaledMMLinearKernel`이 선택됐습니다. per-channel 체크포인트는 Ada에서 CUTLASS 커널을 씁니다.
- MTP는 모델 자신의 헤드로 동작합니다(`Resolved architecture: Qwen3_5MTP`). 짧은 요청 세 번에서 드래프트 토큰 39개 중 39개가 수락됐습니다. 표본이 작아 수락률로 쓰기에는 부족하고, 0이 아니라는 것만 확인됩니다.
- 응답 확인: 한국어 질문에 정상 응답했고 `get_order` 도구 호출이 나왔습니다(`qwen-smoke.txt`).

### sleep 진입과 복귀

파드 안에서 `/sleep?level=1`과 `/wake_up`을 한 번씩 호출했습니다(`qwen-sleep-wake.txt`).

| 항목 | 값 |
|---|---|
| level 1 sleep 진입 | 31.71초 |
| sleep 중 GPU 메모리 | 40,791MiB에서 2,299MiB로 감소 |
| sleep 중 `/health` | HTTP 200 |
| sleep 중 `/is_sleeping` | `true`, 파드는 NotReady로 전환 |
| 복귀(`/wake_up`) | 3.64초 |
| 복귀 후 GPU 메모리 | 40,899MiB |
| 복귀 후 응답 | 정상(0.22초) |

- v0.26.0에서 보고된 하이브리드 모델의 복귀 실패는 v0.33.0에서 `--kv-cache-dtype=fp8`을 쓰는 이 구성에 나타나지 않았습니다.
- sleep을 한 번 거친 뒤 컨테이너 메모리는 60.4GiB였고 그중 공유 메모리가 54.9GiB였습니다(cgroup `memory.current`, `memory.stat`). `/dev/shm`은 비어 있습니다. AGENT.md의 "약 30GiB"보다 큽니다.
- 진입과 복귀 시간은 한 번 잰 값입니다. 6단계에서 다시 측정합니다.

## compile 캐시

첫 기동 뒤 `jobs/cache-publish`로 hostPath의 캐시를 S3에 올렸습니다.

| 모델 | S3 prefix | 객체 수 | 크기 |
|---|---|---|---|
| Gemma | `vllm-cache/v0.33.0-gemma4-31b-fp8-l40s/` | 522 | 90.8MB |
| Qwen | `vllm-cache/v0.33.0-qwen38-27b-fp8-l40s/` | 2,056 | 216.7MB |

- vLLM은 `VLLM_CACHE_ROOT` 아래에 `torch_compile_cache/`와 `modelinfos`를 만듭니다. S3의 모델 설정 파일 사본은 `/root/.cache/vllm/assets/`에 따로 받으므로 hostPath에는 들어가지 않습니다.
- initContainer가 이 prefix를 새 노드로 복원했을 때 컴파일 시간이 얼마나 줄어드는지는 아직 재지 않았습니다. 8단계의 콜드 최적화 시나리오에서 측정합니다.

## AGENT.md의 시작 설정과 달라진 점

- Qwen의 `--gpu-memory-utilization`을 0.85에서 0.90으로 올렸습니다.
- 두 모델에 `--served-model-name`(`gemma-4-31b`, `qwen38-27b`)을 줬습니다.
- 환경 변수 `RUNAI_STREAMER_NO_BOTO3_SESSION=0`과 `HF_HUB_OFFLINE=1`을 뒀습니다. 앞의 것은 S3 자격 증명을 boto3로 받게 하고, 뒤의 것은 Hugging Face 접근을 막습니다.
- Qwen 노드를 Spot에서 On-Demand로 바꿨습니다(NodePool `qwen-od`).

## 다음 단계에 영향을 주는 점

- KV 캐시가 작습니다. Gemma는 34,052 토큰, Qwen은 42,780 토큰이어서 긴 요청이 겹치면 대기가 생깁니다. Qwen은 `--max-num-seqs=32`보다 KV 캐시가 먼저 한도가 됩니다. 8단계의 SLO 처리량이 이 값에 묶일 가능성이 큽니다.
- Qwen의 여유를 늘리는 방법은 세 가지입니다. `--gpu-memory-utilization`을 더 올리거나, `--max-model-len`을 줄이거나, 가중치가 5.9GB 작은 공식 block FP8 체크포인트로 바꾸는 것입니다. 마지막 방법은 Ada에서 느린 커널을 씁니다.
- GuardDuty 에이전트가 GPU 노드에도 떠 있습니다. 콜드 스타트 측정의 조건으로 기록해 둡니다.
