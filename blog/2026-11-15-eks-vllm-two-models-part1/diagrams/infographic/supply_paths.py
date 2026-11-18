"""1부 그림 4: 가중치와 compile 캐시가 GPU 노드에 올라가는 경로.

한 그림에 두 가지만 담는다. 위는 가중치를 읽는 두 경로, 아래는 compile 캐시를 두는 세 위치다.
본문 안에 넣는 도식이라 글자를 한눈에 보기보다 키웠다(K).
값은 원고의 표 3, 5, 10과 본문에서 옮겼다(2026-11-14 서울 리전, 1회).
"""
from infokit import CODE_FAMILY, Doc, F, cw, footer_note, header, para, rw, section, tag

K = 1.3

T = dict(
    title="가중치와 compile 캐시의 공급 경로",
    sub_en="How Weights and the Compile Cache Reach the GPU",
    sub_ko="기준 구성과 최적화 구성의 차이",
    s1=("가중치 로드 경로", "같은 S3 버킷, 읽는 방법이 다름"),
    lanes=[
        dict(name="기준 구성", color="muted", time="59.6초", time_color="text", gain=None,
             steps=[("service/Amazon-Simple-Storage-Service", "S3 모델 버킷", "models/ 아래 safetensors"),
                    (None, "Mountpoint for Amazon S3", "버킷을 파일 시스템으로 마운트"),
                    (None, "vLLM 기본 로더", "마운트 경로의 파일을 읽음"),
                    ("service/Amazon-EC2", "GPU 메모리", "가중치 30.63GiB")]),
        dict(name="최적화 구성", color="green", time="19.2초", time_color="orange", gain="3.1배",
             steps=[("service/Amazon-Simple-Storage-Service", "S3 모델 버킷", "models/ 아래 safetensors"),
                    (None, "runai_streamer", "텐서를 동시에 읽으면서 GPU 메모리로 스트리밍, 노드 디스크에 내려받지 않음"),
                    ("service/Amazon-EC2", "GPU 메모리", "가중치 30.63GiB")]),
    ],
    time_label="가중치 로드",
    s1_notes=[
        "권한은 EKS Pod Identity의 읽기 역할, 트래픽은 S3 게이트웨이 엔드포인트 경유",
        "HF_HUB_OFFLINE=1로 서빙 파드의 Hugging Face 다운로드 차단",
    ],
    s2=("compile 캐시의 수명 세 단계", "캐시를 두는 위치가 다음 시작의 compile 시간을 결정"),
    tiers=[
        dict(color="pink", icon="category/Containers", name="컨테이너 안", where="기준 구성의 위치", code=False,
             life="파드와 함께 소실", result="시작할 때마다 torch.compile 61.0초", init="엔진 초기화 95.5초"),
        dict(color="yellow", icon="resource/Disk", name="노드 hostPath", where="/var/cache/vllm", code=True,
             life="같은 노드에서는 유지", result="웜 재시작에서 compile 0.9초", init="엔진 초기화 23.7초"),
        dict(color="green", icon="service/Amazon-Simple-Storage-Service", name="S3 prefix",
             where="vllm-cache/<구성>/", code=True,
             life="노드가 바뀌어도 유지", result="새 노드에서 3.3초에 복원, compile 0.9초",
             init="엔진 초기화 23.7초"),
    ],
    links=[
        # (위 화살표, 아래 화살표). None이면 그리지 않는다
        (("VLLM_CACHE_ROOT", "캐시 위치 변경"), None),
        (("캐시 게시 Job", "구성마다 1회"), ("cache-restore", "새 노드마다 복원")),
    ],
    prefix_label="prefix 이름의 네 요소",
    prefix=[("v0.33.0", "vLLM 버전"), ("gemma4-31b", "모델"), ("fp8", "정밀도"), ("l40s", "GPU")],
    prefix_note="하나라도 바뀌면 캐시 불일치, 새 prefix로 다시 게시",
    restore_label="새 노드에서 복원한 캐시",
    restore=[("Gemma 4 31B", "522개, 90.8MB", "3.3초"), ("Qwen3.8-27B", "2,056개, 216.7MB", "10초")],
    note="2026-11-14 서울 리전, g6e.4xlarge(L40S 1장), vLLM v0.33.0. 시간은 Gemma 4 31B 콜드 스타트 1회 측정값",
)


