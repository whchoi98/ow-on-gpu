# model-sync: Hugging Face에서 S3로 체크포인트 적재

`models.json`에 적힌 저장소 네 개를 리비전 해시로 고정해 S3 버킷의 `models/` 아래에 올립니다. 서빙 파드는 Hugging Face에서 내려받지 않고 이 S3 경로만 읽습니다.

| 저장소 | S3 경로 | 객체 수 | 크기 |
|---|---|---|---|
| RedHatAI/gemma-4-31B-it-FP8-dynamic | `models/gemma-4-31B-it-FP8-dynamic/` | 18 | 33.30GB |
| AzatAI/Qwen3.8-27B-FP8-dynamic | `models/Qwen3.8-27B-FP8-dynamic/` | 14 | 36.80GB |
| StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 | `models/strands-decider-2B-qwen3.5-v1-2610/` | 29 | 0.23GB |
| Qwen/Qwen3.5-2B-Base | `models/Qwen3.5-2B-Base/` | 12 | 4.57GB |

합계는 객체 73개, 74.90GB입니다(`python3 sync.py --plan`으로 조회, 2026-11-14). `Qwen/Qwen3.5-2B-Base`는 Decider의 기반 모델입니다. Decider 저장소에는 LoRA 어댑터와 헤드만 있어서 함께 올립니다.

## 동작

- 파일을 받는 대로 `s5cmd pipe`로 S3에 올립니다. 로컬 디스크에 가중치를 쌓지 않습니다.
- 파일 8개를 동시에 처리하고, 파일마다 s5cmd가 64MiB 파트 4개를 병렬로 올립니다.
- 받으면서 해시를 계산해 Hugging Face가 알려 준 값과 비교합니다. LFS 파일은 sha256, 나머지는 git blob sha1입니다.
- 끝나면 S3의 객체 목록을 기대값(경로와 크기)과 비교하고, 다르면 Job이 실패합니다.
- 다시 실행하면 같은 크기로 이미 올라간 파일은 건너뜁니다. 건너뛴 파일의 내용은 다시 확인하지 않습니다.
- AWS 권한은 `model-jobs/model-sync` ServiceAccount에 연결된 쓰기 역할(EKS Pod Identity)만 씁니다. s5cmd 2.3.0의 AWS SDK가 Pod Identity를 지원하지 않아, 스크립트가 Pod Identity 에이전트에서 임시 자격 증명을 받아 s5cmd에 넘깁니다.
- Job은 system NodePool에서 실행합니다. 8 vCPU On-Demand 노드 한 대가 뜨고, Job이 끝난 뒤 30분 동안 비어 있으면 회수됩니다.

## 실행

```bash
export KUBECONFIG=~/my-project/ow-on-gpu/infra/terraform/.kubeconfig

kubectl apply -k jobs/model-sync
kubectl -n model-jobs logs -f job/model-sync
kubectl -n model-jobs wait --for=condition=complete job/model-sync --timeout=60m
```

`params.env`의 `BUCKET`은 `terraform -chdir=infra/terraform output -raw model_bucket` 값과 같아야 합니다.

다시 실행하려면 Job을 지우고 적용합니다. Job의 파드 템플릿은 바꿀 수 없기 때문입니다.

```bash
kubectl -n model-jobs delete job model-sync
kubectl apply -k jobs/model-sync
```

## 결과 저장

Job 로그는 한 줄에 JSON 하나입니다. `verified` 줄에 모델별 객체 수와 총 크기가, `summary` 줄에 전체 합계와 소요 시간이 있습니다. Job을 지우면 로그도 사라지므로 지우기 전에 저장합니다.

```bash
D=results/$(date +%F)-model-sync
mkdir -p "$D"
kubectl -n model-jobs logs job/model-sync > "$D/job.log"
grep -E '"event": "(verified|summary)"' "$D/job.log" > "$D/summary.jsonl"
kubectl -n model-jobs get job model-sync -o yaml > "$D/job.yaml"
aws s3 ls "s3://$(terraform -chdir=infra/terraform output -raw model_bucket)/models/" \
  --recursive --summarize > "$D/s3-listing.txt"
```

## 예상 소요 시간

전송 10분에서 12분에 노드와 파드 준비 시간이 더해질 것으로 예상합니다. 근거는 다음과 같습니다.

- 2026-11-14에 작업 장비(서울 리전)에서 Gemma 가중치 파일을 범위 요청으로 받아 측정했습니다. 연결 하나의 속도는 44.0MB/s와 44.4MB/s였고(1GiB씩 2회), 연결 4개를 동시에 열면 각각 40.2MB/s에서 41.1MB/s, 합계 160.6MB/s였습니다.
- 속도가 연결 단위로 제한되고 파일을 동시에 받으므로, 전체 시간은 가장 큰 파일이 정합니다. 가장 큰 파일은 26.89GB이고 40MB/s에서 44MB/s로 받으면 10.2분에서 11.2분입니다.
- 큰 파일은 7개입니다(Gemma 2개, Qwen 3개, 기반 모델 1개, Decider 어댑터 1개). 동시 처리 수 8 안에 들어갑니다.

측정하지 않은 부분도 있습니다. 측정은 EKS 노드가 아닌 작업 장비에서 했고, 연결 5개 이상에서의 속도와 S3 업로드 속도는 재지 않았습니다. 노드 프로비저닝과 이미지 pull 시간도 재지 않았습니다. 실제 값은 Job 로그의 `uploaded`와 `summary` 줄로 확인합니다.

## 실행 결과 (2026-11-14)

원시 자료는 `results/2026-11-14-model-sync/`에 있습니다.

| 항목 | 값 |
|---|---|
| Job 시작부터 완료까지 | 9분 8초 (10:06:16Z에서 10:15:24Z) |
| 적용부터 컨테이너 시작까지 | 53초 (노드 c7i-flex.2xlarge 프로비저닝과 이미지 pull 포함) |
| 전송과 검증 | 491.4초 |
| 올린 객체 | 73개, 74,904,971,631바이트. 네 저장소 모두 기대값과 일치 |
| 재시도 | 0회 |

- 전체 시간을 정한 파일은 Qwen의 19.98GB 파일이었고 40.7MB/s로 490초 걸렸습니다. Qwen 저장소의 큰 파일 세 개는 36.7MB/s에서 42.8MB/s로, 예상의 근거로 삼은 연결당 속도와 비슷했습니다.
- Gemma의 26.89GB 파일은 213.4MB/s로 126초 만에 끝났습니다. 작업 장비에서 같은 파일을 잰 값(44MB/s)의 약 다섯 배여서, 연결당 속도가 40MB/s대로 제한된다는 가정은 저장소에 따라 맞지 않았습니다.
- 적재 뒤 작업 장비에서 S3 객체 세 개를 다시 받아 sha256을 Hugging Face 값과 대조했고 모두 일치했습니다(`s3-sha256-spotcheck.txt`).
