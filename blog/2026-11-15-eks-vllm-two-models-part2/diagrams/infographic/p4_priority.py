"""Part 2, figure 4: the two layers where priority works, the gateway (EPP and InferenceObjective) and the engine
(priority scheduling in vLLM).

Numbers are from the priority table of the post (2026-11-14, Gemma 4 31B, one 90 s run per case).
The number of requests drawn in the queues is illustrative.
Layout is the same as ow-on-gpu/blog/2026-11-15-eks-vllm-two-models-part3/diagrams/infographic/priority_layers.py.
"""
from infokit import Doc, F, callout, cell, check, cross, footer_note, header, para, series_nav
from common import SERIES, SUB, pick
from p3kit import EC2, EKS, chip, code, sec

K = 1.3

T_KO = dict(
    title="우선순위가 작동하는 두 층",
    sub_en=SUB,
    sub_ko="배치 부하에서 상담 요청이 기다리는 자리",
    s1=("요청이 기다리는 자리", "게이트웨이는 거절, 엔진은 순서 변경"),
    s2=("4가지 경우의 상담 TTFT", "p50, 배치 32개 부하"),
    s3=("두 층의 설정값", "게이트웨이는 큰 값이 먼저, 엔진은 작은 값이 먼저"),
    interactive=("상담 요청", "1.5초마다 1건"),
    batch=("배치 요청", "32개를 끊임없이"),
    retry=("429를 받으면", "0.5초 뒤 재전송"),
    gateway=("게이트웨이", "agentgateway, EPP"),
    objectives=[
        ("gemma-interactive", "priority 10", "포화해도 통과", True),
        ("gemma-batch", "priority -1", "풀 포화 시 429로 거절", False),
    ],
    gateway_note="flow control을 켜지 않은 기본 상태: priority 0 미만만 거절, 게이트웨이에는 대기열 없음",
    engine=("엔진", "vLLM, Gemma 4 31B"),
    engine_flag="--scheduling-policy=priority",
    queues=[
        ("본문에 priority가 없으면: 도착한 순서", ["i", "b", "b", "b", "b"],
         "상담이 배치 뒤에서 대기, TTFT p50 [pink]{30.9초}"),
        ("본문에 priority가 있으면: 값이 작은 요청 먼저", ["b", "b", "b", "b", "i"],
         "상담이 대기열 맨 앞으로, TTFT p50 [green]{0.19초}"),
    ],
    queue_ends=("늦게 도착", "먼저 실행"),
    chip=dict(i="상담", b="배치"),
    running=("실행 중", "KV 캐시 한도"),
    engine_note="처리 순서만 바뀌고 배치의 출력 처리량은 4가지 경우 모두 초당 159~176토큰",
    matrix_cols=("엔진 priority 없음", "엔진 priority 지정"),
    # each row head is two lines
    matrix_rows=(("게이트웨이", "objective 없음"), ("게이트웨이", "objective 지정")),
    # name, p50, 429 rejections, average engine queue, color
    matrix=[
        [("우선순위 없음", "30.9초", "429 거절 0건", "엔진 대기 31.0", "pink"),
         ("엔진만", "0.19초", "429 거절 0건", "엔진 대기 17.9", "green")],
        [("게이트웨이만", "11.2초", "429 거절 1,907건", "엔진 대기 15.3", "orange"),
         ("두 층 모두", "0.19초", "429 거절 1,988건", "엔진 대기 9.3", "green")],
    ],
    insight=("대기를 없앤 것은 엔진 priority", "게이트웨이는 배치를 거절해 엔진 대기열을 줄이는 역할"),
    table_head=("층", "지정하는 곳", "상담 요청", "배치 요청", "포화했을 때의 동작", "측정에서 확인한 효과"),
    # layer, where it is set (text, code), interactive (code), batch (code), behavior, effect
    table=[
        ("게이트웨이", "EPP", "요청 헤더로 InferenceObjective 선택", "x-llm-d-inference-objective",
         "gemma-interactive", "priority 10", "gemma-batch", "priority -1",
         "priority 0 미만인 요청을 대기 없이 429로 거절", "엔진 대기 31.0에서 15.3, 상담 p50 11.2초"),
        ("엔진", "vLLM", "요청 본문의 값", "priority",
         "0", "", "10", "",
         "값이 작은 요청을 먼저 실행", "상담 p50 30.9초에서 0.19초"),
    ],
    note=("2026-11-14 서울 리전, Gemma 4 31B. 배치 요청(입력 평균 1,845토큰, 출력 최대 256토큰) 32개 부하에 상담 60건, 경우마다 90초씩 1회 측정. "
          "대기열에 그린 요청 수는 설명용"),
)

