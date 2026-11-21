"""Part 2, figure 5: sleep and wake for Qwen3.8-27B. The weekday schedule, a request that arrives during sleep,
and how a sleeping pod is taken out of the targets.

Numbers are from the sleep tables of the post and the paragraphs under them.
  sleep entry 2.977~2.981 s, wake 3.655~3.662 s, Service after wake 1.115~1.169 s: 2026-11-14, 5 runs on one pod
  request to a sleeping Qwen (wake 3,662 ms, response headers 3.91 s, first content 4.06 s): 2026-11-15, one run
  wake check while awake 12.8 ms: 2026-11-15, median of 20
Layout is the same as ow-on-gpu/blog/2026-11-15-eks-vllm-two-models-part3/diagrams/infographic/sleep_wake.py.
"""
from infokit import Doc, F, callout, check, cross, footer_note, header, para, series_nav
from common import SERIES, SUB, pick
from p3kit import EC2, EKS, code, sec, stat

K = 1.3

T_KO = dict(
    title="Qwen3.8-27B의 sleep과 깨우기",
    sub_en=SUB,
    sub_ko="업무 시간 밖에는 재우고 요청이 오면 깨우는 흐름",
    s1=("평일 하루의 상태", "CronJob 두 개가 재우고 깨움, 파드와 노드는 그대로"),
    s2=("잠든 동안 들어온 요청", "BFF가 깨우기 API를 먼저 호출"),
    s3=("잠든 파드의 대상 제외", "/health 대신 /is_sleeping"),
    # hour, name, detail, color
    marks=[
        (8.5, "08:30 CronJob qwen-wake", "깨우기 API 호출, 복귀 3.66초", "green"),
        (19.0, "19:00 CronJob qwen-sleep", "level 1 sleep 진입 2.98초", "muted"),
    ],
    # start, end, text, serving or not
    bands=[
        (0.0, 8.5, "sleep, GPU 메모리 2,299MiB", False),
        (8.5, 19.0, "서빙, GPU 메모리 40,899MiB", True),
        (19.0, 24.0, "sleep, 2,299MiB", False),
    ],
    day_notes=[
        "mode=wait: 진행 중인 요청이 끝난 뒤에 잠듦",
        "파드가 뜬 뒤의 첫 sleep만 31.7초",
        "노드 요금은 그대로, 줄어드는 것은 GPU 메모리",
    ],
    # icon, name, text, bottom line (code font or not)
    steps=[
        (EKS, "BFF", "Qwen으로 가는 요청 앞에 깨우기 API를 먼저 호출", "POST /wake", True),
        (EKS, "깨우기 API", "잠들었는지 확인하고 잠들어 있으면 깨움", "/is_sleeping, /wake_up", True),
        (EC2, "Qwen vLLM", "가중치를 GPU로 다시 올리고 Ready로 복귀", "복귀 3.66초", False),
        (EKS, "BFF, 게이트웨이", "게이트웨이가 503이면 다시 시도한 뒤 스트리밍", "0.2초 간격, 최대 10초", False),
    ],
    bar_title="잠든 Qwen에 보낸 코딩 요청 한 건",
    # end time in seconds, color
    bar=[(3.662, "yellow"), (3.91, "purple"), (4.06, "blue")],
    bar_inside="깨우기 API 호출 3,662ms",
    bar_marks=("응답 헤더 3.91초", "첫 내용 4.06초"),
    stats=[
        ("0.02초", "잠든 동안 게이트웨이의 503 응답", "pink"),
        ("12.8ms", "깨어 있을 때의 깨우기 확인 호출", "green"),
        ("123초", "파드를 다시 띄우는 웜 재시작", "orange"),
    ],
    probes=[
        ("GET /health", "sleep 중에도 200 반환, 판정에 사용 불가", False),
        ("exec probe: /is_sleeping", "잠들면 NotReady, 일반 Service에서 제외", True),
    ],
    services=[
        ("일반 Service", ["Ready인 파드만 등록", "게이트웨이와 EPP가 사용", "복귀 뒤 응답까지 1.1~1.2초"], "line2"),
        ("관리용 헤드리스 Service", ["NotReady 주소도 반환", "깨우기 API와 재우기 CronJob이 사용", "/sleep, /wake_up 전용 경로"], "purple"),
    ],
    insight=("깨우기 API는 깨우는 동작만 제공", "NetworkPolicy로 BFF와 깨우기 CronJob 파드만 허용"),
    note=("서울 리전. sleep 진입, 복귀, Service 응답은 2026-11-14 같은 파드에서 5회, 요청 한 건의 시간은 2026-11-15 1회, 12.8ms는 20건의 중앙값. "
          "일정은 Asia/Seoul 기준이고 두 CronJob은 수동 실행으로 확인"),
)

