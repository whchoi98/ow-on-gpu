"""Part 2, figure 3: GPU memory, the KV cache and concurrent requests on a single L40S.

Every number comes from the tables of the post: workloads, GPU memory split (start-up log),
results by concurrency (Gemma S1, Qwen S1 with MTP on), MTP on versus off.
Layout is the same as ow-on-gpu/blog/2026-11-15-eks-vllm-two-models-part2/diagrams/infographic/overview.py.
"""
from infokit import Doc, callout, footer_note, header, rw, section, series_nav, tag

from common import SERIES, SUB
from common import pick as pick_lang

W, H = 1920, 1080

M = dict(
    conc=[1, 2, 4, 8, 16, 32, 64],
    gemma=dict(tput=[18.5, 36.6, 71.5, 138.2, 248.3, 424.4, 447.0],
               ttft=[86.6, 123.0, 271.6, 478.4, 973.5, 1760.7, 12335.1],
               running=[1, 2, 4, 8, 16, 32, 45], limit_from=6),
    qwen=dict(tput=[32.5, 58.7, 79.9, 91.2, 87.9, 85.0, 90.4],
              ttft=[210.4, 280.1, 4374.5, 9274.6, 23394.0, 48678.4, 91191.4],
              running=[1, 2, 3, 3, 3, 3, 3], limit_from=2),
    device=44.39, target=39.95, ttft_slo=500,
    mem=dict(gemma=dict(weights=31.13, act=3.45, kv=5.37), qwen=dict(weights=34.74, act=2.76, kv=2.45)),
)

T_KO = dict(
    title="GPU 메모리와 동시 실행",
    sub_en=SUB,
    sub_ko="동시 실행 수를 정하는 KV 캐시와 MTP, 동시성 1에서도 넘는 토큰 간격 기준",
    s1=("SLO와 워크로드", "두 기준을 함께 만족하는 최대 동시성 탐색"),
    slo=[("TTFT p99", "500ms 이하", "첫 토큰까지의 시간, 답의 시작 시점"),
         ("ITL p99", "50ms 이하", "토큰 간격, 글자가 이어지는 속도")],
    wl_head=("워크로드", "입력 토큰", "출력 토큰", "측정한 모델"),
    wl=[("S1 짧은 채팅", "256", "128", "Gemma, Qwen"),
        ("S2 요약과 생성", "1,024", "256", "Gemma, Qwen"),
        ("S3 분류", "512", "16", "Gemma"),
        ("S4 장문 RAG", "4,096", "256", "Gemma")],
    conc_label="동시성 단계",
    conc_note="단계마다 요청 수 = 동시성 × 8, 최소 16건, 최대 256건, 프롬프트는 랜덤 토큰",
    s2=("GPU 메모리 배분과 KV 캐시", "가중치와 활성값을 빼고 남는 한 자릿수 GiB"),
    legend=[("purple", "가중치와 비 torch 메모리", False), ("blue", "활성값 최대", False),
            ("yellow", "KV 캐시", False), (None, "사용하지 않는 10%", True)],
    mem_axis=("gpu-memory-utilization 0.90 = 39.95GiB", "44.39GiB"),
    mem_rows=[("gemma", "Gemma 4 31B", "가중치와 비 torch 31.13GiB",
               "KV 캐시 34,052 토큰, 16,384 토큰 요청 2.08개 분량", "5.37GiB", "S1 요청 45건에서 사용률 0.998"),
              ("qwen", "Qwen3.8-27B", "가중치와 비 torch 34.74GiB",
               "KV 캐시 42,780 토큰, 32,768 토큰 요청 1.31개 분량", "2.45GiB", "46블록, MTP 켬은 요청당 13블록")],
    kv_label="KV 캐시",
    formula="KV 캐시 = GPU 메모리 × 0.90 - 가중치와 비 torch 메모리 - 활성값 최대",
    formula_ex="Gemma 44.39 × 0.90 - 31.13 - 3.45 = 5.37GiB,   Qwen 44.39 × 0.90 - 34.74 - 2.76 = 2.45GiB",
    mem_insight=("Qwen은 gpu-memory-utilization 0.85에서 시작 실패",
                 "KV 캐시가 0.24GiB만 남아 기동하지 못했고 0.90에서 2.45GiB 확보"),
    s3=("동시성별 결과", "한도에 닿은 뒤 처리량은 정체, TTFT만 증가 (S1 짧은 채팅)"),
    s3_legend=[("blue", "출력 처리량"), ("pink", "동시 실행 한도 도달")],
    s3_legend_ttft=("500ms 이하", "500ms 초과"),
    gemma=dict(name="Gemma 4 31B", note="동시성 64에서 45건 실행, KV 캐시 사용률 0.998",
               memo=("동시성 32까지 처리량 증가", "64에서는 45건만 실행, 나머지는 대기")),
    qwen=dict(name="Qwen3.8-27B, MTP 켬", note="동시성 4부터 3건 실행, KV 캐시 사용률 0.848",
              memo=("동시성 8 이후 85.0~91.2 tok/s에서 정체", "4번째 요청부터 capacity 사유로 대기")),
    rows3=("동시성", "실행 중 최대", "TTFT p99 ms"),
    unit3="tok/s",
    s3_insight=("ITL p99는 동시성 1에서 이미 기준 50ms 초과",
                "Gemma 57.7ms, Qwen 74.3ms. 부하를 줄여도 내려가지 않는 값으로 GPU와 체크포인트가 결정"),
    s4=("MTP 판단 기준", "동시에 겹치는 요청 수로 선택"),
    mtp_head=("Qwen3.8-27B, S1", "MTP 켬", "MTP 끔"),
    mtp_sub=("", "추측 토큰 3개", ""),
    mtp=[("요청당 KV 캐시 블록", "13", "4", 2),
         ("KV 캐시", "2.45GiB, 46블록", "4.0GiB, 82블록", 2),
         ("동시 실행 한도", "3건", "20건", 2),
         ("요청 하나의 생성 속도", "32.5 tok/s", "19.2 tok/s", 1),
         ("최대 출력 처리량", "91.2 tok/s", "281.8 tok/s", 2),
         ("TTFT p99 500ms 이하 최대 동시성", "2", "8", 2)],
    choice=[("겹치는 요청 3건 이하", "MTP 켬", "요청 하나의 속도 1.7배"),
            ("겹치는 요청 4건 이상", "MTP 끔", "최대 출력 처리량 3.1배")],
    blocks="요청당 블록 = Mamba 그룹 3 × (1 + 추측 토큰 3) + attention 1 = 13",
    note=("2026-11-14와 15일 서울 리전 측정, g6e.4xlarge(L40S 48GB) 2대, vLLM v0.33.0, 랜덤 토큰 프롬프트, 단계마다 1회, "
          "게이트웨이 없이 vLLM Service 직접 호출. MTP 끔은 2026-11-15 측정"),
)