T_EN = dict(
    title="Two Layers Where Priority Works",
    sub_en=SUB,
    sub_ko="Where an interactive request waits under batch load",
    s1=("Where a request waits", "The gateway rejects, the engine reorders"),
    s2=("Interactive TTFT", "p50 in four cases"),
    s3=("Settings in the two layers", "Gateway: larger value first, engine: smaller value first"),
    interactive=("Interactive", "1 every 1.5 s"),
    batch=("Batch", "32 at all times"),
    retry=("On a 429,", "resend after 0.5 s"),
    gateway=("Gateway", "agentgateway, EPP"),
    objectives=[
        ("gemma-interactive", "priority 10", "Passes when saturated", True),
        ("gemma-batch", "priority -1", "429 when saturated", False),
    ],
    gateway_note="Default without flow control: only priority below 0 is rejected, and the gateway has no queue",
    engine=("Engine", "vLLM, Gemma 4 31B"),
    engine_flag="--scheduling-policy=priority",
    queues=[
        ("No priority in the body: arrival order", ["i", "b", "b", "b", "b"],
         "Interactive waits behind batch, TTFT p50 [pink]{30.9 s}"),
        ("priority in the body: smaller value first", ["b", "b", "b", "b", "i"],
         "Interactive moves to the front, TTFT p50 [green]{0.19 s}"),
    ],
    queue_ends=("Arrived last", "Runs first"),
    chip=dict(i="Int.", b="Batch"),
    running=("Running", "KV cache limit"),
    engine_note="Only the order changes: batch output throughput is 159~176 tokens per second in all four cases",
    matrix_cols=("No engine priority", "Engine priority set"),
    matrix_rows=(("No gateway", "objective"), ("Gateway", "objective set")),
    matrix=[
        [("No priority", "30.9 s", "429 rejected: 0", "Engine queue 31.0", "pink"),
         ("Engine only", "0.19 s", "429 rejected: 0", "Engine queue 17.9", "green")],
        [("Gateway only", "11.2 s", "429 rejected: 1,907", "Engine queue 15.3", "orange"),
         ("Both layers", "0.19 s", "429 rejected: 1,988", "Engine queue 9.3", "green")],
    ],
    insight=("Engine priority removed the wait", "The gateway rejects batch and shortens the engine queue"),
    table_head=("Layer", "Set in", "Interactive", "Batch", "When saturated", "Effect measured"),
    table=[
        ("Gateway", "EPP", "Request header picks an InferenceObjective", "x-llm-d-inference-objective",
         "gemma-interactive", "priority 10", "gemma-batch", "priority -1",
         "Rejects requests with priority below 0 with 429, no waiting",
         "Engine queue 31.0 to 15.3, interactive p50 11.2 s"),
        ("Engine", "vLLM", "Value in the request body", "priority",
         "0", "", "10", "",
         "Runs requests with a smaller value first", "Interactive p50 30.9 s to 0.19 s"),
    ],
    note=("2026-11-14, Seoul Region, Gemma 4 31B. 60 interactive requests under a load of 32 batch requests "
          "(1,845 input tokens on average, up to 256 output tokens), one 90 s run per case. "
          "The number of requests drawn in the queues is illustrative"),
)

T = pick(T_KO, T_EN)

COLOR = dict(i="orange", b="blue")


def source(d, x, y, w, h, title, sub, color, box):
    d.rect(x, y, w, h, rx=12, fill=color + "F", fo=0.12, stroke=color, sw=1.6)
    d.text(x + w / 2, y + h / 2 - 4, title, F(16, K), 700, "text", "middle", box=box)
    d.text(x + w / 2, y + h / 2 + 22, sub, F(12, K), 400, "muted", "middle", box=box)