T_EN = dict(
    title="Sleep and Wake for Qwen3.8-27B",
    sub_en=SUB,
    sub_ko="Asleep outside business hours, woken when a request arrives",
    s1=("State over a weekday", "Two CronJobs put it to sleep and wake it, the pod and the node stay"),
    s2=("A request that arrives during sleep", "The BFF calls the wake API first"),
    s3=("Excluding a sleeping pod", "by /is_sleeping"),
    marks=[
        (8.5, "08:30 CronJob qwen-wake", "Calls the wake API, wake 3.66 s", "green"),
        (19.0, "19:00 CronJob qwen-sleep", "Enters level 1 sleep in 2.98 s", "muted"),
    ],
    bands=[
        (0.0, 8.5, "Sleep, GPU memory 2,299 MiB", False),
        (8.5, 19.0, "Serving, GPU memory 40,899 MiB", True),
        (19.0, 24.0, "Sleep, 2,299 MiB", False),
    ],
    day_notes=[
        "mode=wait: sleeps after in-flight requests finish",
        "Only the first sleep after the pod starts takes 31.7 s",
        "Node cost stays the same, what drops is GPU memory",
    ],
    steps=[
        (EKS, "BFF", "Calls the wake API before any request that goes to Qwen", "POST /wake", True),
        (EKS, "Wake API", "Checks whether it is asleep and wakes it if so", "/is_sleeping, /wake_up", True),
        (EC2, "Qwen vLLM", "Loads the weights back onto the GPU and returns to Ready", "Wake 3.66 s", False),
        (EKS, "BFF, gateway", "Retries while the gateway returns 503, then streams", "Every 0.2 s, up to 10 s", False),
    ],
    bar_title="One coding request sent to a sleeping Qwen",
    bar=[(3.662, "yellow"), (3.91, "purple"), (4.06, "blue")],
    bar_inside="Wake API call 3,662 ms",
    bar_marks=("Response headers 3.91 s", "First content 4.06 s"),
    stats=[
        ("0.02 s", "Gateway 503 while it is asleep", "pink"),
        ("12.8 ms", "Wake check call when it is awake", "green"),
        ("123 s", "Warm restart that recreates the pod", "orange"),
    ],
    probes=[
        ("GET /health", "Returns 200 during sleep too, unusable for the check", False),
        ("exec probe: /is_sleeping", "NotReady when asleep, removed from the regular Service", True),
    ],
    services=[
        ("Regular Service", ["Registers Ready pods only", "Used by the gateway and EPP", "Answers 1.1~1.2 s after wake"], "line2"),
        ("Headless admin Service", ["Returns NotReady addresses too", "For wake API and sleep CronJob", "Only for /sleep and /wake_up"],
         "purple"),
    ],
    insight=("The wake API can only wake", "NetworkPolicy allows only the BFF and the wake CronJob pods"),
    note=("Seoul Region. Sleep entry, wake and Service response: 5 runs on one pod on 2026-11-14. The single request: one run on "
          "2026-11-15, and 12.8 ms is the median of 20. The schedule is in Asia/Seoul, and the two CronJobs were verified by "
          "running them manually"),
)

T = pick(T_KO, T_EN)


def s1(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 1, *T["s1"], k=K)
    box = (x, y, w, h)
    ax0, per_hour = x + 48, (w - 96) / 24
    band_y, band_h = cy + 68, 56

    def at(hour):
        return ax0 + hour * per_hour

    for start, end, text, serving in T["bands"]:
        bx, bw = at(start), at(end) - at(start)
        if serving:
            d.rect(bx, band_y, bw, band_h, rx=8, fill="greenF", fo=0.18, stroke="green", sw=1.6)
        else:
            d.rect(bx, band_y, bw, band_h, rx=8, fill="line2", fo=0.35, stroke="line2", sw=1.2, dash="6 5")
        d.text(bx + bw / 2, band_y + band_h / 2 + 7, text, F(14, K), 700, "text" if serving else "muted", "middle", box=box)
    for hour, name, detail, color in T["marks"]:
        mx = at(hour)
        d.line(mx, band_y - 8, mx, band_y + band_h + 10, stroke=color, sw=2.4)
        d.circle(mx, band_y - 8, 5, fill=color)
        d.text(mx, cy + 14, name, F(13, K), 700, "text", "middle", box=box)
        d.text(mx, cy + 38, detail, F(12, K), 700, color, "middle", box=box)
    for hour in range(0, 25, 3):
        tx = at(hour)
        d.line(tx, band_y + band_h + 4, tx, band_y + band_h + 10, stroke="faint", sw=1.2)
        anchor = "start" if hour == 0 else "end" if hour == 24 else "middle"
        d.text(tx, band_y + band_h + 30, f"{hour:02d}:00", F(10.5, K), 400, "muted", anchor, box=box)
    note_y = band_y + band_h + 68
    third = (w - 96) / 3
    for index, text in enumerate(T["day_notes"]):
        nx_ = ax0 + index * third
        d.circle(nx_ + 5, note_y - 6, 3.6, fill="muted")
        d.text(nx_ + 20, note_y, text, F(12.5, K), 400, "text2", box=box)


