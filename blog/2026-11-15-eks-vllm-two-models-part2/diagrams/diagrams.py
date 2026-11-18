# -*- coding: utf-8 -*-
# 2부의 차트 두 장(그림 4, 그림 5). diagram_lib.py(블로그 프로필)로 만든다.
#   (cd diagrams && BLOG_IMAGES=../images python3 diagrams.py)
# 값의 출처
#   그림 4: results/2026-11-14-vllm-first-start/gemma-0.90.log, results/2026-11-14-coldstart/qwen-warm-optimized.log 의
#           "Free memory on device" 줄과 "GPU KV cache size" 줄 (docs/03-vllm.md, docs/08-results.md와 같은 값)
#   그림 5: results/2026-11-14-slo/{gemma,qwen}/SUMMARY.md 의 S1 표, engine-state.json 의 running_max
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_lib import *

OUT = os.environ.get("BLOG_IMAGES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images"))
os.makedirs(OUT, exist_ok=True)
SLUG = "2026-11-15-eks-vllm-two-models-part2"
AXIS = "rgba(35,47,62,0.25)"
GRID = "rgba(35,47,62,0.08)"


def r4(v):
    """4px 그리드로 반올림(텍스트 좌표용)."""
    return int(round(v / 4.0)) * 4


# --------------------------------------------------------------------------
# 그림 4. GPU 메모리 배분 (누적 가로 막대)
# --------------------------------------------------------------------------
def fig04():
    TOTAL, TARGET = 44.39, 39.95
    rows = [  # 이름, 가중치와 비 torch, 활성값 최대, KV 캐시, 색, KV 주석
        ("Gemma 4 31B", 31.13, 3.45, 5.37, SERIES_TEAL,
         "KV 캐시 5.37GiB = 34,052 토큰 (16,384 토큰 요청 2.08개 분량)"),
        ("Qwen3.8-27B", 34.74, 2.76, 2.45, SERIES_PURPLE,
         "KV 캐시 2.45GiB = 42,780 토큰 (32,768 토큰 요청 1.31개 분량)"),
    ]
    for _, w, a, k, _, _ in rows:  # 세 항목의 합이 0.90 목표와 맞는지 검산
        assert abs((w + a + k) - TARGET) < 0.011, (w, a, k)
    c = Canvas("p2-fig04", "L40S의 GPU 메모리 배분과 KV 캐시",
               "L40S의 GPU 메모리 44.39GiB 가운데 gpu-memory-utilization 0.90에 해당하는 39.95GiB 안에서, "
               "Gemma 4 31B는 가중치와 비 torch 메모리 31.13GiB와 활성값 최대 3.45GiB를 빼고 KV 캐시 5.37GiB가 남고, "
               "Qwen3.8-27B는 34.74GiB와 2.76GiB를 빼고 KV 캐시 2.45GiB가 남는다")
    c.text("top", 40, 44, "GPU 메모리 배분: KV 캐시는 가중치와 활성값을 빼고 남는 부분 (L40S, 기동 로그 기준)", size=20, weight=600)
    X0, PX = 160, 24.0          # 1GiB = 24px, 0~45GiB
    X = lambda g: X0 + g * PX
    AX_Y = 528
    L = c.layers
    # 눈금
    for k in range(0, 10):
        x = X0 + k * 120
        L["zones"].append(f'<line x1="{x}" y1="112" x2="{x}" y2="{AX_Y}" stroke="{GRID}" stroke-width="0.8"/>')
        L["zones"].append(f'<line x1="{x}" y1="{AX_Y}" x2="{x}" y2="{AX_Y+8}" stroke="{AXIS}" stroke-width="1"/>')
        c.text("zones", x, AX_Y + 28, f"{k*5}", size=16, fill=MUTED, anchor="middle", mono=True)
    L["zones"].append(f'<line x1="{X0}" y1="{AX_Y}" x2="1240" y2="{AX_Y}" stroke="{AXIS}" stroke-width="1"/>')
    c.text("zones", 1240, AX_Y + 56, "GPU 메모리 (GiB)", size=16, fill=MUTED, anchor="end", mono=True)
    # 0.90 목표선과 전체
    xt, xe = X(TARGET), X(TOTAL)
    L["top"].append(f'<line x1="{xt:.1f}" y1="124" x2="{xt:.1f}" y2="{AX_Y}" stroke="{INK}" stroke-width="1.2" stroke-dasharray="6,4"/>')
    c.text("top", r4(xt) - 12, 116, "gpu-memory-utilization 0.90 = 39.95GiB", size=16, fill=INK, anchor="end", mono=True)
    c.text("top", 1240, 116, "전체 44.39GiB", size=16, fill=MUTED, anchor="end", mono=True)

    def seg(x1, x2, y, h, fill, fo, stroke, sw=1.2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        L["nodes"].append(f'<rect x="{x1:.1f}" y="{y}" width="{x2-x1:.1f}" height="{h}" fill="{PAPER}"/>')
        L["nodes"].append(f'<rect x="{x1:.1f}" y="{y}" width="{x2-x1:.1f}" height="{h}" fill="{fill}" fill-opacity="{fo}" '
                          f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    H = 88
    for i, (name, w, a, k, col, note) in enumerate(rows):
        y = 176 + i * 184
        c.text("top", X0, y - 16, name, size=20, weight=600)
        x1, x2, x3 = X(w), X(w + a), X(w + a + k)
        seg(X0, x1, y, H, INK, 0.20, INK)
        seg(x1, x2, y, H, INK, 0.07, INK)
        seg(x2, x3, y, H, col, 0.30, col, sw=2)
        seg(x3, xe, y, H, PAPER, 1, MUTED, sw=1, dash="4,3")
        ty = y + H // 2 + 4
        c.text("top", r4((X0 + x1) / 2), ty, f"가중치와 비 torch 메모리 {w:.2f}", size=16, fill=INK, anchor="middle", mono=True)
        c.text("top", r4((x1 + x2) / 2), ty, f"{a:.2f}", size=16, fill=INK, anchor="middle", mono=True)
        c.text("top", r4((x2 + x3) / 2), ty, f"{k:.2f}", size=16, weight=600, fill=INK, anchor="middle", mono=True)
        c.text("top", r4((x3 + xe) / 2), ty, f"{TOTAL-TARGET:.2f}", size=16, fill=SOFT, anchor="middle", mono=True)
        c.text("top", X0, y + H + 28, note, size=16, fill=col, mono=True)

    # 범례(막대 조각의 뜻)
    y = 648
    L["top"].append(f'<line x1="40" y1="{y-16}" x2="1240" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
    c.text("top", 40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    items = [((INK, 0.20, INK, None), "가중치와 비 torch 메모리"), ((INK, 0.07, INK, None), "활성값 최대"),
             ((SERIES_TEAL, 0.30, SERIES_TEAL, None), "KV 캐시 (Gemma)"),
             ((SERIES_PURPLE, 0.30, SERIES_PURPLE, None), "KV 캐시 (Qwen)"),
             ((PAPER, 1, MUTED, "4,3"), "0.90 밖의 메모리")]
    x = 120
    for (f, fo, st, dash), label in items:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        L["top"].append(f'<rect x="{x}" y="{y-10}" width="40" height="24" rx="4" fill="{f}" fill-opacity="{fo}" stroke="{st}"{d}/>')
        c.text("top", x + 52, y + 8, label, size=16, fill=MUTED)
        x += 52 + ((text_w(label) + 36 + 3) // 4) * 4
    assert x <= 1240, f"legend overflow: {x}"
    c.check()
    c.write(os.path.join(OUT, f"{SLUG}-fig04-gpu-memory-split.html"),
            os.path.join(OUT, f"{SLUG}-fig04-gpu-memory-split.svg"))
    print("OK fig04")


# --------------------------------------------------------------------------
# 그림 5. S1에서 동시성에 따른 출력 처리량과 ITL p99 (선 그래프 두 개)
# --------------------------------------------------------------------------
def fig05():
    CONC = [1, 2, 4, 8, 16, 32, 64]
    G_OUT = [18.5, 36.6, 71.5, 138.2, 248.3, 424.4, 447.0]
    Q_OUT = [32.5, 58.7, 79.9, 91.2, 87.9, 85.0, 90.4]
    G_ITL = [57.7, 58.1, 59.0, 60.2, 88.2, 394.2, 436.9]
    Q_ITL = [74.3, 109.3, 110.3, 111.6, 111.7, 110.9, 111.8]
    c = Canvas("p2-fig05", "S1에서 동시성에 따른 출력 처리량과 ITL p99",
               "S1 짧은 채팅에서 동시성을 1에서 64까지 올리면 Gemma 4 31B의 출력 처리량은 18.5에서 447.0 tok/s까지 늘고 "
               "Qwen3.8-27B(MTP 켬)는 동시성 8 이후 85.0에서 91.2 tok/s에 머문다. ITL p99는 동시성 1에서 Gemma 57.7ms, "
               "Qwen 74.3ms로 두 모델 모두 기준 50ms를 넘는다")
    c.text("top", 40, 44, "S1 짧은 채팅(입력 256, 출력 128)에서 동시성에 따른 출력 처리량과 ITL p99", size=20, weight=600)
    L = c.layers
    Y0, Y1 = 160, 560
    STEP = 84

    def frame(x0, title):
        x1 = x0 + STEP * 6
        c.text("top", x0, 120, title, size=20, weight=600)
        L["zones"].append(f'<line x1="{x0}" y1="{Y1}" x2="{x1}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')
        L["zones"].append(f'<line x1="{x0}" y1="{Y0}" x2="{x0}" y2="{Y1}" stroke="{AXIS}" stroke-width="1"/>')
        for i, v in enumerate(CONC):
            x = x0 + STEP * i
            L["zones"].append(f'<line x1="{x}" y1="{Y1}" x2="{x}" y2="{Y1+8}" stroke="{AXIS}" stroke-width="1"/>')
            c.text("zones", x, 588, str(v), size=16, fill=MUTED, anchor="middle", mono=True)
        c.text("zones", x1, 616, "동시성 (동시에 보낸 요청 수)", size=16, fill=MUTED, anchor="end", mono=True)
        return x1

    def series(x0, ys, col):
        pts = [(x0 + STEP * i, y) for i, y in enumerate(ys)]
        d = " ".join(f"{x},{y:.1f}" for x, y in pts)
        L["arrows"].append(f'<polyline points="{d}" fill="none" stroke="{col}" stroke-width="2.4" stroke-linejoin="round"/>')
        for x, y in pts:
            L["top"].append(f'<circle cx="{x}" cy="{y:.1f}" r="4" fill="{PAPER}" stroke="{col}" stroke-width="2"/>')
        return pts

    # ---- 왼쪽: 출력 처리량 (선형 0~500)
    XL = 96
    xl1 = frame(XL, "출력 처리량 (tok/s)")
    YL = lambda v: Y1 - v * 0.8
    for k in range(0, 6):
        y = Y1 - k * 80
        if k:
            L["zones"].append(f'<line x1="{XL}" y1="{y}" x2="{xl1}" y2="{y}" stroke="{GRID}" stroke-width="0.8"/>')
        c.text("zones", XL - 12, y + 4, f"{k*100}", size=16, fill=MUTED, anchor="end", mono=True)
    g = series(XL, [YL(v) for v in G_OUT], SERIES_TEAL)
    q = series(XL, [YL(v) for v in Q_OUT], SERIES_PURPLE)
    c.text("top", xl1, r4(g[-1][1]) - 20, "최대 447.0 tok/s (실행 중 최대 45건)", size=16, fill=SERIES_TEAL, anchor="end", mono=True)
    c.text("top", xl1, 528, "85.0~91.2 tok/s (실행 중 최대 3건)", size=16, fill=SERIES_PURPLE, anchor="end", mono=True)

    # ---- 오른쪽: ITL p99 (로그 20~500)
    XR = 736
    xr1 = frame(XR, "ITL p99 (ms, 로그 눈금)")
    LO, HI = 20.0, 500.0
    YR = lambda v: Y1 - (Y1 - Y0) * math.log10(v / LO) / math.log10(HI / LO)
    for v in (20, 50, 100, 200, 500):
        y = YR(v)
        if v != 20:
            L["zones"].append(f'<line x1="{XR}" y1="{y:.1f}" x2="{xr1}" y2="{y:.1f}" stroke="{GRID}" stroke-width="0.8"/>')
        c.text("zones", XR - 12, r4(y + 4), str(v), size=16, fill=MUTED, anchor="end", mono=True)
    ys = YR(50)
    L["arrows"].append(f'<line x1="{XR}" y1="{ys:.1f}" x2="{xr1}" y2="{ys:.1f}" stroke="{INK}" stroke-width="1.2" stroke-dasharray="6,4"/>')
    c.text("top", xr1, r4(ys) + 24, "기준: ITL p99 50ms", size=16, fill=INK, anchor="end", mono=True)
    g2 = series(XR, [YR(v) for v in G_ITL], SERIES_TEAL)
    q2 = series(XR, [YR(v) for v in Q_ITL], SERIES_PURPLE)
    c.text("top", XR + 20, 188, "동시성 1의 ITL p99", size=16, fill=INK, mono=True)
    c.text("top", XR + 20, 212, "Gemma 57.7ms", size=16, fill=SERIES_TEAL, mono=True)
    c.text("top", XR + 20, 236, "Qwen 74.3ms", size=16, fill=SERIES_PURPLE, mono=True)
    c.text("top", xr1, r4(q2[-1][1]) - 16, "111.8ms", size=16, fill=SERIES_PURPLE, anchor="end", mono=True)
    c.text("top", xr1 - 96, r4(g2[-1][1]) - 4, "436.9ms", size=16, fill=SERIES_TEAL, anchor="end", mono=True)

    c.legend([("teal", "Gemma 4 31B"), ("purple", "Qwen3.8-27B (MTP 켬)"), ("dashed", "SLO의 ITL 기준 (p99 50ms)")], y=664)
    c.check()
    c.write(os.path.join(OUT, f"{SLUG}-fig05-s1-throughput-itl.html"),
            os.path.join(OUT, f"{SLUG}-fig05-s1-throughput-itl.svg"))
    print("OK fig05")


if __name__ == "__main__":
    fig04(); fig05()
