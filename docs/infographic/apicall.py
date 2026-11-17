"""LLM API 호출 한 건의 여정 인포그래픽. aws-infographic 스킬의 infokit으로 그린다.

  landscape(theme)  16:9 인포그래픽 한 장 (buildkit이 SVG와 PNG로 만든다)
  web_data()        웹 화면(app/web의 "API 호출" 보기)이 쓰는 값. 단계 카드의 위치와 측정값을 담는다
  use(lang)         그릴 언어를 고른다("ko" 또는 "en"). 카드의 위치는 같고 글만 바뀐다. 영어판은 apicall_en.py가 만든다

구성은 reference/L300-01-api-journey의 8단계를 따르고, 단계마다 이 환경에서 그 일을 하는 구성 요소와
이 환경에서 잰 값을 적는다. 수치는 모두 M에 모아 두고 그림과 웹 화면이 같은 값을 쓴다.

수치의 출처
  구간별 값       docs/08-results.md 2절 (CloudFront 경유, 모델마다 20건을 하나씩 보낸 중앙값, BFF를 EKS 파드로 옮긴 뒤인 2026-11-15의 재측정)
                  decide는 BFF의 판단 시간, wake_check는 깨우기 API 확인 시간의 중앙값이다. decider_ms는 BFF가 잰 Decider 왕복 4건의 범위다.
  s1              docs/08-results.md 3절과 results/2026-11-14-slo/<모델>/S1_chat_c1.json (입력 256, 출력 128, 동시성 1)
  메모리          docs/03-vllm.md (기동 로그)
  Decider, 비용   docs/07-bff.md
  우선순위        docs/08-results.md 4절
  웹 검색         docs/10-web-search.md (작업 장비에서 잰 값과, 배포 뒤 BFF가 잰 검색 시간)
지표의 정의는 vLLM 문서(https://docs.vllm.ai/en/latest/design/metrics.html), L40S의 메모리는
NVIDIA 제품 페이지(https://www.nvidia.com/en-us/data-center/l40s/)에서 확인했다.
"""
from infokit import CODE_FAMILY, Doc, card, cw, dot_list, footer_note, header, rw, section, tag

W, H = 1920, 1080

M = {
    "gemma": {
        "name": "Gemma 4 31B",
        "edge": 1.8, "cloudfront": 5.0, "alb": 1.6, "bff": 0.1, "decide": 0.1, "gateway": 9.7,
        "vllm_ttft": 63.2, "queue": 0.0, "prefill": 58.8, "headers": 19.8, "first_content": 81.9,
        "s1": {"ttft": 81.3, "ttft_p99": 86.6, "itl": 54.0, "itl_p99": 57.7, "tpot": 53.91, "e2e": 6927.8,
               "tokens_per_s": 18.5, "running_max": 45},
        "s4_ttft_p99": 1093.2,
        "weights_gib": 30.63, "kv_gib": 5.37, "kv_tokens": 34052, "max_model_len": 16384,
    },
    "qwen": {
        "name": "Qwen3.8-27B",
        "edge": 1.9, "cloudfront": 5.0, "alb": 1.6, "bff": 12.8, "decide": 0.1, "wake_check": 12.8, "gateway": 8.4,
        "vllm_ttft": 147.6, "queue": 0.0, "prefill": 144.4, "headers": 32.4, "first_content": 177.5,
        "s1": {"ttft": 167.6, "ttft_p99": 210.4, "itl": 69.8, "itl_p99": 74.3, "tpot": 26.64, "e2e": 3554.7,
               "tokens_per_s": 32.5, "running_max": 3},
        "weights_gib": 34.39, "kv_gib": 2.46, "kv_tokens": 42780, "max_model_len": 32768,
    },
    "device_gib": 44.39,
    "epp_ms": 0.03,
    "decider_ms": [139, 150],
    "priority_ttft_ms": {"none": 30895, "engine": 190},
    "fixed_cost_usd_per_hour": 10.05,
    "s1_output_tokens": 128,
    # 웹 검색(Amazon Bedrock AgentCore Web Search). 검색 시간은 작업 장비(서울)에서 us-east-1을 부른 값이다.
    "search": {
        "region": "us-east-1", "results": 5, "text_chars": 1200, "max_rounds": 3,
        "ms": [481, 1065],
        "input_tokens": {"gemma": 2606, "qwen": 4328},
        "searches": {"gemma": 1, "qwen": 2},
        "qwen_round_s": [2.6, 12.1],
        "usd_per_1000": 7, "quota_per_s": 10,
        # 배포 뒤 BFF가 잰 검색 시간(요청 8건, results/2026-11-15-websearch/bff-search-ms.json). 그림에는 쓰지 않고 화면에만 쓴다.
        "bff_ms": [485, 662], "bff_median_ms": 568, "bff_n": 8,
    },
}


def entry(model):
    """진입 구간: 사용자와 엣지 사이, CloudFront, ALB의 중앙값 합."""
    m = M[model]
    return round(m["edge"] + m["cloudfront"] + m["alb"], 1)


def routing(model):
    """라우팅 구간: BFF와 게이트웨이(agentgateway, EPP)의 중앙값 합."""
    m = M[model]
    return round(m["bff"] + m["gateway"], 1)


def share(model):
    """사용자가 본 첫 내용까지의 시간에서 vLLM이 차지하는 비율(%)."""
    m = M[model]
    return round(m["vllm_ttft"] / m["first_content"] * 100)


def num(value, digits=1):
    return f"{value:,.{digits}f}"


G, Q, S = M["gemma"], M["qwen"], M["search"]
E2E_CHECK = G["s1"]["ttft"] + (M["s1_output_tokens"] - 1) * G["s1"]["tpot"]
assert abs(E2E_CHECK - G["s1"]["e2e"]) < 1.0, E2E_CHECK  # E2E = TTFT + (출력 토큰 - 1) x TPOT