T_EN = dict(
    title="GPU Memory and Concurrent Requests",
    sub_en=SUB,
    sub_ko="What sets concurrency, and a token gap over target even at concurrency 1",
    s1=("SLO and workloads", "Looking for the highest concurrency that meets both"),
    slo=[("TTFT p99", "500 ms or less", "Time to first token, when the answer starts"),
         ("ITL p99", "50 ms or less", "Gap between tokens, how fast text flows")],
    wl_head=("Workload", "Input tokens", "Output tokens", "Models measured"),
    wl=[("S1 Short chat", "256", "128", "Gemma, Qwen"),
        ("S2 Summarize and generate", "1,024", "256", "Gemma, Qwen"),
        ("S3 Classification", "512", "16", "Gemma"),
        ("S4 Long-context RAG", "4,096", "256", "Gemma")],
    conc_label="Concurrency levels",
    conc_note="Requests per level = concurrency × 8, at least 16, at most 256, random-token prompts",
    s2=("GPU memory split and the KV cache", "A single-digit number of GiB is left after weights and activations"),
    legend=[("purple", "Weights and non-torch memory", False), ("blue", "Peak activations", False),
            ("yellow", "KV cache", False), (None, "Unused 10%", True)],
    mem_axis=("gpu-memory-utilization 0.90 = 39.95 GiB", "44.39 GiB"),
    mem_rows=[("gemma", "Gemma 4 31B", "Weights and non-torch 31.13 GiB",
               "KV cache 34,052 tokens, room for 2.08 requests of 16,384 tokens", "5.37 GiB",
               "0.998 used at 45 S1 requests"),
              ("qwen", "Qwen3.8-27B", "Weights and non-torch 34.74 GiB",
               "KV cache 42,780 tokens, room for 1.31 requests of 32,768 tokens", "2.45 GiB",
               "46 blocks, 13 per request with MTP")],
    kv_label="KV cache",
    formula="KV cache = GPU memory × 0.90 - weights and non-torch memory - peak activations",
    formula_ex="Gemma 44.39 × 0.90 - 31.13 - 3.45 = 5.37 GiB,   Qwen 44.39 × 0.90 - 34.74 - 2.76 = 2.45 GiB",
    mem_insight=("Qwen fails to start at gpu-memory-utilization 0.85",
                 "Only 0.24 GiB was left for the KV cache, so it could not start, and 0.90 gave 2.45 GiB"),
    s3=("Results by concurrency", "Past the limit only TTFT grows (S1)"),
    s3_legend=[("blue", "Throughput"), ("pink", "At the concurrency limit")],
    s3_legend_ttft=("500 ms or less", "over 500 ms"),
    gemma=dict(name="Gemma 4 31B", note="45 running at concurrency 64, KV usage 0.998",
               memo=("Throughput grows up to concurrency 32", "At 64 only 45 run and the rest wait")),
    qwen=dict(name="Qwen3.8-27B, MTP on", note="3 running from concurrency 4, KV usage 0.848",
              memo=("Flat at 85.0~91.2 tok/s from concurrency 8", "The 4th request waits, reason capacity")),
    rows3=("Concurrency", "Running (max)", "TTFT p99 ms"),
    unit3="tok/s",
    s3_insight=("ITL p99 is over the 50 ms target already at concurrency 1",
                "Gemma 57.7 ms, Qwen 74.3 ms. Lower load does not bring it down, the GPU and the checkpoint set it"),
    s4=("When to use MTP", "Choose by how many requests overlap"),
    mtp_head=("Qwen3.8-27B, S1", "MTP on", "MTP off"),
    mtp_sub=("", "3 speculative tokens", ""),
    mtp=[("KV cache blocks per request", "13", "4", 2),
         ("KV cache size, blocks", "2.45 GiB, 46", "4.0 GiB, 82", 2),
         ("Concurrency limit", "3", "20", 2),
         ("Speed of one request", "32.5 tok/s", "19.2 tok/s", 1),
         ("Peak output throughput", "91.2 tok/s", "281.8 tok/s", 2),
         ("Max concurrency within TTFT p99 500 ms", "2", "8", 2)],
    choice=[("3 or fewer overlapping requests", "MTP on", "1.7x speed per request"),
            ("4 or more overlapping requests", "MTP off", "3.1x peak output throughput")],
    blocks="Blocks per request = 3 Mamba groups × (1 + 3 speculative tokens) + 1 attention = 13",
    note=("Measured 2026-11-14 and 15, Seoul Region, two g6e.4xlarge (L40S 48 GB), vLLM v0.33.0, random-token prompts, "
          "one run per level, direct calls to the vLLM Service without the gateway. MTP off: 2026-11-15"),
)

