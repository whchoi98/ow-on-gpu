# bench 모듈

## Role

측정 스크립트입니다. 콜드 스타트, sleep 복귀, 구간별 TTFT, SLO 하 처리량, 우선순위 효과를 재고, 배포 뒤의 동작을 확인합니다. 방법과 결과는 `docs/08-results.md`에 있고 원시 자료는 `results/<날짜>-<항목>/`에 있습니다.

## Key Files

| 파일 | 내용 |
|---|---|
| `job.py` | 클러스터 안에서 도는 측정의 실행기. 측정 전용 NodePool `bench`에서 Job으로 실행 |
| `coldstart/measure.py`, `coldstart/k8s/` | 콜드 스타트를 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화로 나눠 측정. 기준 구성은 1부와 같은 Mountpoint FUSE |
| `sleep/measure.py` | Qwen의 sleep과 깨우기 시간 |
| `ttft/segments.py` | 첫 토큰까지의 시간을 구간별로 나눔 |
| `slo/bench_serve.py`, `slo/run-bench.sh`, `slo/summarize.py` | SLO를 지키는 최대 처리량. `vllm bench serve`는 GPU 없는 노드에서 시작하지 못해 벤치마크 모듈을 직접 부름 |
| `slo/k8s/` | 원인 확인용 구성(prefix caching 끔, MTP 끔) |
| `priority/run.py` | 배치 부하가 있을 때 interactive 요청의 TTFT |
| `decider/bench.py` | Decider의 판단 시간 |
| `bff/websearch_check.py`, `bff/stream_check.py`, `bff/waf_rate_check.sh` | CloudFront 주소로 하는 배포 뒤 확인(로그인 필요) |
| `bff/lang_check_live.py` | 토큰 없는 요청과 가짜 토큰으로 하는 라이브 확인(비밀번호 불필요) |
| `bff/lang_check_in_pod.py` | BFF 파드 안에서 같은 앱을 띄워 실제 모델까지 보내는 확인(비밀번호 불필요) |

## Rules

- 측정값을 추정하거나 만들어 내지 않습니다. 측정하지 않은 수치는 문서에 쓰지 않습니다
- 스크립트의 출력과 원시 로그는 `results/<날짜>-<항목>/`에 저장합니다. 커밋하기 전에 `python3 scripts/mask-identifiers.py results/<날짜>-<항목>`으로 환경 식별 값(계정 ID, ARN, CloudFront와 로드 밸런서 주소, 리소스 ID, 공인 IP)을 가립니다. 사용자 식별자도 남기지 않습니다. 커밋 전 검사가 가리지 않은 값을 막습니다
- `coldstart/k8s/storage-s3.yaml`(모델 버킷 이름)은 추적하지 않습니다. 추적하는 것은 `coldstart/k8s/storage-s3.yaml.example`입니다
- 측정용 노드나 GPU 노드가 뜨는 측정은 실행 전에 그 사실을 따로 알리고 승인을 받습니다
- 평일 19:00부터 08:30까지(Asia/Seoul)는 Qwen이 잠들어 있습니다. 그 시간대에 Qwen을 재려면 CronJob `qwen-sleep`을 suspend합니다
- CloudFront 주소로 부하를 걸 때는 `waf_rate_limit`을 올리거나 측정 장비를 예외로 둡니다. 넘기면 그 IP의 요청이 한동안 403입니다
- 동작 확인(요청마다 한 번)과 측정(반복해서 통계를 냄)을 구분해 적습니다
- 측정 조건이 달라졌으면 문서에 조건을 함께 적습니다. 2026-11-16부터 모든 노드에 `cloudwatch-agent`가, GPU 노드에 `dcgm-exporter`가 실행 중입니다(`docs/07-bff.md`)