# 단계 카드의 위치 (x, y, w, h). 웹 화면이 같은 값으로 그림 위에 누를 수 있는 영역을 놓는다.
ROW1 = (148, 316)
ROW2 = (488, 300)
ROW3 = (812, 232)
W4, GAP = 429, 36
# 5단계부터는 왼쪽에 웹 검색 경로(LANE)를 세로로 두고, 그 오른쪽에 단계 카드를 놓는다.
LANE = (48, ROW2[0], 250, ROW3[0] + ROW3[1] - ROW2[0])
X2 = LANE[0] + LANE[2] + 26
W2 = 48 + 1824 - X2
W3 = (W2 - 2 * GAP) / 3
REGIONS = {
    1: (48, ROW1[0], W4, ROW1[1]),
    2: (48 + (W4 + GAP), ROW1[0], W4, ROW1[1]),
    3: (48 + 2 * (W4 + GAP), ROW1[0], W4, ROW1[1]),
    4: (48 + 3 * (W4 + GAP), ROW1[0], W4, ROW1[1]),
    5: (X2, ROW2[0], W2, ROW2[1]),
    6: (X2, ROW3[0], W3, ROW3[1]),
    7: (X2 + (W3 + GAP), ROW3[0], W3, ROW3[1]),
    8: (X2 + 2 * (W3 + GAP), ROW3[0], W3, ROW3[1]),
}

T = dict(
    title="LLM API 호출 한 건의 여정",
    sub_en="Inside an LLM API Call on ow-on-gpu",
    sub_ko="단계마다 이 환경에서 그 일을 하는 구성 요소와 측정값",
    budget=("Latency Budget", "첫 내용까지의 시간, 요청 1건씩 보낸 중앙값",
            f"{share('gemma')}~{share('qwen')}%가 vLLM"),
    budget_parts=("진입", "라우팅"),
    measured="측정",                 # 측정값 앞에 붙이는 이름표
    label_w=dict(s3=48, s4=58),      # 이름표 열의 폭(가장 긴 이름표에 맞춘다)
    s1=("API Gateway", "요청 진입: 암호화, 제한, 인증, 검증"),
    s1_rows=[
        ("service/Amazon-CloudFront", "CloudFront", "HTTPS 수신, /v1/* 을 내부 ALB로 전달"),
        ("service/AWS-WAF", "AWS WAF", "IP당 5분 300회 초과 시 403"),
        ("service/Amazon-Cognito", "Cognito", "액세스 토큰 발급, 가입 차단"),
        ("service/Amazon-Elastic-Kubernetes-Service", "BFF", "토큰 검증 401, 본문 검증 400"),
    ],
    s1_measure=f"엣지까지 {num(G['edge'])}ms, CloudFront {num(G['cloudfront'])}ms",
    s1_note=("429는 게이트웨이에서 발생", "풀 포화 시 배치 요청만 거절"),
    s2=("Load Balancer", "BFF 파드와 게이트웨이 파드로 분산"),
    s2_rows=[
        ("service/Elastic-Load-Balancing", "내부 ALB", "BFF 파드 2개, 쿠키 고정 30분"),
        ("service/Amazon-Elastic-Kubernetes-Service", "Service", "BFF가 게이트웨이를 직접 호출"),
        ("service/Amazon-Elastic-Kubernetes-Service", "agentgateway", "파드 2개, 본문의 model로 풀 선택"),
        ("service/Amazon-Elastic-Kubernetes-Service", "헬스체크", "/healthz, 잠든 Qwen은 대상 제외"),
    ],
    s2_measure=f"ALB {num(G['alb'])}ms, 게이트웨이 구간 {num(G['gateway'])}ms",
    s2_note=("GPU 부하 기반 파드 선택은 4단계", "EPP가 InferencePool 안에서 결정"),
    s3=("Tokenization", "vLLM API 서버가 토큰화, 길이 확인"),
    s3_bubble=("반품은 며칠 안에", "신청해야 하나요"),
    s3_ids=("Token IDs (예시)", "2  1045  9873  412", "236  5521  88  107"),
    s3_rows=[
        ("위치", "vLLM API 서버, 모델 파드 안"),
        ("한도", f"Gemma {G['max_model_len']:,}, Qwen {Q['max_model_len']:,}토큰"),
        ("측정", "토큰화 시간은 따로 재지 않음"),
    ],
    s3_note=("이 환경의 순서는 4 다음 3", "라우팅은 토큰화 없이 헤더와 원문으로 결정"),
    s4=("Model Router", "BFF가 모델 결정, EPP가 파드 선택"),
    s4_models=[("Gemma 4 31B", "상담, 번역, 요약"), ("Qwen3.8-27B", "코딩, 이미지")],
    s4_rows=[
        ("결정", "민감 규칙 > 업무 > 첨부 > Decider > 기본값"),
        ("파드", f"GAIE InferencePool, EPP {M['epp_ms']}ms"),
        ("대기열", "vLLM priority 스케줄러, 상담 0, 배치 10"),
        ("측정", f"BFF {num(G['bff'])}ms, Decider {M['decider_ms'][0]}~{M['decider_ms'][1]}ms"),
    ],
    s4_note=f"배치 부하 중 상담 TTFT p50: {M['priority_ttft_ms']['none'] / 1000:.1f}초 → "
            f"{M['priority_ttft_ms']['engine'] / 1000:.2f}초",
    s5=("Inference Engine", "vLLM v0.33.0, 모델마다 L40S 1장에서 토큰 생성"),
    a=("Prefill", "입력 토큰을 한 번에 처리, KV 캐시 기록"),
    a_kv="KV 캐시 기록",
    a_lines=[
        f"→ TTFT를 좌우: Gemma {num(G['prefill'])}ms, Qwen {num(Q['prefill'])}ms (짧은 입력)",
        f"입력 256토큰 {num(G['s1']['ttft_p99'])}ms, 4,096토큰 {num(G['s4_ttft_p99'], 0)}ms (Gemma TTFT p99)",
    ],
    b=("Decode", "토큰 생성 반복: Attention, FFN, Sampling"),
    b_boxes=[("Attention", "KV 캐시 조회"), ("FFN", "층마다 변환"), ("Sampling", "다음 토큰 선택")],
    b_loop="새 토큰을 입력에 더해 반복 (KV 캐시 재사용)",
    b_lines=[
        f"→ Chunk 간격: Gemma {num(G['s1']['itl'])}ms (초당 {num(G['s1']['tokens_per_s'])}토큰), "
        f"Qwen {num(Q['s1']['itl'])}ms",
        f"Qwen은 MTP로 Chunk에 여러 토큰, 토큰당 {num(Q['s1']['tpot'])}ms (초당 {num(Q['s1']['tokens_per_s'])}토큰)",
    ],
    c=("Hardware", "L40S 48GB 1장"),
    c_caption=f"GDDR6 48GB 중 사용 가능 {M['device_gib']}GiB",
    c_bars=[
        ("Gemma", G["weights_gib"], G["kv_gib"], f"가중치 {G['weights_gib']}, KV 캐시 {G['kv_gib']}GiB"),
        ("Qwen", Q["weights_gib"], Q["kv_gib"], f"가중치 {Q['weights_gib']}, KV 캐시 {Q['kv_gib']}GiB"),
    ],
    c_line=f"동시 실행 한도: Gemma {G['s1']['running_max']}건, Qwen {Q['s1']['running_max']}건",
    side=[
        "첫 내용까지 시간의",
        f"{share('gemma')}~{share('qwen')}%가 vLLM",
        "E2E ≒ TTFT",
        "+ (출력 토큰 - 1) × TPOT",
        f"{num(G['s1']['ttft'])} + 127 × {G['s1']['tpot']}",
        f"≒ {num(G['s1']['e2e'], 0)}ms (Gemma S1)",
    ],
    s6=("Post-processing", "텍스트 복원, 추론과 도구 호출 분리"),
    s6_items=[
        ("Detokenize", "토큰 ID → 텍스트", "vLLM, Chunk 단위"),
        ("Reasoning parser", "gemma4, qwen3", "reasoning_content 분리"),
        ("Tool-call parser", "gemma4, qwen3_coder", "tool_calls 추출"),
    ],
    s6_code="finish_reason: stop / length / tool_calls",
    s6_line="출력 안전 필터 없음, 도구는 BFF가 실행 후 다시 요청 (최대 3회)",
    s7=("Response & Billing", "SSE 전달, 과금은 GPU 시간"),
    s7_bullets=[
        "stream=true: BFF가 받은 Chunk를 바로 전달",
        "마지막 Chunk의 usage: 입력, 출력 토큰 수",
        "응답 헤더: x-bff-model, x-bff-timing",
        "웹 검색 답변: [1], [2] 번호와 출처 목록",
    ],
    s7_pink=("토큰 단가 없음", "출력이 길수록", "GPU 점유 시간 증가"),
    s7_cost=f"비용 = GPU 노드 시간 × 단가, 이 환경은 시간당 약 {M['fixed_cost_usd_per_hour']}달러",
    s8=("Logging & Observability", "AMP와 구간별 로그"),
    s8_items=[
        ("service/Amazon-Managed-Service-for-Prometheus", "AMP", "agent가 지표 전송"),
        ("service/Amazon-EC2", "vLLM 지표", "TTFT, 대기열, KV 캐시"),
        ("service/Amazon-Elastic-Kubernetes-Service", "EPP, 게이트웨이", "스케줄링, 요청 수"),
        ("service/Amazon-Elastic-Kubernetes-Service", "BFF 로그", "파드 표준 출력"),
        ("service/Amazon-Simple-Storage-Service", "ALB 접근 로그", "S3 버킷에 저장"),
        ("service/Amazon-CloudFront", "Server-Timing", "CloudFront 응답 헤더"),
    ],
    s8_line="요청 ID와 X-Amzn-Trace-Id로 구간 기록을 요청마다 연결",
    lane=("선택 경로", "Web Search 도구", "x-web-search: on 요청에만 추가", "민감 요청, 성능 평가 요청은 제외"),
    lane_steps=dict(
        again=("다시 추론", "결과를 붙여 5로 재요청", f"상한 {S['max_rounds']}회, 끝은 tool_choice: none"),
        number=("결과 정리", f"결과 {S['results']}건에 출처 번호 부여", f"본문은 {S['text_chars']:,}자까지 전달"),
        search=("AgentCore Web Search", f"InvokeWebSearch, {S['region']}", "Pod Identity 역할의 권한으로 호출"),
        run=("도구 실행", "BFF", "6이 뽑은 tool_calls 수신", "web_search(query)", "민감 검색어는 차단"),
    ),
    lane_notes=[
        f"검색 1회 {S['ms'][0]}~{S['ms'][1]:,}ms",
        f"작업 장비에서 {S['region']} 호출",
        f"입력 Gemma {S['input_tokens']['gemma']:,}, Qwen {S['input_tokens']['qwen']:,}토큰",
        f"1,000건에 {S['usd_per_1000']}달러, 초당 {S['quota_per_s']}건 한도",
    ],
    legend=[("Routing / Control", "purple"), ("Compute / Inference", "blue"), ("Memory / Cache", "yellow"),
            ("Latency / Cost", "orange"), ("Notes / Caveats", "pink")],
    note="서울 리전 측정, 구간 값은 2026-11-15에 요청 1건씩 보낸 중앙값, S1은 2026-11-14의 입력 256, 출력 128토큰, 동시성 1",
)