T = pick_lang(T_KO, T_EN)


def fmt(v):
    return f"{v:,.1f}"


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    cwd = (iw - 16) / 2
    for i, (name, limit, desc) in enumerate(T["slo"]):
        cx = ix + i * (cwd + 16)
        d.rect(cx, cy + 4, cwd, 78, rx=10, fill="orangeF", fo=0.08, stroke="orange", sw=1.2)
        d.text(cx + 16, cy + 35, name, 16, 700, "text", box=box)
        d.text(cx + cwd - 16, cy + 37, limit, 22, 700, "orange", "end", box=box)
        d.text(cx + 16, cy + 63, desc, 13, 400, "muted", box=box)
    # workload table
    ty = cy + 98
    cols = (ix + 14, ix + 322, ix + 440, ix + 482)
    d.rect(ix, ty, iw, 28, rx=6, fill="panel")
    for j, head in enumerate(T["wl_head"]):
        d.text(cols[j], ty + 19, head, 13, 400, "muted", "end" if j in (1, 2) else "start", box=box)
    for i, row in enumerate(T["wl"]):
        mid = ty + 28 + i * 32 + 16
        if i:
            d.line(ix, mid - 16, ix + iw, mid - 16, stroke="cardline", sw=1)
        d.text(cols[0], mid + 5, row[0], 15, 700, "text", box=box)
        d.text(cols[1], mid + 5, row[1], 15, 400, "text2", "end", box=box)
        d.text(cols[2], mid + 5, row[2], 15, 400, "text2", "end", box=box)
        d.text(cols[3], mid + 5, row[3], 14, 400, "text2", box=box)
    # concurrency levels
    ry = ty + 28 + 4 * 32 + 14
    d.text(ix, ry + 17, T["conc_label"], 13, 400, "muted", box=box)
    px = ix + rw(T["conc_label"], 13) + 14
    for c in M["conc"]:
        d.rect(px, ry, 44, 24, rx=12, fill="blueF", fo=0.12, stroke="blue", sw=1.1)
        d.text(px + 22, ry + 16.5, str(c), 13, 700, "blue", "middle", box=box)
        px += 50
    d.text(ix, ry + 50, T["conc_note"], 13, 400, "muted", box=box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    lx = ix
    for color, label, dashed in T["legend"]:
        if dashed:
            d.rect(lx, cy, 14, 14, rx=3, fill="none", stroke="faint", sw=1.2, dash="3 3")
        else:
            d.rect(lx, cy, 14, 14, rx=3, fill=color + "F", fo=0.9)
        d.text(lx + 21, cy + 12, label, 13, 400, "text2", box=box)
        lx += 21 + rw(label, 13) + 24
    bx, bw, bh = ix + 126, 664, 38
    s = bw / M["device"]
    tx = bx + M["target"] * s
    tops = (cy + 52, cy + 128)
    # the 0.90 line and its labels
    d.line(tx, tops[0] - 10, tx, tops[1] + bh + 6, stroke="faint", sw=1.2, dash="4 4")
    d.text(tx - 8, cy + 38, T["mem_axis"][0], 12, 400, "muted", "end", box=box)
    d.text(bx + bw, cy + 38, T["mem_axis"][1], 12, 400, "muted", "end", box=box)
    for (key, name, wlabel, sub, kv, kvnote), by in zip(T["mem_rows"], tops):
        m = M["mem"][key]
        d.text(ix, by + bh / 2 + 5, name, 15, 700, "text", box=box)
        x1 = bx + m["weights"] * s
        x2 = x1 + m["act"] * s
        d.rect(bx, by, bw, bh, rx=5, fill="none", stroke="faint", sw=1.1, dash="4 4")
        d.rect(bx, by, x1 - bx, bh, rx=5, fill="purpleF", fo=0.9)
        d.rect(x1 + 1.5, by, x2 - x1 - 1.5, bh, fill="blueF", fo=0.9)
        d.rect(x2 + 1.5, by, tx - x2 - 1.5, bh, fill="yellowF", fo=0.95)
        d.text(bx + 14, by + bh / 2 + 5, wlabel, 14, 700, "badgetext", box=box)
        d.text((x1 + x2) / 2 + 1, by + bh / 2 + 4.5, f"{m['act']:.2f}", 12, 700, "badgetext", "middle", box=box)
        d.text((x2 + tx) / 2 + 1, by + bh / 2 + 4.5, f"{m['kv']:.2f}", 12, 700, "onwarm", "middle", box=box)
        d.text(bx, by + bh + 18, sub, 13, 400, "muted", box=box)
        rx_ = bx + bw + 22
        d.runs(rx_, by + 17, [(T["kv_label"], 13, 400, "muted"), (kv, 19, 700, "yellow", 8)], box=box)
        d.text(rx_, by + 37, kvnote, 13, 400, "text2", box=box)
    d.text(ix, cy + 216, T["formula"], 14, 700, "text", box=box)
    d.text(ix, cy + 238, T["formula_ex"], 13, 400, "muted", box=box)
    callout(d, ix, y + h - 20 - 58, iw, *T["mem_insight"], color="pink", box=box)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    # legend, right side of the heading line
    lx = x + w - 24
    ok, bad = T["s3_legend_ttft"]
    for text, color in ((bad, "pink"), (ok, "green")):
        lx -= rw(text, 12, 700)
        d.text(lx, y + 38, text, 12, 700, color, box=box)
        lx -= 10
    lx -= rw("TTFT p99", 12)
    d.text(lx, y + 38, "TTFT p99", 12, 400, "muted", box=box)
    lx -= 22
    for color, label in reversed(T["s3_legend"]):
        lx -= rw(label, 12)
        d.text(lx, y + 38, label, 12, 400, "muted", box=box)
        lx -= 19
        d.rect(lx, y + 27, 13, 13, rx=3, fill=color + "F", fo=0.85)
        lx -= 18
    lab, gap = 104, 28
    pw = (iw - lab - gap) / 2
    top, base = y + 128, y + 306
    ymax = 450
    d.text(ix + lab - 12, top - 12, T["unit3"], 12, 400, "faint", "end", box=box)
    for pi, key in enumerate(("gemma", "qwen")):
        px = ix + lab + pi * (pw + gap)
        m = M[key]
        twd = tag(d, px, cy + 2, T[key]["name"], "purple", 13, 24, 10, box=box)
        d.text(px + twd + 10, cy + 19, T[key]["note"], 13, 400, "muted", box=box)
        for v in (0, 100, 200, 300, 400):
            gy = base - v / ymax * (base - top)
            d.line(px, gy, px + pw, gy, stroke="cardline" if v else "line2", sw=1)
            if pi == 0:
                d.text(ix + lab - 12, gy + 4, str(v), 12, 400, "faint", "end", box=box)
        memo, memo2 = T[key]["memo"]
        # placed between and above the grid lines (400 at top + 20, 300 at top + 59)
        d.text(px + 14, top + 13, memo, 14, 700, "pink" if key == "qwen" else "blue", box=box)
        d.text(px + 14, top + 42, memo2, 13, 400, "muted", box=box)
        step = pw / len(M["conc"])
        for i, c in enumerate(M["conc"]):
            bx = px + i * step + step / 2
            v = m["tput"][i]
            bh = v / ymax * (base - top)
            limit = i >= m["limit_from"]
            d.rect(bx - 17, base - bh, 34, bh, rx=3, fill="pinkF" if limit else "blueF", fo=0.85)
            d.text(bx, base - bh - 6, f"{v:.1f}", 12, 700, "pink" if limit else "text", "middle", box=box)
            d.text(bx, base + 21, str(c), 13, 700, "text2", "middle", box=box)
            d.text(bx, base + 45, str(m["running"][i]), 13, 700, "pink" if limit else "text", "middle", box=box)
            good = m["ttft"][i] <= M["ttft_slo"]
            d.text(bx, base + 69, fmt(m["ttft"][i]), 12, 700, "green" if good else "pink", "middle", box=box)
    for j, label in enumerate(T["rows3"]):
        d.text(ix, base + 21 + j * 24, label, 13, 400, "muted", box=box)
    callout(d, ix, y + h - 20 - 58, iw, *T["s3_insight"], box=box)


def s4(d, x, y, w, h):
    cy = section(d, x, y, w, h, 4, *T["s4"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    c1, c2, c3 = ix + 14, ix + 424, ix + 574
    ty = cy + 2
    d.rect(ix, ty, iw, 30, rx=6, fill="panel")
    d.text(c1, ty + 20, T["mtp_head"][0], 13, 400, "muted", box=box)
    d.runs(c2, ty + 20, [(T["mtp_head"][1], 13, 700, "text"), (T["mtp_sub"][1], 12, 400, "muted", 6)], "middle",
           box=box)
    d.text(c3, ty + 20, T["mtp_head"][2], 13, 700, "text", "middle", box=box)
    rh = 34
    for i, (label, on, off, win) in enumerate(T["mtp"]):
        mid = ty + 30 + i * rh + rh / 2
        if i:
            d.line(ix, mid - rh / 2, ix + iw, mid - rh / 2, stroke="cardline", sw=1)
        d.text(c1, mid + 5, label, 14, 400, "text2", box=box)
        d.text(c2, mid + 5, on, 15, 700, "green" if win == 1 else "text", "middle", box=box)
        d.text(c3, mid + 5, off, 15, 700, "green" if win == 2 else "text", "middle", box=box)
    # the two choices
    gy = ty + 30 + len(T["mtp"]) * rh + 18
    cwd = (iw - 16) / 2
    for i, (cond, pick, why) in enumerate(T["choice"]):
        cx = ix + i * (cwd + 16)
        d.rect(cx, gy, cwd, 96, rx=10, fill="greenF", fo=0.07, stroke="green", sw=1.2)
        tag(d, cx + 14, gy + 12, cond, "orange", 13, 24, 10, box=box)
        d.text(cx + 16, gy + 64, pick, 20, 700, "text", box=box)
        d.text(cx + 16, gy + 84, why, 13, 400, "green", box=box)
    d.text(ix, y + h - 22, T["blocks"], 13, 400, "muted", box=box)


def landscape(theme):
    d = Doc(W, H, theme)
    d.rect(0, 0, W, H, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "2")
    s1(d, 48, 140, 700, 404)
    s2(d, 768, 140, 1104, 404)
    s3(d, 48, 564, 1104, 480)
    s4(d, 1172, 564, 700, 480)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
