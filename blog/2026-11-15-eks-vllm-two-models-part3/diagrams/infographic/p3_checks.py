"""Part 3, figure 3: what to check after each step and the measured value that tells it worked.

Values (ow-on-gpu repository, Seoul Region):
  step 1  AGENT.md, docs/onboarding.md              step 5  docs/05-decider.md (warm-up, 50 decisions per kind)
  step 2  jobs/model-sync/README.md (2026-11-14)     step 6  docs/06-sleep.md (5 cycles)
  step 3  docs/03-vllm.md (first start, one run)     step 7  docs/07-bff.md (2026-11-15, current setup)
  step 4  docs/04-gateway.md                         step 8  docs/08-results.md (first content: 2026-11-15, 20 requests)
Nodes: README.md (2026-11-16). Fixed cost: docs/07-bff.md (2026-11-15).
"""
from infokit import Doc, badge, cell, footer_note, header, para, section, series_nav

from common import PART, SERIES, pick

T_KO = dict(
    title="단계별 확인표",
    sub_en="OpenWeight on AWS GPU",
    sub_ko="단계마다 확인하는 방법, 측정한 값, 막히기 쉬운 곳",
    s1=("1~8단계의 확인 방법과 측정한 값", "0단계는 리소스가 없고 9단계는 아직 실행하지 않아 제외"),
    cols=["단계", "확인 방법", "측정한 값", "막히기 쉬운 곳"],
    rows=[
        ("1", "네트워크와 EKS 기반", "terraform validate와 서버 dry-run 통과, kubectl get nodes로 연결 확인",
         "VPC 10.200.0.0/16, AZ 4개, 애드온용 노드 m7g.large 2대", "params.yaml과 terraform.tfvars의 값 채우기"),
        ("2", "모델 적재", "Job 로그의 verified 줄과 summary 줄",
         "첫 적재 73개 74.90GB 491초, Decider 12B 추가 13개 23.97GB 315초", "다시 실행은 Job 삭제 뒤 적용, 로그는 먼저 저장"),
        ("3", "vLLM 배포", "파드 로그의 Model loading took 줄과 init engine 줄",
         "가중치 로드 Gemma 19.1초, Qwen 34.3초, KV 캐시 5.37GiB와 2.46GiB",
         "Qwen은 gpu-memory-utilization 0.85에서 시작 실패, 0.90 사용"),
        ("4", "GAIE와 게이트웨이", "model 값만 바꿔 두 모델이 각각 200, /sleep 경로는 404",
         "설치 72초, Gateway와 HTTPRoute, InferencePool이 Accepted", "EPP 대기 복제본의 NotReady는 설계된 동작"),
        ("5", "Strands Decider 12B", "예열 뒤 Ready, /health의 model 값과 device 값 cuda:0",
         "시작부터 Ready 43초, 판단 1회 89.7~90.6ms (게이트웨이 경유, 중앙값)", "공개 이미지는 v2를 읽지 못해 직접 빌드"),
        ("6", "sleep 컨트롤러", "잠든 동안 Qwen 요청 503, 깨우기 API 호출 뒤 성공",
         "sleep 진입 2.98초, 복귀 3.66초 (5회)", "VPC CNI의 enableNetworkPolicy를 켜야 정책 적용"),
        ("7", "앱 계층", "토큰 없는 요청 401, 로그인 뒤 스트리밍 응답",
         "이벤트 간격 중앙값 53.5ms, VPC origin 생성 9분 18초", "Terraform, install.sh, Terraform 순서로 적용"),
        ("8", "관측과 측정", "수집 대상 8개 모두 up, 대시보드 쿼리 27개에 값",
         "콜드 스타트 394초에서 260초, 첫 내용 81.9ms와 177.5ms", "EPP의 /metrics는 토큰 없이는 401"),
    ],
    s2=("전체 동작 확인", "0~8단계를 마친 뒤의 환경"),
    stats=[
        ("노드 9대", "m7g.large 2, c7i-flex.xlarge 2, c7g.large 2, g6e.4xlarge 2, g6e.xlarge 1", "blue"),
        ("토큰 없는 요청 401", "로그인하지 않은 /v1/* 요청은 BFF가 거절", "purple"),
        ("이벤트 간격 53.5ms", "상담 요청의 내용 이벤트 53개, 1ms 안에 붙어 온 이벤트 0개", "orange"),
        ("첫 내용 81.9ms, 177.5ms", "Gemma 4 31B와 Qwen3.8-27B, 요청 20건의 중앙값", "orange"),
        ("시간당 약 $11.35", "모든 구성 요소가 실행 중일 때의 고정 비용 추정", "pink"),
    ],
    note="2026-11-14 서울 리전에서 적용하고 측정, 7단계와 첫 내용은 2026-11-15, 5단계는 2026-11-24, 노드 수는 2026-11-26 확인, "
         "횟수를 적지 않은 값은 1회 측정",
)