def s2(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 2, *T["s2"], k=K)
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 40
    cw_, ch = (iw - 3 * gap) / 4, 190
    top = cy + 8
    for index, (icon, name, text, foot, is_code) in enumerate(T["steps"]):
        cx = ix + index * (cw_ + gap)
        cbox = (cx, top, cw_, ch)
        d.rect(cx, top, cw_, ch, rx=12, fill="panel", stroke="line2", sw=1.3)
        d.icon(icon, cx + 14, top + 14, 32)
        d.text(cx + 56, top + 37, name, F(14, K), 700, "text", box=cbox)
        para(d, cx + 16, top + 76, cw_ - 32, text, F(12, K), 22, 400, "text2", box=cbox)
        if is_code:
            code(d, cx + 16, top + ch - 20, foot, F(11.5, K), "purple", box=cbox)
        else:
            d.text(cx + 16, top + ch - 20, foot, F(12, K), 700, "orange", box=cbox)
        if index:
            d.arrow([(cx - gap + 6, top + ch / 2), (cx - 6, top + ch / 2)], sw=2.2)

    # the time of one request, from 0 s to the first content on one scale
    bar_y, bar_h = top + ch + 56, 36
    bar_w = iw - 62
    scale = bar_w / T["bar"][-1][0]
    d.text(ix, bar_y - 14, T["bar_title"], F(12.5, K), 700, "text", box=box)
    start = 0.0
    for end, color in T["bar"]:
        d.rect(ix + start * scale + (1 if start else 0), bar_y, (end - start) * scale - (1 if start else 0), bar_h, rx=5,
               fill=color + "F")
        start = end
    first_w = T["bar"][0][0] * scale
    d.text(ix + first_w / 2, bar_y + bar_h / 2 + 6, T["bar_inside"], F(12.5, K), 700, "onwarm", "middle", box=box)
    header_x, content_x = ix + T["bar"][1][0] * scale, ix + T["bar"][2][0] * scale
    d.line(header_x, bar_y - 8, header_x, bar_y + bar_h, stroke="purple", sw=1.6)
    d.text(header_x + 6, bar_y - 14, T["bar_marks"][0], F(12, K), 700, "purple", "end", box=box)
    d.line(content_x, bar_y, content_x, bar_y + bar_h + 8, stroke="blue", sw=1.6)
    d.text(content_x + 6, bar_y + bar_h + 26, T["bar_marks"][1], F(12, K), 700, "blue", "end", box=box)

    sgap = 16
    sw_ = (iw - 2 * sgap) / 3
    sy = bar_y + bar_h + 56
    sh = y + h - 20 - sy
    for index, (value, label, color) in enumerate(T["stats"]):
        stat(d, ix + index * (sw_ + sgap), sy, sw_, sh, value, label, color, k=K, box=box, vsize=19, lsize=12)


def s3(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 3, *T["s3"], k=K)
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    top = cy + 8
    ph, pgap = 86, 12
    for index, (name, text, ok) in enumerate(T["probes"]):
        py = top + index * (ph + pgap)
        color = "green" if ok else "pink"
        d.rect(ix, py, iw, ph, rx=10, fill=color + "F", fo=0.08, stroke=color, sw=1.5)
        (check if ok else cross)(d, ix + 18, py + 34, 18, color, sw=2.8)
        code(d, ix + 54, py + 36, name, F(13, K), "text", box=box)
        d.text(ix + 54, py + 64, text, F(12, K), 400, "text2", box=box)
    arrow_y = top + 2 * ph + pgap
    sv_y = arrow_y + 34
    insight_h = 58 * K
    sv_h = y + h - 20 - insight_h - 16 - sv_y
    sgap = 14
    sv_w = (iw - sgap) / 2
    for index, (name, lines, color) in enumerate(T["services"]):
        sx = ix + index * (sv_w + sgap)
        sbox = (sx, sv_y, sv_w, sv_h)
        d.arrow([(sx + sv_w / 2, arrow_y + 2), (sx + sv_w / 2, sv_y - 2)], sw=2)
        d.rect(sx, sv_y, sv_w, sv_h, rx=10, fill="panel", stroke=color, sw=1.5)
        d.text(sx + 16, sv_y + 32, name, F(13, K), 700, "purple" if color == "purple" else "text", box=sbox)
        for i, line in enumerate(lines):
            d.circle(sx + 21, sv_y + 60 + i * 26 - 5, 3, fill="muted")
            d.text(sx + 34, sv_y + 60 + i * 26, line, F(11.5, K), 400, "text2", box=sbox)
    callout(d, ix, y + h - 20 - insight_h, iw, *T["insight"], k=K, color="green", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "2")
    s1(d, 48, 140, 1824, 318)
    s2(d, 48, 478, 1150, 566)
    s3(d, 1218, 478, 654, 566)
    footer_note(d, 1872, 1064, T["note"], size=12)
    return d.svg()
