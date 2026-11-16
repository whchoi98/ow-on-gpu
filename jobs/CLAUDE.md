# jobs 모듈

## Role

모델 가중치와 compile 캐시를 S3에 올리는 Job입니다. 서빙 파드는 Hugging Face에서 직접 내려받지 않고 여기서 올린 S3 객체만 읽습니다. 네임스페이스는 `model-jobs`입니다.

## Key Files

| 파일 | 내용 |
|---|---|
| `model-sync/sync.py` | Hugging Face 저장소의 파일을 S3로 스트리밍 적재(`s5cmd pipe`). s5cmd가 EKS Pod Identity를 쓰지 못해 에이전트에서 자격 증명을 직접 받음 |
| `model-sync/models.json` | 적재할 저장소 목록 |
| `model-sync/job.yaml`, `params.env`, `kustomization.yaml` | Job 매니페스트와 값 |
| `model-sync/README.md` | 적재 방법과 확인 |
| `cache-publish/cache-publish.py`, `jobs.yaml` | 노드의 hostPath에 있는 compile 캐시를 S3에 게시 |

## Rules

- S3 경로는 `AGENT.md`의 "S3 구조"를 따릅니다. compile 캐시 prefix에는 vLLM 버전, 모델, 정밀도, GPU 아키텍처를 넣고, 구성이 하나라도 바뀌면 새 prefix로 게시합니다
- 적재 뒤에는 객체 수와 크기를 확인하고 출력을 `results/<날짜>-<항목>/`에 남깁니다
- Hugging Face 토큰이 필요하면 코드와 매니페스트에 넣지 않습니다
- `model-sync/params.env`(모델 버킷 이름)는 추적하지 않습니다. 추적하는 것은 `model-sync/params.env.example`입니다. 값은 `terraform output -raw model_bucket`으로 채웁니다
- Job을 실행하기 전에 `kubectl diff`를 보여 주고 승인을 받습니다
- 모델 목록이나 경로를 바꾸면 `AGENT.md`와 `docs/03-vllm.md`를 함께 고칩니다