T_EN = dict(
    title="What to Check after Each Step",
    sub_en="OpenWeight on AWS GPU",
    sub_ko="How to check each step, the measured value, and where it tends to go wrong",
    s1=("Checks and measured values for steps 1 to 8", "Step 0 creates nothing and step 9 has not been run, so both are left out"),
    cols=["Step", "How to check", "Measured value", "Where it goes wrong"],
    rows=[
        ("1", "Network and EKS base", "terraform validate and a server dry-run pass, kubectl get nodes reaches the cluster",
         "VPC 10.200.0.0/16, 4 AZs, 2 x m7g.large add-on nodes", "Fill in params.yaml and terraform.tfvars first"),
        ("2", "Model sync", "The verified and summary lines in the Job log",
         "First sync 73 objects 74.90 GB 491 s, Decider 12B added 13 objects 23.97 GB 315 s", "To rerun, delete the Job and apply. Save the log before"),
        ("3", "vLLM deployment", "The Model loading took and init engine lines in the pod log",
         "Weight load Gemma 19.1 s, Qwen 34.3 s, KV cache 5.37 GiB and 2.46 GiB",
         "Qwen fails to start at gpu-memory-utilization 0.85, use 0.90"),
        ("4", "GAIE and gateway", "Changing only the model value returns 200 from each model, /sleep returns 404",
         "Installed in 72 s, Gateway, HTTPRoute and InferencePool are Accepted", "A NotReady standby EPP replica is by design"),
        ("5", "Strands Decider 12B", "Ready after warm-up, model name and device cuda:0 in /health",
         "Start to Ready 43 s, one decision 89.7~90.6 ms (via the gateway, median)", "The public image cannot read v2, build your own"),
        ("6", "Sleep controller", "A Qwen request gets 503 while asleep and succeeds after the wake API call",
         "Enter sleep 2.98 s, wake 3.66 s (5 runs)", "Policies apply only with enableNetworkPolicy on in the VPC CNI"),
        ("7", "App layer", "401 without a token, a streamed reply after sign-in",
         "Median event interval 53.5 ms, VPC origin created in 9 min 18 s", "Apply in the order Terraform, install.sh, Terraform"),
        ("8", "Observability and measurement", "All 8 scrape targets up, all 27 dashboard queries return values",
         "Cold start 394 s to 260 s, first content 81.9 ms and 177.5 ms", "The EPP /metrics endpoint returns 401 without a token"),
    ],
    s2=("Checking the whole environment", "After steps 0 to 8"),
    stats=[
        ("9 nodes", "m7g.large 2, c7i-flex.xlarge 2, c7g.large 2, g6e.4xlarge 2, g6e.xlarge 1", "blue"),
        ("401 without a token", "The BFF rejects /v1/* requests that are not signed in", "purple"),
        ("Event interval 53.5 ms", "53 content events of a support request, none arrived within 1 ms of another", "orange"),
        ("First content 81.9, 177.5 ms", "Gemma 4 31B and Qwen3.8-27B, median of 20 requests", "orange"),
        ("About $11.35 per hour", "Estimated fixed cost with every component running", "pink"),
    ],
    note="Applied and measured 2026-11-14 in the Seoul Region, step 7 and first content on 2026-11-15, step 5 on 2026-11-24, "
         "node count checked 2026-11-26. Values without a count were measured once",
)

T = pick(T_KO, T_EN)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    widths = [258, 520, 520, iw - 258 - 520 - 520]
    xs = [ix + sum(widths[:i]) for i in range(4)]
    head_h = 36
    rh = (y + h - 14 - cy - head_h) / len(T["rows"])
    d.rect(ix, cy, iw, head_h, rx=6, fill="panel")
    for cx, name in zip(xs, T["cols"]):
        d.text(cx + 14, cy + head_h / 2 + 5, name, 14, 700, "muted", box=box)
    for r, (num, name, how, value, trap) in enumerate(T["rows"]):
        top = cy + head_h + r * rh
        mid = top + rh / 2
        if r:
            d.line(ix, top, ix + iw, top, stroke="cardline", sw=1.0)
        badge(d, xs[0] + 26, mid, num, r=13, size=14)
        cell(d, xs[0] + 50, mid, widths[0] - 60, name, 15, 20, 700, "text", box)
        cell(d, xs[1] + 14, mid, widths[1] - 34, how, 14, 19, 400, "text2", box)
        cell(d, xs[2] + 14, mid, widths[2] - 34, value, 14, 19, 700, "orange", box)
        cell(d, xs[3] + 14, mid, widths[3] - 24, trap, 14, 19, 400, "pink", box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 16
    cw_ = (iw - gap * (len(T["stats"]) - 1)) / len(T["stats"])
    ch = y + h - 16 - cy
    for i, (value, label, color) in enumerate(T["stats"]):
        cx = ix + i * (cw_ + gap)
        d.rect(cx, cy, cw_, ch, rx=10, fill="panel", stroke="cardline", sw=1.2)
        d.rect(cx, cy + 10, 4, ch - 20, rx=2, fill=color + "F")
        d.text(cx + 18, cy + 32, value, 19, 700, color, box=box)
        para(d, cx + 18, cy + 56, cw_ - 34, label, 12.5, 17, 400, "muted", box=box, maxl=3)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, PART)
    s1(d, 48, 140, 1824, 702)
    s2(d, 48, 862, 1824, 182)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