def s1(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 1, *T["s1"], k=K)
    box = (x, y, w, h)
    sx, sw_ = x + 24, 184          # senders
    gx, gw = sx + sw_ + 60, 310     # gateway
    ex = gx + gw + 56               # engine
    ew = x + w - 24 - ex
    top, bottom = cy + 6, y + h - 22
    bh = bottom - top

    # gateway
    gbox = (gx, top, gw, bh)
    d.rect(gx, top, gw, bh, rx=14, fill="panel", stroke="purple", sw=1.6)
    d.icon(EKS, gx + 16, top + 14, 36)
    d.text(gx + 64, top + 34, T["gateway"][0], F(17, K), 700, "text", box=gbox)
    d.text(gx + 64, top + 58, T["gateway"][1], F(12, K), 400, "muted", box=gbox)
    rows_y = [top + 88, top + 228]
    rh = 112
    for (name, prio, result, ok), ry in zip(T["objectives"], rows_y):
        color = "green" if ok else "pink"
        d.rect(gx + 16, ry, gw - 32, rh, rx=10, fill="card", stroke="cardline", sw=1.2)
        code(d, gx + 30, ry + 32, name, F(13, K), "text", box=gbox)
        d.text(gx + 30, ry + 60, prio, F(13, K), 700, "purple", box=gbox)
        (check if ok else cross)(d, gx + 30, ry + 78, 16, color)
        d.text(gx + 56, ry + 93, result, F(13, K), 700, color, box=gbox)
    para(d, gx + 18, rows_y[1] + rh + 34, gw - 36, T["gateway_note"], F(11.5, K), 21, 400, "muted", box=gbox)

    # senders. Interactive lines up with the upper objective and batch with the lower one.
    src_h = 84
    iy = rows_y[0] + rh / 2 - src_h / 2
    by = rows_y[1] + rh / 2 - src_h / 2
    source(d, sx, iy, sw_, src_h, *T["interactive"], "orange", box)
    source(d, sx, by, sw_, src_h, *T["batch"], "blue", box)
    d.arrow([(sx + sw_, iy + src_h / 2), (gx, iy + src_h / 2)], color="orange", sw=2.4)
    d.arrow([(sx + sw_, by + 26), (gx, by + 26)], color="blue", sw=2.4)
    d.arrow([(gx, by + 60), (sx + sw_, by + 60)], color="pink", sw=2.4, dash="6 5")
    d.text(sx + sw_ + 30, by + 84, "429", F(13, K), 700, "pink", "middle", box=box)
    for i, line in enumerate(T["retry"]):
        d.text(sx + sw_ / 2, by + src_h + 30 + i * 22, line, F(12, K), 400, "muted", "middle", box=box)

    # engine
    ebox = (ex, top, ew, bh)
    d.rect(ex, top, ew, bh, rx=14, fill="panel", stroke="purple", sw=1.6)
    d.icon(EC2, ex + 16, top + 14, 36)
    d.text(ex + 64, top + 34, T["engine"][0], F(17, K), 700, "text", box=ebox)
    d.text(ex + 64, top + 58, T["engine"][1], F(12, K), 400, "muted", box=ebox)
    code(d, ex + ew - 18, top + 36, T["engine_flag"], F(11.5, K), "purple", "end", box=ebox)
    cw_, ch, cg = 58, 40, 6
    run_w = 118
    qx = ex + 20
    q_right = qx + 5 * cw_ + 4 * cg
    run_x = ex + ew - 20 - run_w
    q_tops = [top + 122, top + 268]
    for (label, order, result), qy in zip(T["queues"], q_tops):
        d.text(qx, qy - 16, label, F(12.5, K), 700, "text2", box=ebox)
        for index, kind in enumerate(order):
            chip(d, qx + index * (cw_ + cg), qy, cw_, ch, T["chip"][kind], COLOR[kind], F(11.5, K),
                 fo=0.2 if kind == "i" else 0.12, sw=2 if kind == "i" else 1.2, box=ebox)
        d.arrow([(q_right + 6, qy + ch / 2), (run_x - 4, qy + ch / 2)], sw=2)
        d.rect(run_x, qy - 6, run_w, ch + 12, rx=8, fill="yellowF", fo=0.14, stroke="yellow", sw=1.4)
        d.text(run_x + run_w / 2, qy + 16, T["running"][0], F(11.5, K), 700, "text", "middle", box=ebox)
        d.text(run_x + run_w / 2, qy + 35, T["running"][1], F(10, K), 400, "muted", "middle", box=ebox)
        d.text(qx, qy + ch + 22, T["queue_ends"][0], F(10.5, K), 400, "faint", box=ebox)
        d.text(q_right, qy + ch + 22, T["queue_ends"][1], F(10.5, K), 400, "faint", "end", box=ebox)
        d.text(qx, qy + ch + 52, result, F(13, K), 700, "text", box=ebox)
    para(d, ex + 20, q_tops[1] + ch + 96, ew - 40, T["engine_note"], F(11.5, K), 21, 400, "muted", box=ebox)

    # requests that pass the gateway enter one queue
    mid = (iy + src_h / 2 + by + 26) / 2
    bend = gx + gw + 26
    d.arrow([(gx + gw, iy + src_h / 2), (bend, iy + src_h / 2), (bend, mid - 9), (ex, mid - 9)], color="orange", sw=2.4)
    d.arrow([(gx + gw, by + 26), (bend, by + 26), (bend, mid + 9), (ex, mid + 9)], color="blue", sw=2.4)


