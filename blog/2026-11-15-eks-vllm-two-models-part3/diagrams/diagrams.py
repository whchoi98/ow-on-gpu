# -*- coding: utf-8 -*-
# 3부의 차트 두 장(그림 2, 그림 4). 그림 2의 값은 docs/08-results.md의 표에서 옮겼다.
# 그림 4의 값은 BFF를 EKS 파드로 옮긴 뒤 다시 잰 results/2026-11-15-ttft-segments-eks/summary.json의 중앙값이다.
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_lib import *

OUT = os.environ.get("BLOG_IMAGES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images"))
os.makedirs(OUT, exist_ok=True)
SLUG = "2026-11-15-eks-vllm-two-models-part3"
GRID = "rgba(35,47,62,0.08)"
AXIS = "rgba(35,47,62,0.25)"


def legend_fill(c, x, y, color, op, label):
    """범례 칸 하나(채움 사각형과 라벨). 다음 칸의 x를 돌려준다."""
    c.layers["top"].append(f'<rect x="{x}" y="{y-10}" width="40" height="24" rx="4" fill="{color}" '
                           f'fill-opacity="{op}" stroke="{color}"/>')
    c.text("top", x + 52, y + 8, label, size=16, fill=MUTED)
    return x + 52 + ((text_w(label) + 40 + 3) // 4) * 4


# --------------------------------------------------------------------------
# 그림 2. 배치 부하 중 상담 요청의 TTFT (우선순위 구성별, 로그 눈금)
# --------------------------------------------------------------------------
def fig02():
    c = Canvas(f"{SLUG}-fig02", "배치 부하 중 상담 요청의 TTFT (우선순위 구성별)",
               "Gemma 4 31B에 배치 요청 32개를 계속 보내는 동안 상담 요청의 TTFT를 우선순위 구성 네 가지로 비교한 "
               "로그 눈금 막대 그래프. 우선순위가 없으면 중앙값 30.9초, 게이트웨이만 켜면 11.2초, 엔진 우선순위를 켜면 "
               "0.19초이다.")
    c.text("top", 40, 44, "배치 부하 중 상담 요청의 TTFT (Gemma 4 31B, 배치 32개 동시, 90초, 로그 눈금)", size=20, weight=600)
    X0, X1, Y0, Y1 = 136, 1240, 96, 552
    DEC = (Y1 - Y0) / 3.0          # 100ms에서 100초까지 세 자릿수
    def Y(ms): return Y1 - (math.log10(ms) - 2) * DEC
    L = c.layers
    for k, lab in enumerate(["100ms", "1초", "10초", "100초"]):
        y = Y1 - int(k * DEC)
        L["zones"].append(f'<line x1="{X0}" y1="{y}" x2="{X1}" y2="{y}" stroke="{GRID}" stroke-width="0.8"/>')
        c.text("zones", 124, y + 4, lab, size=16, fill=MUTED, anchor="end", mono=True)
    c.text("zones", 124, 72, "TTFT", size=16, fill=MUTED, anchor="end", mono=True)
    L["zones"].append(f'<line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')
    L["zones"].append(f'<line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')

    cases = [
        ("우선순위 없음", "배치 429 거절 0건", [(30895, "30.9초"), (39154, "39.2초"), (39839, "39.8초")]),
        ("게이트웨이만", "배치 429 거절 1,907건", [(11183, "11.2초"), (23081, "23.1초"), (27563, "27.6초")]),
        ("엔진만", "배치 429 거절 0건", [(190, "190ms"), (1244, "1.24초"), (1409, "1.41초")]),
        ("둘 다", "배치 429 거절 1,988건", [(193, "193ms"), (1030, "1.03초"), (1433, "1.43초")]),
    ]
    OPS = [0.60, 0.32, 0.12]       # p50, p90, p99
    BW, GAP, GW = 56, 8, 276
    for i, (name, sub, vals) in enumerate(cases):
        gx = X0 + GW * i + 44
        for j, (ms, lab) in enumerate(vals):
            x = gx + j * (BW + GAP)
            yt = Y(ms)
            L["nodes"].append(f'<rect x="{x}" y="{yt:.1f}" width="{BW}" height="{Y1 - yt:.1f}" fill="{PAPER}"/>')
            L["nodes"].append(f'<rect x="{x}" y="{yt:.1f}" width="{BW}" height="{Y1 - yt:.1f}" fill="{SERIES_TEAL}" '
                              f'fill-opacity="{OPS[j]}" stroke="{SERIES_TEAL}" stroke-width="1.2"/>')
            c.text("top", x + BW // 2, ((int(yt) - 10) // 4) * 4, lab, size=16, fill=INK, anchor="middle", mono=True)
        cx = gx + (3 * BW + 2 * GAP) // 2
        c.text("top", cx, 588, name, size=20, weight=600, fill=INK, anchor="middle")
        c.text("top", cx, 616, sub, size=16, fill=SOFT, anchor="middle", mono=True)

    y = 664
    L["top"].append(f'<line x1="40" y1="{y-16}" x2="{c.w-40}" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
    c.text("top", 40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    x = 120
    for op, lab in zip(OPS, ["상담 TTFT p50", "p90", "p99"]):
        x = legend_fill(c, x, y, SERIES_TEAL, op, lab)
    c.text("top", x + 8, y + 8, "게이트웨이 = InferenceObjective 헤더, 엔진 = vLLM priority", size=16, fill=MUTED)
    c.check()
    c.write(os.path.join(OUT, f"{SLUG}-fig02-priority-ttft.html"), os.path.join(OUT, f"{SLUG}-fig02-priority-ttft.svg"))
    print("OK fig02")


# --------------------------------------------------------------------------
# 그림 4. 구간별 TTFT (두 모델의 구간 막대)
# --------------------------------------------------------------------------
def fig04():
    c = Canvas(f"{SLUG}-fig04", "구간별 TTFT 중앙값",
               "사용자가 본 첫 내용까지의 시간을 여섯 구간으로 나눈 가로 막대 그래프. Gemma 4 31B는 중앙값 81.9ms 중 "
               "vLLM이 63.2ms, Qwen3.8-27B는 177.5ms 중 vLLM이 147.6ms이고, 나머지 경로 구간은 각각 18.2ms와 29.7ms이다.")
    c.text("top", 40, 44, "구간별 TTFT 중앙값 (ms, 요청을 하나씩, 모델마다 20건, 서울 리전)", size=20, weight=600)
    X0, PX = 320, 4                # 1ms = 4px, 0에서 200ms
    X1 = X0 + 200 * PX
    TOP, ROW = 84, 64
    rows = [
        ("사용자와 엣지 사이", 1.8, 1.9),
        ("CloudFront", 5.0, 5.0),
        ("ALB", 1.6, 1.6),
        ("BFF", 0.1, 12.8),
        ("게이트웨이", 9.7, 8.4),
        ("vLLM", 63.2, 147.6),
        ("사용자가 본 첫 내용", 81.9, 177.5),
    ]
    BOT = TOP + ROW * len(rows)    # 532
    L = c.layers
    for k in range(0, 6):
        x = X0 + k * 40 * PX
        L["zones"].append(f'<line x1="{x}" y1="{TOP}" x2="{x}" y2="{BOT}" stroke="{GRID if k else AXIS}" stroke-width="{0.8 if k else 1}"/>')
        c.text("zones", x, BOT + 28, f"{k*40}", size=16, fill=MUTED, anchor="middle", mono=True)
    c.text("zones", X1 + 16, BOT + 28, "ms", size=16, fill=MUTED, mono=True)
    L["zones"].append(f'<line x1="{X0}" y1="{BOT}" x2="{X1}" y2="{BOT}" stroke="{AXIS}" stroke-width="1"/>')
    BH = 20
    for i, (name, g, q) in enumerate(rows):
        y = TOP + ROW * i
        last = i == len(rows) - 1
        if last:
            L["zones"].append(f'<line x1="40" y1="{y}" x2="{X1 + 100}" y2="{y}" stroke="{RULE_SOLID}" stroke-width="1"/>')
        c.text("top", X0 - 16, y + 36, name, size=20, weight=600, fill=INK, anchor="end")
        for j, (v, col) in enumerate([(g, SERIES_TEAL), (q, SERIES_PURPLE)]):
            by = y + 8 + j * (BH + 4)
            w = max(v * PX, 1.2)
            op = 0.45 if last else 0.22
            L["nodes"].append(f'<rect x="{X0}" y="{by}" width="{w:.1f}" height="{BH}" fill="{PAPER}"/>')
            L["nodes"].append(f'<rect x="{X0}" y="{by}" width="{w:.1f}" height="{BH}" fill="{col}" fill-opacity="{op}" '
                              f'stroke="{col}" stroke-width="1.2"/>')
            tx = ((int(X0 + w) + 12) // 4) * 4
            c.text("top", tx, by + 16, f"{v:.1f}", size=16, fill=INK, mono=True)
    # vLLM 비중 주석
    c.text("top", 1000, TOP + ROW * 5 + 24, "첫 내용의 77%", size=16, fill=SOFT, mono=True)
    c.text("top", 1000, TOP + ROW * 5 + 48, "첫 내용의 83%", size=16, fill=SOFT, mono=True)
    c.legend([("fill-teal", "Gemma 4 31B (상담 질문)"), ("fill-purple", "Qwen3.8-27B (코딩 질문)")], y=664)
    c.text("top", 720, 672, "구간별 중앙값이라 합이 맨 아래 행과 정확히 같지는 않음", size=16, fill=MUTED)
    c.check()
    c.write(os.path.join(OUT, f"{SLUG}-fig04-ttft-segments.html"), os.path.join(OUT, f"{SLUG}-fig04-ttft-segments.svg"))
    print("OK fig04")


if __name__ == "__main__":
    fig02(); fig04()
