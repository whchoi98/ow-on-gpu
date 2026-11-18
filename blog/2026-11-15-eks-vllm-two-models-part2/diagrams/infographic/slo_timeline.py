"""2부 그림 2. TTFT와 ITL이 재는 구간, KV 캐시가 정하는 동시 실행 수. infokit(docs/infographic)으로 그린다.

  landscape(theme)  16:9 도식 한 장. 본문 안에서 읽히도록 글자를 키웠다(K = 1.3)

위쪽 타임라인의 구간 길이와 토큰 수는 설명용 비율이다. 측정값은 모두 원고의 표에서 옮겼다.
  TTFT, ITL 값          표 5(Gemma S1 동시성별), 4.2절의 ITL 중앙값 54.0ms와 초당 18.5토큰
  KV 캐시에 들어간 요청  표 6(동시성 64 단계의 실행 중 최대와 KV 캐시 사용률 최대), 표 2(입력과 출력 토큰)
  한도에 닿은 뒤         4.3절의 S2 동시성 16, 32, 64 값
  Qwen                  5.1절과 5.3절(요청당 13블록, 46블록, 3건)
원본 기록은 docs/08-results.md 3절과 results/2026-11-14-slo 이다.
"""
from infokit import Doc, F, footer_note, header, rw, section, tag

W, H = 1920, 1080
K = 1.3

M = dict(
    # 요청이 짧은 순서. (이름, 요청 하나의 토큰, 실행 중 최대, KV 캐시 사용률 최대)
    fits=[("S1 짧은 채팅", "입력 256, 출력 128", 45, 0.998),
          ("S3 분류", "입력 512, 출력 16", 24, 0.993),
          ("S2 요약과 생성", "입력 1,024, 출력 256", 12, 0.996),
          ("S4 장문 RAG", "입력 4,096, 출력 256", 7, 0.949)],
)

T = dict(
    title="TTFT, ITL과 동시 실행 한도",
    sub_en="What TTFT and ITL Measure, What Caps Concurrency",
    sub_ko="요청 한 건의 구간과 KV 캐시가 만드는 대기",
    s1=("요청 한 건의 타임라인", "TTFT는 대기와 Prefill, ITL은 Decode 한 번"),
    lanes=[("클라이언트", "보낸 요청, 받은 토큰"), ("vLLM 엔진", "요청 하나의 처리")],
    request="요청",
    token="토큰",
    wait="대기",
    prefill=("Prefill", "입력 토큰을 한 번에 처리"),
    decode="Decode",
    ttft=("TTFT", "요청부터 첫 토큰까지 = 대기 + Prefill", "기준 p99 500ms 이하"),
    itl=("ITL", "토큰 사이 간격 = Decode 한 번", "기준 p99 50ms 이하"),
    cards=[("TTFT", "Time To First Token", "답이 시작됐다고 느끼는 시점",
            ["Gemma S1 p99: 동시성 1 86.6ms, 8 478.4ms, 16 973.5ms",
             "입력이 긴 S4(4,096토큰)는 동시성 1에서 1,093.2ms"],
            "부하에 따라 증가, S1은 동시성 8까지 기준 이내", "green"),
           ("ITL", "Inter-Token Latency", "글자가 이어지는 속도",
            ["Gemma S1 동시성 1: p99 57.7ms, 중앙값 54.0ms, 초당 18.5토큰",
             "동시성 8까지 60.2ms 이하, 16에서 88.2ms, 32에서 394.2ms"],
            "동시성 1에서 이미 기준 50ms 초과", "pink")],
    s2=("KV 캐시와 동시 실행 한도", "KV 캐시에 들어가는 만큼만 실행, 나머지는 대기"),
    flow=[("부하 발생기, 동시성 64", "동시에 보내 둔 요청 64건 (S1 짧은 채팅)", None, False),
          ("대기열", "KV 캐시에 자리가 날 때까지 대기, 그 시간은 TTFT에 포함", "pink", True),
          ("KV 캐시 5.37GiB, 실행 중 45건", "사용률 0.998, 들어가는 만큼만 실행", "yellow", False)],
    flow_arrows=("KV 캐시가 차 있을 때", "자리가 났을 때"),
    after=("한도에 닿은 뒤: 처리량 정체, TTFT만 증가",
           "Gemma S2, 동시성 16, 32, 64: 163.6, 164.7, 164.0 tok/s",
           "TTFT p99 19,049.8ms, 37,950.4ms, 91,297.4ms"),
    fits_title=("KV 캐시 5.37GiB에 들어간 요청 수", "Gemma 4 31B, 동시성 64 단계의 실행 중 최대"),
    fits_unit="건",
    usage="사용률",
    fits_take="요청 하나가 잡는 KV 캐시가 클수록 동시에 실행되는 수는 감소",
    qwen=("Qwen3.8-27B, MTP 켬", "토큰 수가 아닌 블록 수로 제한: 요청당 13블록, 46블록에 3건, 요청 길이와 무관"),
    note=("위 타임라인의 구간 길이와 토큰 수는 설명용 비율. 측정값은 2026-11-14 서울 리전, g6e.4xlarge(L40S 48GB), "
          "vLLM v0.33.0, 랜덤 토큰 프롬프트, 단계마다 1회"),
)