T_EN = dict(
    title="Journey of One LLM API Call",
    sub_en="Inside an LLM API Call on ow-on-gpu",
    sub_ko="The components that do each step here, with measured values",
    budget=("Latency Budget", "Time to first content, median of single requests",
            f"{share('gemma')}~{share('qwen')}% is vLLM"),
    budget_parts=("Entry", "routing"),
    measured="Measured",
    label_w=dict(s3=78, s4=78),
    s1=("API Gateway", "Request entry: TLS, rate limit, auth, validation"),
    s1_rows=[
        ("service/Amazon-CloudFront", "CloudFront", "HTTPS in, /v1/* to the internal ALB"),
        ("service/AWS-WAF", "AWS WAF", "403 above 300 requests per 5 min per IP"),
        ("service/Amazon-Cognito", "Cognito", "Issues access tokens, sign-up disabled"),
        ("service/Amazon-Elastic-Kubernetes-Service", "BFF", "Token check 401, body check 400"),
    ],
    s1_measure=f"To the edge {num(G['edge'])}ms, CloudFront {num(G['cloudfront'])}ms",
    s1_note=("429 comes from the gateway", "Only batch is rejected when a pool is saturated"),
    s2=("Load Balancer", "Spread across BFF pods and gateway pods"),
    s2_rows=[
        ("service/Elastic-Load-Balancing", "Internal ALB", "2 BFF pods, 30-min sticky cookie"),
        ("service/Amazon-Elastic-Kubernetes-Service", "Service", "BFF calls the gateway directly"),
        ("service/Amazon-Elastic-Kubernetes-Service", "agentgateway", "2 pods, pool by the body's model"),
        ("service/Amazon-Elastic-Kubernetes-Service", "Health check", "/healthz, sleeping Qwen excluded"),
    ],
    s2_measure=f"ALB {num(G['alb'])}ms, gateway segment {num(G['gateway'])}ms",
    s2_note=("Load-aware pod choice is step 4", "EPP decides inside the InferencePool"),
    s3=("Tokenization", "vLLM API server tokenizes, checks length"),
    s3_bubble=("How many days to", "request a return"),
    s3_ids=("Token IDs (example)", "2  1045  9873  412", "236  5521  88  107"),
    s3_rows=[
        ("Where", "vLLM API server, inside the model pod"),
        ("Limit", f"Gemma {G['max_model_len']:,}, Qwen {Q['max_model_len']:,} tokens"),
        ("Measured", "Tokenization time not measured separately"),
    ],
    s3_note=("Here the order is 4, then 3", "Routing uses headers and raw text, no tokenization"),
    s4=("Model Router", "BFF picks the model, EPP picks the pod"),
    s4_models=[("Gemma 4 31B", "Support, text tasks"), ("Qwen3.8-27B", "Coding, images")],
    s4_rows=[
        ("Decide", "Sensitive > task > image > Decider > default"),
        ("Pod", f"GAIE InferencePool, EPP {M['epp_ms']}ms"),
        ("Queue", "vLLM priority scheduler, support 0, batch 10"),
        ("Measured", f"BFF {num(G['bff'])}ms, Decider {M['decider_ms'][0]}~{M['decider_ms'][1]}ms"),
    ],
    s4_note=f"Support TTFT p50 under batch load: {M['priority_ttft_ms']['none'] / 1000:.1f}s → "
            f"{M['priority_ttft_ms']['engine'] / 1000:.2f}s",
    s5=("Inference Engine", "vLLM v0.33.0, one L40S per model generates tokens"),
    a=("Prefill", "All input tokens at once, KV cache written"),
    a_kv="KV cache",
    a_lines=[
        f"→ Sets TTFT: Gemma {num(G['prefill'])}ms, Qwen {num(Q['prefill'])}ms (short input)",
        f"Input 256: {num(G['s1']['ttft_p99'])}ms, 4,096: {num(G['s4_ttft_p99'], 0)}ms (Gemma TTFT p99)",
    ],
    b=("Decode", "Token loop: Attention, FFN, Sampling"),
    b_boxes=[("Attention", "KV cache lookup"), ("FFN", "Per-layer transform"), ("Sampling", "Pick next token")],
    b_loop="Append the new token to the input and repeat (KV cache reused)",
    b_lines=[
        f"→ Chunk interval: Gemma {num(G['s1']['itl'])}ms ({num(G['s1']['tokens_per_s'])} tokens/s), "
        f"Qwen {num(Q['s1']['itl'])}ms",
        f"Qwen MTP: several tokens per chunk, {num(Q['s1']['tpot'])}ms per token ({num(Q['s1']['tokens_per_s'])} tokens/s)",
    ],
    c=("Hardware", "One L40S 48GB"),
    c_caption=f"{M['device_gib']}GiB usable of GDDR6 48GB",
    c_bars=[
        ("Gemma", G["weights_gib"], G["kv_gib"], f"Weights {G['weights_gib']}, KV cache {G['kv_gib']}GiB"),
        ("Qwen", Q["weights_gib"], Q["kv_gib"], f"Weights {Q['weights_gib']}, KV cache {Q['kv_gib']}GiB"),
    ],
    c_line=f"Concurrency limit: Gemma {G['s1']['running_max']}, Qwen {Q['s1']['running_max']}",
    side=[
        "Time to first content:",
        f"{share('gemma')}~{share('qwen')}% is vLLM",
        "E2E ≒ TTFT",
        "+ (output - 1) × TPOT",
        f"{num(G['s1']['ttft'])} + 127 × {G['s1']['tpot']}",
        f"≒ {num(G['s1']['e2e'], 0)}ms (Gemma S1)",
    ],
    s6=("Post-processing", "Text, reasoning, tool calls"),
    s6_items=[
        ("Detokenize", "Token IDs → text", "vLLM, per chunk"),
        ("Reasoning parser", "gemma4, qwen3", "reasoning_content"),
        ("Tool-call parser", "gemma4, qwen3_coder", "Extracts tool_calls"),
    ],
    s6_code="finish_reason: stop / length / tool_calls",
    s6_line="No output safety filter, BFF runs tools then re-requests (max 3)",
    s7=("Response & Billing", "SSE delivery, cost is GPU time"),
    s7_bullets=[
        "stream=true: BFF relays each chunk",
        "Last chunk usage: input, output tokens",
        "Headers: x-bff-model, x-bff-timing",
        "Search answers: [1], [2] and sources",
    ],
    s7_pink=("No per-token price", "Longer output means", "more GPU time"),
    s7_cost=f"Cost = GPU node hours × rate, about {M['fixed_cost_usd_per_hour']} USD per hour here",
    s8=("Logging & Observability", "AMP, segment logs"),
    s8_items=[
        ("service/Amazon-Managed-Service-for-Prometheus", "AMP", "Agent sends metrics"),
        ("service/Amazon-EC2", "vLLM metrics", "TTFT, queue, KV"),
        ("service/Amazon-Elastic-Kubernetes-Service", "EPP, gateway", "Scheduling, requests"),
        ("service/Amazon-Elastic-Kubernetes-Service", "BFF logs", "Pod stdout"),
        ("service/Amazon-Simple-Storage-Service", "ALB access logs", "Stored in S3"),
        ("service/Amazon-CloudFront", "Server-Timing", "CloudFront header"),
    ],
    s8_line="Request ID and X-Amzn-Trace-Id tie segment records to each request",
    lane=("Optional path", "Web Search tool", "Added only for x-web-search: on", "Not for sensitive or benchmark"),
    lane_steps=dict(
        again=("Infer again", "Re-request 5 with results", f"Max {S['max_rounds']}, then tool_choice: none"),
        number=("Number results", f"Source numbers on {S['results']} results", f"Up to {S['text_chars']:,} chars of text"),
        search=("AgentCore Web Search", f"InvokeWebSearch, {S['region']}", "Uses the BFF Pod Identity role"),
        run=("Run tool", "BFF", "Receives tool_calls from 6", "web_search(query)", "Sensitive queries blocked"),
    ),
    lane_notes=[
        f"Search {S['ms'][0]}~{S['ms'][1]:,}ms",
        f"{S['region']} from the work machine",
        f"Input: Gemma {S['input_tokens']['gemma']:,}, Qwen {S['input_tokens']['qwen']:,} tokens",
        f"{S['usd_per_1000']} USD per 1,000, limit {S['quota_per_s']} per second",
    ],
    legend=[("Routing / Control", "purple"), ("Compute / Inference", "blue"), ("Memory / Cache", "yellow"),
            ("Latency / Cost", "orange"), ("Notes / Caveats", "pink")],
    note=("Measured in the Seoul Region. Segment values: median of single requests, 2026-11-15. "
          "S1 (2026-11-14): 256 input, 128 output tokens, concurrency 1"),
)

