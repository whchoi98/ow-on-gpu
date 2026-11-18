"""1부 한눈에 보기: 콜드 스타트 구간 분해와 최적화.

값은 원고의 표 9, 10, 11과 본문에서 옮겼다(2026-11-14 서울 리전, 시나리오마다 1회).
빌드는 같은 폴더의 build.sh를 쓴다. infokit.py, buildkit.py는 docs/infographic의 것을 그대로 쓴다.
"""
from infokit import (CODE_FAMILY, Doc, callout, card, cell, cw, dot_list, footer_note, header, rw, section,
                     series_nav, tag)

SERIES = [("1", "콜드 스타트"), ("2", "처리량과 SLO"), ("3", "라우팅과 앱 계층")]

# 구간의 이름과 색. node는 회색 채움, etc는 점선 테두리로 그린다.
SEGMENTS = [("노드 프로비저닝", "node"), ("이미지 pull", "purple"), ("가중치 로드", "yellow"),
            ("엔진 초기화", "blue"), ("기타", "etc")]

T = dict(
    title="콜드 스타트 구간 분해와 최적화",
    sub_en="Cold Start on Amazon EKS: Pod Created to Ready",
    sub_ko="Gemma 4 31B 콜드 394초에서 260초, 웜 재시작 214초에서 86초",
    s1=("시나리오별 시작 시간", "파드 생성에서 Ready까지, 네 구간과 기타의 합"),
    # (이름, 구간별 초, 합계, 줄어든 비율)
    rows=[
        ("Gemma 콜드, 기준", [55.0, 111.1, 59.6, 95.5, 72.7], 394, None),
        ("Gemma 콜드, 최적화", [71.0, 71.0, 19.2, 23.7, 75.1], 260, "-34%"),
        ("Gemma 웜 재시작, 기준", [0, 0, 59.1, 95.6, 59.3], 214, None),
        ("Gemma 웜 재시작, 최적화", [0, 0, 19.6, 23.7, 42.7], 86, "-60%"),
        ("Qwen 콜드, 최적화", [63.0, 77.5, 34.9, 42.5, 72.1], 290, None),
        ("Qwen 웜 재시작, 최적화", [0, 0, 35.4, 41.8, 45.8], 123, None),
    ],
    sleep=("Qwen sleep 복귀", 3.7, "3.7초", "깨우기 API 응답까지, 2회 측정 3.70초와 3.67초, 노드와 파드는 그대로 유지"),
    s1_note="기타 = 전체 - 네 구간 (스케줄링 대기, 컨테이너 생성, API 서버 기동 등). "
            "웜 재시작은 노드와 이미지가 이미 있어 앞의 두 구간이 0",
    s2=("구간별 원인과 조치", "구간마다 기다리는 대상이 다름"),
    causes=[
        ("purple", "이미지 pull 111.1초에서 71.0초",
         "이미지 9.74GB, 기준 구성은 파드 스케줄 뒤에 kubelet이 받기 시작",
         "조치: 노드 부팅 중에 사전 pull 시작, 받는 시간이 아닌 시작 시점을 당김"),
        ("yellow", "가중치 로드 59.6초에서 19.2초, 3.1배",
         "Mountpoint로 마운트한 경로를 vLLM 기본 로더로 읽음, 가중치 30.63GiB",
         "조치: runai_streamer가 S3에서 GPU 메모리로 바로 스트리밍"),
        ("blue", "엔진 초기화 95.5초에서 23.7초",
         "compile 캐시가 컨테이너 안에 있어 파드마다 torch.compile 61.0초 반복",
         "조치: 캐시를 노드와 S3에 보존, 3.3초에 복원한 뒤 compile 0.9초"),
    ],
    s3=("적용한 조치와 결과", "조치마다 자기 구간에만 작용, 하나씩 적용하고 하나씩 측정 가능"),
    cols=["구분", "조치", "줄이는 구간", "결과 (조치 1~4는 Gemma 4 31B)", "설정"],
    table=[
        ("전제", "blue", "Hugging Face에서 S3로 1회 적재", "가중치 원본", "4종 74.90GB, 491.4초", "s5cmd pipe"),
        ("조치 1", "green", "스트리밍 로더로 S3에서 직접 읽기", "가중치 로드", "59.6초에서 19.2초, 3.1배",
         "--load-format=runai_streamer"),
        ("조치 2", "green", "compile 캐시를 노드 hostPath에 보존", "엔진 초기화, 같은 노드", "95.6초에서 23.7초",
         "VLLM_CACHE_ROOT"),
        ("조치 3", "green", "compile 캐시를 S3에 게시, initContainer로 복원", "엔진 초기화, 새 노드",
         "95.5초에서 23.7초, 복원 3.3초", "initContainer cache-restore"),
        ("조치 4", "green", "노드 부팅 중 이미지 사전 pull", "이미지 pull", "111.1초에서 71.0초",
         "EC2NodeClass userData"),
        ("대안", "orange", "sleep과 깨우기로 파드 유지 (Qwen)", "재시작 자체", "복귀 3.7초, 웜 재시작은 123초",
         "--enable-sleep-mode"),
    ],
    s4=("운영 점검 항목", "캐시 수명과 놓치기 쉬운 설정"),
    tiers_label="compile 캐시의 수명 세 단계",
    tiers=[
        ("pink", "컨테이너 안", "기준 구성", "파드와 함께 소실"),
        ("yellow", "노드 hostPath", "/var/cache/vllm", "파드 재시작에도 유지"),
        ("green", "S3 prefix", "vllm-cache/<구성>/", "새 노드에서 복원"),
    ],
    checks=[
        "캐시 prefix에 vLLM 버전, 모델, 정밀도, GPU 포함, 구성이 바뀌면 새 prefix로 게시",
        "Qwen은 gpu-memory-utilization 0.85에서 시작 실패, 0.90에서 KV 캐시 2.46GiB",
        "/health는 sleep 중에도 200, Qwen의 readinessProbe는 /is_sleeping 확인",
        "progressDeadlineSeconds 기본 600초는 콜드 스타트보다 짧을 수 있어 1800으로 설정",
        "최적화 뒤 남은 구간: 노드 프로비저닝과 기타가 260초 가운데 146.1초",
    ],
    first=("먼저 구간별로 측정", "NodeClaim과 파드의 시각, kubelet의 Pulled 이벤트, vLLM 로그 두 줄로 네 구간 산출"),
    note="2026-11-14 서울 리전, g6e.4xlarge(L40S 1장), vLLM v0.33.0, 시나리오마다 1회 측정. "
         "Qwen3.8-27B의 기준 구성은 측정하지 않음",
)


