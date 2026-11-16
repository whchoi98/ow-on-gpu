#!/usr/bin/env bash
# SLO 하 처리량. 2부와 같은 방법(vllm bench serve, random 데이터셋, 워크로드 4종, 동시성 7단계)으로
# 모델 하나를 잰다. 클러스터 안의 측정 파드에서 실행한다(bench/job.py).
# 측정 파드는 GPU가 없어서 `vllm bench serve` 대신 같은 벤치마크 모듈을 부르는 bench_serve.py를 쓴다.
#
# 환경 변수
#   MODEL_NAME     served model name (gemma-4-31b, qwen38-27b)
#   MODEL_DIR      S3의 models/ 아래 디렉터리 이름. 토크나이저를 여기서 받는다
#   BASE_URL       vLLM Service 주소. 2부처럼 게이트웨이를 거치지 않고 직접 부른다
#   SCENARIOS      기본은 네 가지 모두
#   CONCURRENCIES  기본은 1 2 4 8 16 32 64
set -uo pipefail

: "${MODEL_NAME:?}" "${MODEL_DIR:?}" "${BASE_URL:?}"
SCENARIOS=${SCENARIOS:-"S1_chat S2_summary S3_moderation S4_rag"}
CONCURRENCIES=${CONCURRENCIES:-"1 2 4 8 16 32 64"}
RESULTS_DIR=${RESULTS_DIR:-/results}
TOKENIZER_DIR=/tmp/tokenizer
mkdir -p "$RESULTS_DIR"

# 시나리오: 이름 -> "입력 토큰 수 출력 토큰 수" (2부의 bench/run-bench.sh와 같은 값)
declare -A SCEN=(
  [S1_chat]="256 128"
  [S2_summary]="1024 256"
  [S3_moderation]="512 16"
  [S4_rag]="4096 256"
)

# 랜덤 프롬프트를 만들 토크나이저. Hugging Face가 아닌 모델 버킷에서 받는다.
python3 /bench/fetch_tokenizer.py "$MODEL_DIR" "$TOKENIZER_DIR" || exit 1
python3 -c "import vllm; print(vllm.__version__)" | tee "$RESULTS_DIR/vllm-version.txt"

for s in $SCENARIOS; do
  read -r ILEN OLEN <<< "${SCEN[$s]}"
  for c in $CONCURRENCIES; do
    np=$(( c * 8 )); (( np < 16 )) && np=16; (( np > 256 )) && np=256
    echo "=============================================="
    echo ">>> $s  input=$ILEN output=$OLEN  concurrency=$c  num_prompts=$np  $(date -u +%H:%M:%S)"
    echo "=============================================="
    # 측정 전후의 vLLM 지표를 그대로 남긴다(KV 캐시 사용률, 선점 횟수, 서버 쪽 TTFT 분포 대조용).
    curl -s --max-time 5 "$BASE_URL/metrics" > "$RESULTS_DIR/${s}_c${c}.metrics-before.txt"
    python3 /bench/bench_serve.py \
      --backend openai \
      --base-url "$BASE_URL" \
      --model "$MODEL_NAME" \
      --tokenizer "$TOKENIZER_DIR" \
      --dataset-name random \
      --random-input-len "$ILEN" \
      --random-output-len "$OLEN" \
      --max-concurrency "$c" \
      --num-prompts "$np" \
      --percentile-metrics ttft,tpot,itl,e2el \
      --metric-percentiles 50,90,99 \
      --save-result \
      --save-detailed \
      --result-dir "$RESULTS_DIR" \
      --result-filename "${s}_c${c}.json" \
      2>&1 | tail -40
    rc=${PIPESTATUS[0]}
    curl -s --max-time 5 "$BASE_URL/metrics" > "$RESULTS_DIR/${s}_c${c}.metrics-after.txt"
    if [ "$rc" -ne 0 ]; then
      echo "!!! $s c=$c 실패 (rc=$rc). 다음 조합으로 넘어갑니다" | tee -a "$RESULTS_DIR/failures.log"
    fi
  done
done

echo "완료: $(ls "$RESULTS_DIR"/S*_c*.json 2>/dev/null | wc -l)개 결과"