TEXT = {"ko": T, "en": T_EN}


def use(lang):
    """그릴 언어를 고른다. 카드의 위치는 같고 글만 바뀐다."""
    global T
    T = TEXT[lang]


# ----------------------------------------------------------------------------- 공통 조각
def icon_rows(d, ix, y0, items, rh, name_w, box):
    """아이콘, 이름, 하는 일을 한 줄씩."""
    for index, (ref, name, desc) in enumerate(items):
        mid = y0 + index * rh + rh / 2
        d.icon(ref, ix, mid - 11, 22)
        d.text(ix + 30, mid + 5, name, 13.5, 700, "text", box=box)
        d.text(ix + 30 + name_w, mid + 5, desc, 12.5, 400, "text2", box=box)


def label_rows(d, ix, y0, items, rh, label_w, box, color="purple"):
    """작은 이름표와 내용 한 줄씩."""
    for index, (label, body) in enumerate(items):
        mid = y0 + index * rh + rh / 2
        measured = label == T["measured"]
        tag(d, ix, mid - 10, label, "orange" if measured else color, 11.5, 20, 8, box=box)
        d.text(ix + label_w, mid + 4.5, body, 12.5, 700 if measured else 400, "text" if measured else "text2", box=box)


def measure(d, ix, y, text, box):
    width = tag(d, ix, y - 14, T["measured"], "orange", 11.5, 20, 8, box=box)
    d.text(ix + width + 10, y + 0.5, text, 13, 700, "text", box=box)