def seg_rect(d, x, y, w, h, kind, label=None, box=None):
    """구간 하나의 막대. 폭이 좁으면 값을 적지 않는다."""
    if kind == "node":
        d.rect(x, y, w, h, rx=4, fill="muted", fo=0.30)
        color = "text"
    elif kind == "etc":
        d.rect(x, y, w, h, rx=4, fill="card", stroke="chipline", sw=1.1, dash="5 4")
        color = "muted"
    else:
        d.rect(x, y, w, h, rx=4, fill=kind + "F")
        color = "onwarm" if kind == "yellow" else "badgetext"
    if label and w >= rw(label, 13, 700) + 4:
        d.text(x + w / 2, y + h / 2 + 4.6, label, 13, 700, color, "middle", box=box)


def code_chip(d, x, mid, text, box, size=12):
    w = cw(text, size) + 18
    d.rect(x, mid - 12, w, 24, rx=6, fill="panel", stroke="line2", sw=1.0)
    d.text(x + 9, mid + 4.2, text, size, 400, "text2", family=CODE_FAMILY, box=box)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    ix = x + 24
    # 범례
    lx = ix
    for name, kind in SEGMENTS:
        seg_rect(d, lx, cy + 2, 16, 14, kind)
        d.text(lx + 23, cy + 14, name, 13, 400, "text2", box=box)
        lx += 23 + rw(name, 13) + 22
    x0, scale = ix + 204, 1.9
    top, pitch, bh = cy + 32, 41, 26
    n = len(T["rows"]) + 1
    # 눈금선은 막대보다 먼저 그린다
    for sec in range(0, 401, 100):
        gx = x0 + sec * scale
        d.line(gx, top - 4, gx, top + (n - 1) * pitch + bh + 4, stroke="cardline", sw=1.0)
        d.text(gx, top + (n - 1) * pitch + bh + 20, f"{sec}초", 12, 400, "faint", "middle", box=box)
    for i, (name, parts, total, cut) in enumerate(T["rows"]):
        ry = top + i * pitch
        d.text(ix, ry + bh / 2 + 5, name, 14, 700, "text", box=box)
        bx = x0
        for (_, kind), sec in zip(SEGMENTS, parts):
            if not sec:
                continue
            bw = sec * scale
            seg_rect(d, bx + 1, ry, bw - 2, bh, kind, f"{sec:.1f}", box)
            bx += bw
        d.text(bx + 10, ry + bh / 2 + 6, f"{total}초", 17, 700, "orange" if cut else "text", box=box)
        if cut:
            tag(d, bx + 10 + rw(f"{total}초", 17, 700) + 10, ry + 1, cut, "green", 13, 24, 10, box=box)
    name, sec, label, memo = T["sleep"]
    ry = top + (n - 1) * pitch
    d.text(ix, ry + bh / 2 + 5, name, 14, 700, "text", box=box)
    d.rect(x0 + 1, ry, max(sec * scale, 5), bh, rx=2, fill="greenF")
    d.text(x0 + 18, ry + bh / 2 + 6, label, 17, 700, "green", box=box)
    d.text(x0 + 18 + rw(label, 17, 700) + 12, ry + bh / 2 + 5, memo, 13, 400, "muted", box=box)
    d.text(ix, y + h - 16, T["s1_note"], 12, 400, "faint", box=box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 10
    ch = (y + h - 20 - cy - 2 * gap) / 3
    for i, (color, title, cause, action) in enumerate(T["causes"]):
        ty = cy + i * (ch + gap)
        card(d, ix, ty, iw, ch, stroke=color, sw=1.4, fill="panel", rx=10)
        d.text(ix + 16, ty + 34, title, 16, 700, color, box=box)
        d.text(ix + 16, ty + 62, cause, 14, 400, "text2", box=box)
        d.text(ix + 16, ty + 89, action, 14, 700, "green", box=box)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    cols = [ix + 12, ix + 108, ix + 452, ix + 636, ix + 890]
    d.rect(ix, cy, iw, 30, rx=6, fill="panel")
    for cx, name in zip(cols, T["cols"]):
        d.text(cx, cy + 20, name, 13, 400, "muted", box=box)
    top = cy + 30
    rh = (y + h - 14 - top) / len(T["table"])
    for i, (kind, color, what, where, result, setting) in enumerate(T["table"]):
        mid = top + i * rh + rh / 2
        if i:
            d.line(ix, top + i * rh, ix + iw, top + i * rh, stroke="cardline", sw=1.0)
        tag(d, cols[0], mid - 12, kind, color, 13, 24, 11, box=box)
        cell(d, cols[1], mid, cols[2] - cols[1] - 16, what, 15, 20, 700, "text", box)
        cell(d, cols[2], mid, cols[3] - cols[2] - 12, where, 14, 19, 400, "text2", box)
        cell(d, cols[3], mid, cols[4] - cols[3] - 12, result, 15, 20, 700, "orange", box)
        code_chip(d, cols[4], mid, setting, box)


def s4(d, x, y, w, h):
    cy = section(d, x, y, w, h, 4, *T["s4"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    d.text(ix, cy + 12, T["tiers_label"], 13, 400, "muted", box=box)
    gap, by, bh = 30, cy + 24, 86
    bw = (iw - 2 * gap) / 3
    for i, (color, name, where, life) in enumerate(T["tiers"]):
        bx = ix + i * (bw + gap)
        d.rect(bx, by, bw, bh, rx=10, fill=color + "F", fo=0.10, stroke=color, sw=1.3)
        d.text(bx + 14, by + 27, name, 15, 700, "text", box=box)
        d.text(bx + 14, by + 49, where, 12, 400, "text2", box=box,
               family=None if i == 0 else CODE_FAMILY)
        d.text(bx + 14, by + 71, life, 13, 700, color, box=box)
        if i:
            d.arrow([(bx - gap + 5, by + bh / 2), (bx - 5, by + bh / 2)], "arrow", 1.6)
    dot_list(d, ix, by + bh + 32, iw, T["checks"], 14, 20, 10, dot="pink", box=box)
    callout(d, ix, y + h - 20 - 58, iw, *T["first"], color="green", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "1")
    s1(d, 48, 140, 1148, 446)
    s2(d, 1216, 140, 656, 446)
    s3(d, 48, 606, 1148, 438)
    s4(d, 1216, 606, 656, 438)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