def bracket(d, x1, x2, y, color="orange"):
    d.line(x1, y, x2, y, stroke=color, sw=2.2)
    for xx in (x1, x2):
        d.line(xx, y - 8, xx, y + 8, stroke=color, sw=2.2)


def dots(d, x, y):
    for i in range(3):
        d.circle(x + i * 14, y, 3.2, fill="faint")


def s1(d, x, y, w, h, k=K):
    cy = section(d, x, y, w, h, 1, *T["s1"], tsize=F(21, k), ksize=F(15, k))
    box = (x, y, w, h)
    ix = x + 30
    t0 = ix + 184
    wait, prefill, step, n = 150, 250, 96, 5
    lh = 62
    l1 = cy + 12
    l2 = l1 + lh + 26
    first = t0 + wait + prefill
    end = first + n * step + 76
    for (name, sub), ly in zip(T["lanes"], (l1, l2)):
        d.text(ix, ly + 27, name, 19, 700, "text", box=box)
        d.text(ix, ly + 49, sub, 15, 400, "muted", box=box)
        d.rect(t0 - 14, ly, end - t0 + 28, lh, rx=10, fill="panel", stroke="cardline", sw=1)
    # 안내선은 클라이언트 레인의 사건에서 시작해 아래 괄호까지 내려간다. 엔진 레인에서는 구간의 경계를 지난다
    yb = l2 + lh + 30
    tok = [first + i * step for i in range(n + 1)]
    for gx in (t0, tok[0], tok[1], tok[2]):
        d.line(gx, l1 + lh, gx, yb - 8, stroke="faint", sw=1.2, dash="4 4")
    # 클라이언트 레인: 요청과 토큰
    d.rect(t0, l1 + 12, 78, 38, rx=19, fill="card", stroke="line2", sw=1.4)
    d.text(t0 + 39, l1 + 37, T["request"], 17, 700, "text", "middle", box=box)
    for i, tx in enumerate(tok):
        d.rect(tx - 37, l1 + 12, 74, 38, rx=19, fill="orangeF", fo=0.16, stroke="orange", sw=1.4)
        d.text(tx, l1 + 37, f"{T['token']} {i + 1}", 16, 700, "text", "middle", box=box)
    dots(d, tok[-1] + 52, l1 + lh / 2)
    # 엔진 레인: 대기, Prefill, Decode
    d.rect(t0 + 2, l2 + 8, wait - 5, lh - 16, rx=8, fill="pinkF", fo=0.10, stroke="pink", sw=1.5, dash="7 5")
    d.text(t0 + wait / 2, l2 + lh / 2 + 6, T["wait"], 17, 700, "pink", "middle", box=box)
    d.rect(t0 + wait, l2 + 8, prefill - 3, lh - 16, rx=8, fill="blueF", fo=0.92)
    d.text(t0 + wait + prefill / 2, l2 + 28, T["prefill"][0], 17, 700, "badgetext", "middle", box=box)
    d.text(t0 + wait + prefill / 2, l2 + 47, T["prefill"][1], 13, 400, "badgetext", "middle", box=box)
    for i in range(n):
        bx = first + i * step + 3
        d.rect(bx, l2 + 8, step - 6, lh - 16, rx=8, fill="orangeF", fo=0.92)
        d.text(bx + (step - 6) / 2, l2 + lh / 2 + 5, T["decode"], 15, 700, "onwarm", "middle", box=box)
    dots(d, tok[-1] + 14, l2 + lh / 2)
    # 괄호와 정의
    bracket(d, t0, tok[0], yb)
    bracket(d, tok[1], tok[2], yb)
    name, body, limit = T["ttft"]
    d.runs(t0, yb + 38, [(name, 21, 700, "orange"), (body, 17, 400, "text2", 10)], box=box)
    tag(d, t0, yb + 52, limit, "orange", 15, 28, 12, box=box)
    name, body, limit = T["itl"]
    ax = tok[1] - 6
    d.runs(ax, yb + 38, [(name, 21, 700, "orange"), (body, 17, 400, "text2", 10)], box=box)
    tag(d, ax, yb + 52, limit, "orange", 15, 28, 12, box=box)
    # 오른쪽 카드 두 장
    cwd = 560
    cx = x + w - 30 - cwd
    top, bottom = cy + 4, y + h - 22
    ch = (bottom - top - 14) / 2
    for i, (name, full, what, measured, verdict, color) in enumerate(T["cards"]):
        ty = top + i * (ch + 14)
        d.rect(cx, ty, cwd, ch, rx=12, fill="panel", stroke="orange", sw=1.4)
        d.runs(cx + 20, ty + 35, [(name, 22, 700, "orange"), (full, 15, 400, "muted", 10), (what, 16, 700, "text", 14)],
               box=box)
        for j, line in enumerate(measured):
            d.text(cx + 20, ty + 64 + j * 25, line, 17, 400, "text2", box=box)
        tag(d, cx + 20, ty + ch - 40, verdict, color, 15, 28, 12, box=box)