def note(d, x, y, w, h, lines, box):
    """분홍 주의 상자. 첫 줄은 분홍, 나머지는 본문색."""
    d.rect(x, y, w, h, rx=9, fill="pinkF", fo=0.08, stroke="pink", sw=1.2)
    lh = 18
    top = y + h / 2 - (len(lines) - 1) * lh / 2 + 4.5
    for index, line in enumerate(lines):
        d.text(x + w / 2, top + index * lh, line, 13, 700 if index == 0 else 400, "pink" if index == 0 else "text",
               "middle", box=box)


def letter(d, cx, cy, char):
    d.circle(cx, cy, 11, fill="badge")
    d.text(cx, cy + 4.6, char, 13, 700, "badgetext", "middle")


def sub_card(d, x, y, w, h, char, title, take, stroke="cardline"):
    card(d, x, y, w, h, stroke=stroke, sw=1.4 if stroke != "cardline" else 1.2, fill="panel", rx=10)
    letter(d, x + 24, y + 26, char)
    d.runs(x + 44, y + 32, [(title, 17, 700, "text"), (take, 13, 400, "muted", 10)], box=(x, y, w, h))


# ----------------------------------------------------------------------------- 위쪽 띠
def budget(d, x, y, w, h):
    box = (x, y, w, h)
    card(d, x, y, w, h, rx=12)
    title, sub, right = T["budget"]
    d.runs(x + 18, y + 27, [(title, 16, 700, "text"), (sub, 12, 400, "muted", 10)], box=box)
    d.text(x + w - 18, y + 27, right, 12.5, 700, "pink", "end", box=box)
    bar_x, bar_w = x + 126, 316
    scale = bar_w / (entry("qwen") + routing("qwen") + Q["vllm_ttft"])
    for index, model in enumerate(("gemma", "qwen")):
        m = M[model]
        top = y + 46 + index * 30
        d.text(x + 18, top + 13, f"{'Gemma' if model == 'gemma' else 'Qwen'} {num(m['first_content'])}ms", 12.5, 700,
               "text", box=box)
        cx = bar_x
        for value, color, opacity in ((entry(model), "purple", 0.45), (routing(model), "purple", 0.85),
                                      (m["vllm_ttft"], "blue", 0.9)):
            width = value * scale
            d.rect(cx, top, max(width - 2, 2), 18, rx=3, fill=color + "F", fo=opacity)
            cx += width
        d.text(bar_x + bar_w + 14, top + 13,
               f"{T['budget_parts'][0]} {num(entry(model))} + {T['budget_parts'][1]} {num(routing(model))} "
               f"+ vLLM {num(m['vllm_ttft'])}ms", 12, 400, "text2", box=box)


def legend(d, x, y):
    d.text(x, y, "LEGEND", 11, 700, "faint", ls=1.2)
    cx = x + rw("LEGEND", 11, 700, 1.2) + 16
    for name, color in T["legend"]:
        d.rect(cx, y - 7, 22, 4, rx=2, fill=color + "F")
        d.text(cx + 30, y, name, 12, 400, "muted")
        cx += 30 + rw(name, 12) + 22