def plain_tag(d, x, y, text, size, h, pad, box):
    w = rw(text, size, 700) + 2 * pad
    d.rect(x, y, w, h, rx=h / 2, fill="muted", fo=0.14, stroke="muted", sw=1.1)
    d.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 700, "muted", "middle", box=box)


def step_box(d, x, y, w, h, icon, name, desc, box, stroke="line2"):
    d.rect(x, y, w, h, rx=12, fill="panel", stroke=stroke, sw=1.3)
    tx = x + 20
    if icon:
        d.icon(icon, x + 18, y + h / 2 - 22, 44)
        tx = x + 76
    lines = 2 if rw(desc, F(13, K)) > x + w - 18 - tx else 1
    top = y + h / 2 - (F(16, K) + lines * F(18, K)) / 2
    d.text(tx, top + F(15, K), name, F(15, K), 700, "text", box=box)
    para(d, tx, top + F(15, K) + F(20, K), x + w - 18 - tx, desc, F(13, K), F(18, K), 400, "text2", box=box)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"], tsize=F(21, K), ksize=F(15, K))
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    lane_h, gap = 118, 16
    label_w, time_w, arrow = 168, 256, 46
    bx0 = ix + label_w
    track = iw - label_w - time_w
    unit = (track - 3 * arrow) / 4  # 기준 구성의 네 칸을 기준으로 폭을 잡는다
    for i, lane in enumerate(T["lanes"]):
        ly = cy + 8 + i * (lane_h + gap)
        d.rect(ix, ly, iw, lane_h, rx=14, fill=lane["color"] + "F" if lane["color"] != "muted" else "muted",
               fo=0.07, stroke=lane["color"], sw=1.2, so=0.7)
        if lane["color"] == "muted":
            plain_tag(d, ix + 18, ly + lane_h / 2 - 15, lane["name"], F(13, K), 30, 13, box)
        else:
            tag(d, ix + 18, ly + lane_h / 2 - 15, lane["name"], lane["color"], F(13, K), 30, 13, box=box)
        steps = lane["steps"]
        widths = [unit] * 4 if len(steps) == 4 else [unit, 2 * unit + arrow, unit]
        bx = bx0
        for j, ((icon, name, desc), bw) in enumerate(zip(steps, widths)):
            step_box(d, bx, ly + 14, bw, lane_h - 28, icon, name, desc, box,
                     stroke="green" if lane["color"] == "green" and icon is None else "line2")
            if j:
                d.arrow([(bx - arrow + 6, ly + lane_h / 2), (bx - 6, ly + lane_h / 2)], "arrow", 2.0)
            bx += bw + arrow
        tx = ix + iw - time_w + 26
        d.text(tx, ly + 42, T["time_label"], F(12, K), 400, "muted", box=box)
        d.text(tx, ly + 88, lane["time"], 38, 700, lane["time_color"], box=box)
        if lane["gain"]:
            tag(d, tx + rw(lane["time"], 38, 700) + 14, ly + 60, lane["gain"], "green", F(13, K), 30, 12, box=box)
    ny = cy + 8 + 2 * (lane_h + gap) + 22
    nx = ix + 4
    for text in T["s1_notes"]:
        d.circle(nx + 4, ny - 6, 3.2, fill="muted")
        d.text(nx + 18, ny, text, F(13, K), 400, "text2", box=box)
        nx += 18 + rw(text, F(13, K)) + 44