def s2(d, x, y, w, h, k=K):
    cy = section(d, x, y, w, h, 2, *T["s2"], tsize=F(21, k), ksize=F(15, k))
    box = (x, y, w, h)
    ix = x + 30
    # 왼쪽: 요청이 실행되기까지
    fwd, bh, gap = 500, 72, 34
    for i, (title, desc, color, dashed) in enumerate(T["flow"]):
        by = cy + 6 + i * (bh + gap)
        d.rect(ix, by, fwd, bh, rx=12, fill=(color + "F") if color else "panel", fo=0.10 if color else None,
               stroke=color or "line2", sw=1.5, dash="7 5" if dashed else None)
        d.text(ix + 20, by + 31, title, 20, 700, "text", box=box)
        d.text(ix + 20, by + 57, desc, 16, 400, "text2", box=box)
        if i < len(T["flow"]) - 1:
            ax = ix + 60
            d.arrow([(ax, by + bh + 4), (ax, by + bh + gap - 4)], sw=2)
            d.text(ax + 16, by + bh + gap / 2 + 5, T["flow_arrows"][i], 15, 400, "muted", box=box)
    ay = cy + 6 + len(T["flow"]) * (bh + gap) - 6
    ah = y + h - 22 - ay
    d.rect(ix, ay, fwd, ah, rx=12, fill="pinkF", fo=0.08, stroke="pink", sw=1.4)
    d.text(ix + 20, ay + 30, T["after"][0], 18, 700, "text", box=box)
    d.text(ix + 20, ay + 54, T["after"][1], 16, 400, "text2", box=box)
    d.text(ix + 20, ay + 77, T["after"][2], 16, 400, "text2", box=box)
    # 오른쪽: KV 캐시에 들어간 요청 수
    rx0 = ix + fwd + 62
    d.runs(rx0, cy + 30, [(T["fits_title"][0], 20, 700, "text"), (T["fits_title"][1], 15, 400, "muted", 12)], box=box)
    lab, bw, barh, pitch = 238, 700, 42, 66
    bx = rx0 + lab
    for i, (name, tokens, n, usage) in enumerate(M["fits"]):
        ry = cy + 56 + i * pitch
        d.text(rx0, ry + 18, name, 19, 700, "text", box=box)
        d.text(rx0, ry + 41, tokens, 15, 400, "muted", box=box)
        d.rect(bx - 4, ry - 4, bw + 8, barh + 8, rx=7, fill="none", stroke="faint", sw=1.2, dash="4 4")
        cwid = bw * usage / n
        for j in range(n):
            d.rect(bx + j * cwid + 1, ry, cwid - 2, barh, rx=3, fill="yellowF", fo=0.92)
        d.runs(bx + bw + 26, ry + 30, [(f"{n}{T['fits_unit']}", 25, 700, "yellow"),
                                         (f"{T['usage']} {usage:.3f}", 16, 400, "muted", 12)], box=box)
    ly = cy + 56 + len(M["fits"]) * pitch + 12
    d.text(rx0, ly + 12, T["fits_take"], 18, 700, "text", box=box)
    twd = tag(d, rx0, ly + 30, T["qwen"][0], "purple", 15, 28, 12, box=box)
    d.text(rx0 + twd + 12, ly + 50, T["qwen"][1], 16, 400, "text2", box=box)


def landscape(theme):
    d = Doc(W, H, theme)
    d.rect(0, 0, W, H, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    s1(d, 48, 140, 1824, 392)
    s2(d, 48, 552, 1824, 492)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