# ----------------------------------------------------------------------------- 1~4
def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"], inline=False)
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    icon_rows(d, ix, cy + 2, T["s1_rows"], 29, 86, box)
    measure(d, ix, cy + 140, T["s1_measure"], box)
    note(d, ix, y + h - 16 - 48, iw, 48, T["s1_note"], box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"], inline=False)
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    icon_rows(d, ix, cy + 2, T["s2_rows"], 29, 110, box)
    measure(d, ix, cy + 140, T["s2_measure"], box)
    note(d, ix, y + h - 16 - 48, iw, 48, T["s2_note"], box)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"], inline=False)
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    top, bh = cy + 2, 54
    # 문장 -> tokenizer -> 토큰 ID
    d.rect(ix, top, 128, bh, rx=8, fill="panel", stroke="line2", sw=1.2)
    for index, line in enumerate(T["s3_bubble"]):
        d.text(ix + 64, top + 23 + index * 18, line, 12.5, 400, "text", "middle", box=box)
    d.arrow([(ix + 134, top + bh / 2), (ix + 156, top + bh / 2)], sw=1.6)
    d.rect(ix + 162, top + 6, 78, bh - 12, rx=8, fill="purpleF", fo=0.1, stroke="purple", sw=1.2)
    d.text(ix + 201, top + 24, "chat template", 10.5, 400, "text2", "middle", box=box)
    d.text(ix + 201, top + 40, "Tokenizer", 12, 700, "text", "middle", box=box)
    d.arrow([(ix + 246, top + bh / 2), (ix + 268, top + bh / 2)], sw=1.6)
    d.rect(ix + 274, top, iw - 274, bh, rx=8, fill="purpleF", fo=0.08, stroke="purple", sw=1.2)
    d.text(ix + 274 + (iw - 274) / 2, top + 16, T["s3_ids"][0], 10.5, 400, "muted", "middle", box=box)
    for index, line in enumerate(T["s3_ids"][1:]):
        d.text(ix + 274 + (iw - 274) / 2, top + 32 + index * 15, line, 11.5, 400, "text", "middle", box=box,
               family=CODE_FAMILY)
    label_rows(d, ix, top + bh + 8, T["s3_rows"], 26, T["label_w"]["s3"], box)
    note(d, ix, y + h - 16 - 48, iw, 48, T["s3_note"], box)


def s4(d, x, y, w, h):
    cy = section(d, x, y, w, h, 4, *T["s4"], inline=False)
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    top = cy
    # BFF에서 두 모델로 갈라지는 그림
    d.rect(ix, top + 17, 70, 28, rx=14, fill="purpleF", fo=0.14, stroke="purple", sw=1.3)
    d.text(ix + 35, top + 36, "BFF", 13, 700, "text", "middle", box=box)
    fork_x, model_x = ix + 86, ix + 102
    d.line(ix + 70, top + 31, fork_x, top + 31, stroke="purple", sw=1.5)
    d.line(fork_x, top + 14, fork_x, top + 48, stroke="purple", sw=1.5)
    for index, (name, role) in enumerate(T["s4_models"]):
        my = top + index * 34
        d.line(fork_x, my + 14, model_x, my + 14, stroke="purple", sw=1.5)
        d.rect(model_x, my, iw - 102, 28, rx=8, fill="purpleF", fo=0.1, stroke="purple", sw=1.2)
        d.icon("service/Amazon-EC2", model_x + 6, my + 4, 20)
        d.text(model_x + 34, my + 18.5, name, 13, 700, "text", box=box)
        d.text(model_x + iw - 102 - 10, my + 18.5, role, 12, 400, "text2", "end", box=box)
    label_rows(d, ix, top + 68, T["s4_rows"], 26, T["label_w"]["s4"], box)
    d.rect(ix, y + h - 14 - 32, iw, 32, rx=9, fill="pinkF", fo=0.08, stroke="pink", sw=1.2)
    d.text(ix + iw / 2, y + h - 14 - 32 + 20.5, T["s4_note"], 12.5, 700, "pink", "middle", box=box)


# ----------------------------------------------------------------------------- 5
def s5(d, x, y, w, h):
    cy = section(d, x, y, w, h, 5, *T["s5"])
    d.rect(x, y, w, h, rx=14, fill="none", stroke="blue", sw=1.6)
    top, sh = cy - 14, y + h - 16 - (cy - 14)
    ax, aw = x + 20, 420
    bx, bw = ax + aw + 18, 546
    cx, cw_ = bx + bw + 18, 296
    nx, nw = cx + cw_ + 18, x + w - 20 - (cx + cw_ + 18)
    for start in (ax + aw, bx + bw):
        d.arrow([(start + 2, top + sh / 2), (start + 16, top + sh / 2)], sw=1.6)

    # A Prefill
    box = (ax, top, aw, sh)
    sub_card(d, ax, top, aw, sh, "A", *T["a"])
    tx, tw_ = ax + 20, aw - 40
    d.rect(tx, top + 48, tw_, 36, rx=6, fill="none", stroke="blue", sw=1.3, dash="6 5")
    count, gap = 10, 8
    bw_ = (tw_ - 20 - (count - 1) * gap) / count
    for index in range(count):
        d.rect(tx + 10 + index * (bw_ + gap), top + 56, bw_, 20, rx=3, fill="blueF", fo=0.85)
    d.arrow([(tx + tw_ / 2, top + 86), (tx + tw_ / 2, top + 100)], sw=1.5)
    d.text(tx, top + 122, T["a_kv"], 13, 700, "yellow", box=box)
    kx = tx + 104
    for row, name in enumerate(("K", "V")):
        ky = top + 104 + row * 20
        d.text(kx, ky + 12.5, name, 12, 700, "yellow", box=box)
        cell_w = (tx + tw_ - (kx + 18) - 11 * 5) / 12
        for index in range(12):
            d.rect(kx + 18 + index * (cell_w + 5), ky, cell_w, 14, rx=2, fill="yellowF", fo=0.9)
    d.text(tx, top + 168, T["a_lines"][0], 13, 700, "orange", box=box)
    d.text(tx, top + 190, T["a_lines"][1], 12.5, 400, "text2", box=box)

    # B Decode
    box = (bx, top, bw, sh)
    sub_card(d, bx, top, bw, sh, "B", *T["b"], stroke="blue")
    step_w, step_h, step_gap = 136, 56, 40
    sx = bx + (bw - 3 * step_w - 2 * step_gap) / 2
    sy = top + 48
    for index, (name, role) in enumerate(T["b_boxes"]):
        color = "orange" if index == 2 else "blue"
        px = sx + index * (step_w + step_gap)
        d.rect(px, sy, step_w, step_h, rx=8, fill=color + "F", fo=0.1, stroke=color, sw=1.4)
        d.text(px + step_w / 2, sy + 24, name, 14, 700, "text", "middle", box=box)
        d.text(px + step_w / 2, sy + 43, role, 12, 400, "text2", "middle", box=box)
        if index < 2:
            d.arrow([(px + step_w + 6, sy + step_h / 2), (px + step_w + step_gap - 6, sy + step_h / 2)], sw=1.6)
    loop_y = sy + step_h + 14
    d.arrow([(sx + 2 * (step_w + step_gap) + step_w / 2, sy + step_h + 2),
             (sx + 2 * (step_w + step_gap) + step_w / 2, loop_y), (sx + step_w / 2, loop_y),
             (sx + step_w / 2, sy + step_h + 3)], color="orange", sw=1.5, dash="6 5", r=8)
    d.text(bx + bw / 2, loop_y + 18, T["b_loop"], 12, 400, "muted", "middle", box=box)
    d.text(bx + 20, top + 168, T["b_lines"][0], 13, 700, "orange", box=box)
    d.text(bx + 20, top + 190, T["b_lines"][1], 12.5, 700, "blue", box=box)

    # C Hardware
    box = (cx, top, cw_, sh)
    sub_card(d, cx, top, cw_, sh, "C", *T["c"])
    hx, hw = cx + 20, cw_ - 40
    d.text(hx, top + 58, T["c_caption"], 12, 400, "muted", box=box)
    label_w = 52
    scale = (hw - label_w) / M["device_gib"]
    for index, (name, weights, kv, caption) in enumerate(T["c_bars"]):
        by = top + 68 + index * 46
        d.text(hx, by + 13.5, name, 12.5, 700, "text", box=box)
        d.rect(hx + label_w, by, hw - label_w, 18, rx=3, fill="line2", fo=0.45)
        d.rect(hx + label_w, by, weights * scale - 2, 18, rx=3, fill="purpleF", fo=0.85)
        d.rect(hx + label_w + weights * scale, by, kv * scale, 18, rx=2, fill="yellowF", fo=0.95)
        d.text(hx + label_w, by + 33, caption, 11.5, 400, "text2", box=box)
    d.text(hx, top + 190, T["c_line"], 12, 700, "yellow", box=box)

    # 옆 상자
    box = (nx, top, nw, sh)
    d.rect(nx, top, nw, sh, rx=10, fill="pinkF", fo=0.08, stroke="pink", sw=1.3)
    mid = nx + nw / 2
    d.text(mid, top + 40, T["side"][0], 14, 700, "pink", "middle", box=box)
    d.text(mid, top + 64, T["side"][1], 17, 700, "pink", "middle", box=box)
    d.line(nx + 24, top + 84, nx + nw - 24, top + 84, stroke="pink", sw=1, so=0.5)
    d.text(mid, top + 112, T["side"][2], 13.5, 700, "text", "middle", box=box)
    d.text(mid, top + 132, T["side"][3], 13.5, 700, "text", "middle", box=box)
    d.text(mid, top + 164, T["side"][4], 12.5, 400, "text2", "middle", box=box)
    d.text(mid, top + 184, T["side"][5], 12.5, 400, "text2", "middle", box=box)


# ----------------------------------------------------------------------------- 6~8
def s6(d, x, y, w, h):
    cy = section(d, x, y, w, h, 6, *T["s6"]) + 10
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    col = iw / 3
    for index, (name, line1, line2) in enumerate(T["s6_items"]):
        cx = ix + index * col
        tag(d, cx, cy - 6, name, "purple", 12.5, 24, 10, box=box)
        d.text(cx + 2, cy + 38, line1, 12.5, 400, "text", box=box)
        d.text(cx + 2, cy + 56, line2, 12, 400, "muted", box=box)
    code_w = cw(T["s6_code"], 12.5) * 1.06 + 30
    d.rect(ix, cy + 70, code_w, 28, rx=6, fill="panel", stroke="line2", sw=1.1)
    d.text(ix + 14, cy + 88.5, T["s6_code"], 12.5, 400, "text", box=box, family=CODE_FAMILY)
    d.text(ix, cy + 122, T["s6_line"], 12.5, 400, "muted", box=box)


def s7(d, x, y, w, h):
    cy = section(d, x, y, w, h, 7, *T["s7"]) + 10
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    pink_w = 152
    dot_list(d, ix, cy + 2, iw - pink_w - 12, T["s7_bullets"], 13, 19, 5, dot="orange", box=box)
    px = ix + iw - pink_w
    d.rect(px, cy - 10, pink_w, 84, rx=9, fill="pinkF", fo=0.08, stroke="pink", sw=1.2)
    d.text(px + pink_w / 2, cy + 16, T["s7_pink"][0], 13.5, 700, "pink", "middle", box=box)
    d.text(px + pink_w / 2, cy + 38, T["s7_pink"][1], 12.5, 400, "text", "middle", box=box)
    d.text(px + pink_w / 2, cy + 56, T["s7_pink"][2], 12.5, 400, "text", "middle", box=box)
    d.rect(ix, cy + 92, iw, 32, rx=8, fill="orangeF", fo=0.1, stroke="orange", sw=1.2)
    d.text(ix + 14, cy + 112.5, T["s7_cost"], 12.5, 700, "text", box=box)


def s8(d, x, y, w, h):
    cy = section(d, x, y, w, h, 8, *T["s8"]) + 10
    box = (x, y, w, h)
    ix, iw = x + 20, w - 40
    col = iw / 3
    for index, (ref, name, desc) in enumerate(T["s8_items"]):
        cx = ix + (index % 3) * col
        top = cy - 6 + (index // 3) * 46
        d.icon(ref, cx, top, 28)
        d.text(cx + 36, top + 12, name, 13, 700, "text", box=box)
        d.text(cx + 36, top + 29, desc, 11.5, 400, "muted", box=box)
    d.text(ix, cy + 122, T["s8_line"], 12.5, 400, "muted", box=box)


def lane(d, x, y, w, h):
    """웹 검색 경로. 6에서 받아 위로 올라가 5로 돌아가므로 단계를 아래에서 위로 쌓는다."""
    box = (x, y, w, h)
    card(d, x, y, w, h, stroke="purple", sw=1.5, dashed=True)
    label, title, take1, take2 = T["lane"]
    tag(d, x + 18, y + 14, label, "purple", 11.5, 22, 9, box=box)
    d.text(x + 18, y + 62, title, 19, 700, "text", box=box)
    d.text(x + 18, y + 84, take1, 12.5, 400, "muted", box=box)
    d.text(x + 18, y + 102, take2, 12.5, 400, "muted", box=box)
    bx, bw = x + 16, w - 32
    steps = T["lane_steps"]
    tops = {"again": y + 118, "number": y + 202, "search": y + 286, "run": y + 378}
    heights = {"again": 68, "number": 68, "search": 76, "run": 84}
    for name in ("again", "number", "search", "run"):
        d.rect(bx, tops[name], bw, heights[name], rx=9, fill="purpleF", fo=0.14 if name == "search" else 0.07,
               stroke="purple", sw=1.5 if name == "search" else 1.1)
    for lower, upper in (("run", "search"), ("search", "number"), ("number", "again")):
        d.arrow([(bx + bw / 2, tops[lower] - 2), (bx + bw / 2, tops[upper] + heights[upper] + 3)], color="purple", sw=1.6)

    for name in ("again", "number"):
        label, line1, line2 = steps[name]
        sy = tops[name]
        tag(d, bx + 10, sy + 8, label, "purple", 11.5, 20, 8, box=box)
        d.text(bx + 12, sy + 46, line1, 12.5, 700, "text", box=box)
        d.text(bx + 12, sy + 61, line2, 11.5, 400, "text2", box=box)

    name, line1, line2 = steps["search"]
    sy = tops["search"]
    # 아이콘 세트의 이름은 글리프의 밝기다. 밝은 바탕에는 어두운 글리프를 쓴다.
    d.icon(f"agentcore-{'dark' if d.theme == 'light' else 'light'}/Agentcore", bx + 10, sy + 9, 24)
    d.text(bx + 42, sy + 26, name, 13, 700, "text", box=box)
    d.text(bx + 12, sy + 50, line1, 12, 400, "text", box=box, family=CODE_FAMILY)
    d.text(bx + 12, sy + 67, line2, 11.5, 400, "text2", box=box)

    label, who, line1, line2, line3 = steps["run"]
    sy = tops["run"]
    width = tag(d, bx + 10, sy + 8, label, "purple", 11.5, 20, 8, box=box)
    d.text(bx + 10 + width + 8, sy + 23, who, 13, 700, "text", box=box)
    d.text(bx + 12, sy + 46, line1, 12.5, 700, "text", box=box)
    d.text(bx + 12, sy + 62, line2, 11.5, 400, "text", box=box, family=CODE_FAMILY)
    d.text(bx + 12, sy + 77, line3, 11.5, 400, "text2", box=box)

    ny = y + 484
    width = tag(d, x + 18, ny - 14, T["measured"], "orange", 11.5, 20, 8, box=box)
    d.text(x + 18 + width + 8, ny + 0.5, T["lane_notes"][0], 12.5, 700, "text", box=box)
    d.text(x + 18, ny + 19, T["lane_notes"][1], 11.5, 400, "muted", box=box)
    d.text(x + 18, ny + 38, T["lane_notes"][2], 11.5, 400, "text2", box=box)
    d.text(x + 18, ny + 56, T["lane_notes"][3], 11.5, 400, "text2", box=box)
    return tops["run"] + heights["run"] / 2, tops["again"] + heights["again"] / 2


def landscape(theme):
    d = Doc(W, H, theme)
    d.rect(0, 0, W, H, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    budget(d, 1112, 24, 760, 112)
    for number, draw in ((1, s1), (2, s2), (3, s3), (4, s4), (5, s5), (6, s6), (7, s7), (8, s8)):
        draw(d, *REGIONS[number])
    # 단계 사이의 화살표
    for a, b in ((1, 2), (2, 3), (3, 4), (6, 7), (7, 8)):
        ax, ay, aw, ah = REGIONS[a]
        d.arrow([(ax + aw + 6, ay + ah / 2), (REGIONS[b][0] - 6, ay + ah / 2)], sw=1.8)
    for source, target, start_x in ((4, 5, REGIONS[4][0] + W4 / 2), (5, 6, 1100)):
        sy = REGIONS[source][1] + REGIONS[source][3]
        ty = REGIONS[target][1]
        end_x = REGIONS[target][0] + 72
        d.arrow([(start_x, sy + 2), (start_x, (sy + ty) / 2), (end_x, (sy + ty) / 2), (end_x, ty - 3)], sw=1.8, r=8)
    # 웹 검색 경로: 6에서 받아 5로 돌려보낸다.
    run_y, again_y = lane(d, *LANE)
    edge = LANE[0] + LANE[2]
    d.arrow([(REGIONS[6][0] - 2, run_y), (edge + 4, run_y)], color="purple", sw=2.2)
    d.arrow([(edge + 2, again_y), (REGIONS[5][0] - 4, again_y)], color="purple", sw=2.2)
    legend(d, 48, 1064)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()


def web_data():
    """웹 화면이 쓰는 값. 단계 카드의 위치는 그림 크기에 대한 비율(%)이다."""
    regions = {str(number): {"left": round(x / W * 100, 3), "top": round(y / H * 100, 3),
                             "width": round(w / W * 100, 3), "height": round(h / H * 100, 3)}
               for number, (x, y, w, h) in {**REGIONS, "search": LANE}.items()}
    derived = {model: {"entry": entry(model), "routing": routing(model), "share": share(model)}
               for model in ("gemma", "qwen")}
    return {"regions": regions, "measured": M, "derived": derived}


def web_module():
    """web_data()를 ES 모듈로 낸다. Vite와 Node(시험)가 같은 파일을 읽는다."""
    import json
    body = json.dumps(web_data(), ensure_ascii=False, indent=2)
    return ("// docs/infographic/apicall.py가 만든 파일이다. 직접 고치지 말고 docs/infographic/build.sh로 다시 만든다.\n"
            f"export default {body};\n")