def s2(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 2, *T["s2"], k=K)
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    insight_h = 58 * K
    head_w, head_h, gap = 132, 46, 12
    cell_w = (iw - head_w - gap) / 2
    grid_top = cy + 4
    cell_h = (y + h - 20 - insight_h - 16 - grid_top - head_h - gap) / 2
    for col, text in enumerate(T["matrix_cols"]):
        cx = ix + head_w + col * (cell_w + gap)
        d.rect(cx, grid_top, cell_w - gap, head_h, rx=8, fill="purpleF", fo=0.1, stroke="purple", sw=1.1)
        d.text(cx + (cell_w - gap) / 2, grid_top + head_h / 2 + 6, text, F(12, K), 700, "purple", "middle", box=box)
    for row, text in enumerate(T["matrix_rows"]):
        ry = grid_top + head_h + gap + row * (cell_h + gap)
        d.rect(ix, ry, head_w - gap, cell_h - gap, rx=8, fill="purpleF", fo=0.1, stroke="purple", sw=1.1)
        for i, line in enumerate(text):
            d.text(ix + (head_w - gap) / 2, ry + (cell_h - gap) / 2 - 4 + i * 22, line, F(12, K), 700, "purple", "middle",
                   box=box)
        for col, (name, p50, rejected, waiting, color) in enumerate(T["matrix"][row]):
            cx = ix + head_w + col * (cell_w + gap)
            cw2, ch2 = cell_w - gap, cell_h - gap
            d.rect(cx, ry, cw2, ch2, rx=10, fill=color + "F", fo=0.09, stroke=color, sw=1.5)
            d.text(cx + 16, ry + 30, name, F(12.5, K), 700, "text", box=box)
            d.text(cx + 16, ry + 74, p50, F(26, K), 700, color, box=box)
            d.text(cx + 16, ry + ch2 - 38, rejected, F(11.5, K), 400, "muted", box=box)
            d.text(cx + 16, ry + ch2 - 16, waiting, F(11.5, K), 400, "muted", box=box)
    callout(d, ix, y + h - 20 - insight_h, iw, *T["insight"], k=K, color="green", box=box)


def s3(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 3, *T["s3"], k=K)
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    cols = [0, 200, 620, 890, 1140, 1470]  # x where each column starts, relative to ix
    head_h = 34
    d.rect(ix, cy, iw, head_h, rx=8, fill="panel")
    for cx, text in zip(cols, T["table_head"]):
        d.text(ix + cx + 12, cy + 23, text, F(11.5, K), 400, "muted", box=box)
    rh = (y + h - 14 - cy - head_h) / len(T["table"])
    size, small = F(13, K), F(11.5, K)
    for index, (layer, impl, where, where_code, ic, ip, bc, bp, action, effect) in enumerate(T["table"]):
        ry = cy + head_h + index * rh
        mid = ry + rh / 2
        if index:
            d.line(ix, ry, ix + iw, ry, stroke="cardline", sw=1)
        d.text(ix + 12, mid - 2, layer, F(15, K), 700, "purple", box=box)
        d.text(ix + 12, mid + 20, impl, small, 400, "muted", box=box)
        d.text(ix + cols[1] + 12, mid - 2, where, size, 400, "text2", box=box)
        code(d, ix + cols[1] + 12, mid + 20, where_code, small, "muted", box=box)
        for cx, value, extra, color in ((cols[2], ic, ip, "orange"), (cols[3], bc, bp, "blue")):
            if extra:
                code(d, ix + cx + 12, mid - 2, value, size, color, box=box)
                d.text(ix + cx + 12, mid + 20, extra, small, 700, color, box=box)
            else:
                d.text(ix + cx + 12, mid + 8, f"priority {value}", size, 700, color, box=box)
        cell(d, ix + cols[4] + 12, mid + 2, cols[5] - cols[4] - 24, action, size, 23, 400, "text2", box, K)
        cell(d, ix + cols[5] + 12, mid + 2, iw - cols[5] - 24, effect, size, 23, 700, "text", box, K)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "2")
    s1(d, 48, 140, 1180, 562)
    s2(d, 1248, 140, 624, 562)
    s3(d, 48, 722, 1824, 322)
    footer_note(d, 1872, 1064, T["note"], size=12)
    return d.svg()