def link(d, x1, x2, y, top, bottom, box, reverse=False):
    """카드 사이의 화살표 하나와 그 위아래 두 줄 설명."""
    pts = [(x2 - 6, y), (x1 + 6, y)] if reverse else [(x1 + 6, y), (x2 - 6, y)]
    d.arrow(pts, "arrow", 2.0)
    mid = (x1 + x2) / 2
    code = top.isascii()
    d.text(mid, y - 12, top, F(12, K), 700, "text", "middle", box=box, family=CODE_FAMILY if code else None)
    d.text(mid, y + 26, bottom, F(12, K), 400, "muted", "middle", box=box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"], tsize=F(21, K), ksize=F(15, K))
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 218
    cw_ = (iw - 2 * gap) / 3
    ty, th = cy + 8, 252
    for i, t in enumerate(T["tiers"]):
        bx = ix + i * (cw_ + gap)
        d.rect(bx, ty, cw_, th, rx=14, fill=t["color"] + "F", fo=0.09, stroke=t["color"], sw=1.5)
        d.icon(t["icon"], bx + 22, ty + 22, 46)
        d.text(bx + 84, ty + 44, t["name"], F(17, K), 700, "text", box=box)
        d.text(bx + 84, ty + 72, t["where"], F(12, K) if t["code"] else F(13, K), 400, "text2", box=box,
               family=CODE_FAMILY if t["code"] else None)
        d.line(bx + 22, ty + 96, bx + cw_ - 22, ty + 96, stroke=t["color"], sw=1.0, so=0.45)
        d.text(bx + 22, ty + 130, t["life"], F(15, K), 700, t["color"], box=box)
        d.text(bx + 22, ty + 164, t["result"], F(13, K), 400, "text", box=box)
        tag(d, bx + 22, ty + 194, t["init"], t["color"], F(13, K), 32, 14, box=box)
        if i:
            up, down = T["links"][i - 1]
            x1, x2 = bx - gap, bx
            if down:
                link(d, x1, x2, ty + 84, *up, box)
                link(d, x1, x2, ty + 166, *down, box, reverse=True)
            else:
                link(d, x1, x2, ty + th / 2, *up, box)
    # 아래 두 상자: prefix 이름의 네 요소, 복원한 캐시
    py, ph = ty + th + 22, y + h - 22 - (ty + th + 22)
    lw = iw * 0.60
    d.rect(ix, py, lw, ph, rx=12, fill="panel", stroke="cardline", sw=1.2)
    d.text(ix + 20, py + 34, T["prefix_label"], F(13, K), 700, "text", box=box)
    px, cy2 = ix + 20, py + 52
    for j, (value, meaning) in enumerate(T["prefix"]):
        if j:
            d.text(px + 2, cy2 + 23, "-", F(13, K), 700, "faint", box=box)
            px += 16
        wv = cw(value, F(12, K)) + 20
        d.rect(px, cy2, wv, 34, rx=8, fill="card", stroke="yellow", sw=1.2)
        d.text(px + 10, cy2 + 23, value, F(12, K), 400, "text", box=box, family=CODE_FAMILY)
        d.text(px + wv + 8, cy2 + 23, meaning, F(12, K), 400, "muted", box=box)
        px += wv + 8 + rw(meaning, F(12, K)) + 8
    d.text(px + 20, cy2 + 23, T["prefix_note"], F(13, K), 700, "pink", box=box)
    rx0, rw_ = ix + lw + 20, iw - lw - 20
    d.rect(rx0, py, rw_, ph, rx=12, fill="panel", stroke="cardline", sw=1.2)
    d.text(rx0 + 20, py + 34, T["restore_label"], F(13, K), 700, "text", box=box)
    for j, (model, size, sec) in enumerate(T["restore"]):
        ry = py + 66 + j * 28
        d.text(rx0 + 20, ry, model, F(12, K), 700, "text2", box=box)
        d.text(rx0 + 190, ry, size, F(12, K), 400, "text2", box=box)
        d.text(rx0 + rw_ - 20, ry, sec, F(13, K), 700, "orange", "end", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    s1(d, 48, 140, 1824, 396)
    s2(d, 48, 556, 1824, 488)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
