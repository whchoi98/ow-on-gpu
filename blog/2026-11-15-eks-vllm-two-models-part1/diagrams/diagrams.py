# -*- coding: utf-8 -*-
# 1부의 차트 두 장(그림 3, 그림 4)을 만든다. 값은 docs/08-results.md "1. 콜드 스타트 구간 분해"의 표와
# results/2026-11-14-coldstart/*.json의 segments_s에서 옮겼다(2026-11-14, 서울 리전, 시나리오마다 한 번).
#   (cd diagrams && BLOG_IMAGES=../images python3 diagrams.py)
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from diagram_lib import *

OUT = os.environ.get("BLOG_IMAGES", os.path.join(os.path.dirname(__file__), "..", "images"))
os.makedirs(OUT, exist_ok=True)
SLUG = "2026-11-15-eks-vllm-two-models-part1"

X0, X1, Y0, Y1 = 120, 1240, 96, 560
AXIS = "rgba(35,47,62,0.25)"
GRID = "rgba(35,47,62,0.08)"


def axes(c, top, step, unit):
    """세로축 0..top, 눈금 간격 step. 눈금 사이 간격은 116px(4px 격자)."""
    L = c.layers
    n = top // step
    assert (Y1 - Y0) % n == 0 and ((Y1 - Y0) // n) % 4 == 0
    for k in range(n + 1):
        y = Y1 - k * (Y1 - Y0) // n
        L["zones"].append(f'<line x1="{X0}" y1="{y}" x2="{X1}" y2="{y}" stroke="{GRID}" stroke-width="0.8"/>')
        c.text("zones", 108, y + 4, f"{k * step}", size=16, fill=MUTED, anchor="end", mono=True)
    c.text("zones", 108, 72, unit, size=16, fill=MUTED, anchor="end", mono=True)
    L["zones"].append(f'<line x1="{X0}" y1="{Y1}" x2="{X1}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')
    L["zones"].append(f'<line x1="{X0}" y1="{Y0}" x2="{X0}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')
    return lambda v: Y1 - v * (Y1 - Y0) / float(top)


def bar(c, x, w, y_top, y_bot, color, opacity):
    L = c.layers["nodes"]
    L.append(f'<rect x="{x}" y="{y_top:.1f}" width="{w}" height="{y_bot - y_top:.1f}" fill="{PAPER}"/>')
    L.append(f'<rect x="{x}" y="{y_top:.1f}" width="{w}" height="{y_bot - y_top:.1f}" fill="{color}" '
             f'fill-opacity="{opacity}" stroke="{color}" stroke-width="1.2"/>')


def label_y(y):
    return ((int(y) - 12) // 4) * 4


def swatch_legend(c, items, y=664):
    """items: (color, opacity, label). diagram_lib.legend와 같은 자리, 같은 글자 크기."""
    T = c.layers["top"]
    T.append(f'<line x1="40" y1="{y - 16}" x2="{c.w - 40}" y2="{y - 16}" stroke="{RULE}" stroke-width="0.8"/>')
    c.text("top", 40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    x = 120
    for color, opacity, label in items:
        T.append(f'<rect x="{x}" y="{y - 10}" width="40" height="24" rx="4" fill="{color}" '
                 f'fill-opacity="{opacity}" stroke="{color}"/>')
        c.text("top", x + 52, y + 8, label, size=16, fill=MUTED)
        end = x + 52 + text_w(label)
        x += 52 + ((text_w(label) + 40 + 3) // 4) * 4
    assert end <= c.w - 40, f"legend too wide: {end}"


# --------------------------------------------------------------------------
# 그림 5. 시나리오별 전체 시간
# --------------------------------------------------------------------------
def fig05():
    c = Canvas("part1-fig05", "시나리오별 파드 생성에서 Ready까지의 시간",
               "Gemma 4 31B는 콜드 스타트가 기준 구성 394초에서 최적화 구성 260초로, 웜 재시작이 214초에서 86초로 줄었고, "
               "Qwen3.8-27B는 최적화 구성만 재서 콜드 스타트 290초, 웜 재시작 123초였다")
    c.text("top", 40, 44, "시나리오별 파드 생성에서 Ready까지의 시간", size=20, weight=600)
    c.text("top", X1, 44, "g6e.4xlarge, vLLM v0.33.0, 2026-11-14 서울 리전, 시나리오마다 한 번", size=16, fill=SOFT,
           anchor="end")
    Y = axes(c, 400, 100, "초")
    groups = [  # 이름, 기준, 최적화, 아래 줄
        ("Gemma 4 31B 콜드 스타트", 394, 260, "기준 대비 -134초 (-34%)"),
        ("Gemma 4 31B 웜 재시작", 214, 86, "기준 대비 -128초 (-60%)"),
        ("Qwen3.8-27B 콜드 스타트", None, 290, "기준 구성은 재지 않음"),
        ("Qwen3.8-27B 웜 재시작", None, 123, "기준 구성은 재지 않음"),
    ]
    GW, BW, GAP = 280, 96, 16
    for i, (name, base, opt, sub) in enumerate(groups):
        gx = X0 + i * GW
        cx = gx + GW // 2
        if base is None:
            xs = [(cx - BW // 2, opt, SERIES_TEAL, 0.18)]
        else:
            x1 = gx + (GW - 2 * BW - GAP) // 2
            xs = [(x1, base, INK, 0.15), (x1 + BW + GAP, opt, SERIES_TEAL, 0.18)]
        for x, v, color, op in xs:
            bar(c, x, BW, Y(v), Y1, color, op)
            c.text("top", x + BW // 2, label_y(Y(v)), f"{v}", size=16, fill=color, anchor="middle", mono=True)
        c.text("top", cx, 588, name, size=20, weight=600, fill=INK, anchor="middle")
        c.text("top", cx, 616, sub, size=16, fill=MUTED if base else SOFT, anchor="middle")
    swatch_legend(c, [(INK, 0.15, "기준 구성 (Mountpoint, 기본 로더)"),
                      (SERIES_TEAL, 0.18, "최적화 구성 (runai_streamer, compile 캐시 복원, 이미지 사전 pull)")])
    c.check()
    base = os.path.join(OUT, f"{SLUG}-fig05-scenario-totals")
    c.write(base + ".html", base + ".svg")
    print("OK fig05")


# --------------------------------------------------------------------------
# 그림 6. Gemma 4 31B 콜드 스타트의 구간별 시간
# --------------------------------------------------------------------------
def fig06():
    c = Canvas("part1-fig06", "Gemma 4 31B 콜드 스타트의 구간별 시간: 기준 구성과 최적화 구성",
               "노드 프로비저닝 55.0초와 71.0초, 이미지 pull 111.1초와 71.0초, 가중치 로드 59.6초와 19.2초, "
               "엔진 초기화 95.5초와 23.7초, 기타 72.7초와 75.1초. 합계는 기준 구성 394초, 최적화 구성 260초")
    c.text("top", 40, 44, "Gemma 4 31B 콜드 스타트의 구간별 시간", size=20, weight=600)
    c.text("top", X1, 44, "합계: 기준 구성 394초, 최적화 구성 260초 (2026-11-14 서울 리전, 한 번씩 측정)", size=16,
           fill=SOFT, anchor="end")
    Y = axes(c, 120, 30, "초")
    seg = [  # 구간, 기준, 최적화, 그중 compile(기준, 최적화)
        ("노드 프로비저닝", 55.0, 71.0, None),
        ("이미지 pull", 111.1, 71.0, None),
        ("가중치 로드", 59.6, 19.2, None),
        ("엔진 초기화", 95.5, 23.7, (61.0, 0.9)),
        ("기타", 72.7, 75.1, None),
    ]
    assert abs(sum(s[1] for s in seg) - 394) < 0.5 and abs(sum(s[2] for s in seg) - 260) < 0.5
    GW, BW, GAP = 224, 80, 16
    for i, (name, base, opt, comp) in enumerate(seg):
        gx = X0 + i * GW
        cx = gx + GW // 2
        x1 = gx + (GW - 2 * BW - GAP) // 2
        x2 = x1 + BW + GAP
        bar(c, x1, BW, Y(base), Y1, INK, 0.15)
        bar(c, x2, BW, Y(opt), Y1, SERIES_TEAL, 0.18)
        if comp:
            # 엔진 초기화 가운데 torch.compile이 차지한 부분을 막대 아래쪽에 진하게 겹쳐 그린다
            bar(c, x1, BW, Y(comp[0]), Y1, INK, 0.35)
            bar(c, x2, BW, Y(comp[1]), Y1, SERIES_TEAL, 0.60)
            my = int((Y(comp[0]) + Y1) / 2)
            c.text("top", x1 + BW // 2, (my // 4) * 4 - 4, "compile", size=16, fill=INK, anchor="middle", mono=True)
            c.text("top", x1 + BW // 2, (my // 4) * 4 + 20, f"{comp[0]:.1f}", size=16, fill=INK, anchor="middle",
                   mono=True)
        c.text("top", x1 + BW // 2, label_y(Y(base)), f"{base:.1f}", size=16, fill=INK, anchor="middle", mono=True)
        c.text("top", x2 + BW // 2, label_y(Y(opt)), f"{opt:.1f}", size=16, fill=SERIES_TEAL, anchor="middle",
               mono=True)
        diff = round(opt - base, 1)
        c.text("top", cx, 588, name, size=20, weight=600, fill=INK, anchor="middle")
        c.text("top", cx, 616, f"{diff:+.1f}초", size=16, fill=MUTED, anchor="middle", mono=True)
    swatch_legend(c, [(INK, 0.15, "기준 구성"), (SERIES_TEAL, 0.18, "최적화 구성"),
                      (INK, 0.35, "엔진 초기화 가운데 torch.compile (최적화 구성은 0.9초)")])
    c.check()
    base = os.path.join(OUT, f"{SLUG}-fig06-cold-start-segments")
    c.write(base + ".html", base + ".svg")
    print("OK fig06")


if __name__ == "__main__":
    fig05(); fig06()
