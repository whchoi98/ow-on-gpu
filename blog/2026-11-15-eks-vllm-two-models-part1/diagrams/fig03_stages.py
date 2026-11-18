# -*- coding: utf-8 -*-
# 그림 3. 콜드 스타트의 네 구간 (my-plugins:aws-diagram-design).
# 시맨틱 패턴: Stage framework with semantic slots, 가장 가까운 유형: Process.
#   단계 4개(노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화) x 슬롯 4개(측정 근거, 기준 구성, 최적화 구성, 측정값).
#   칸 16개(한도 20), 칸마다 두 줄 이하. 기타는 단계가 아니므로 아래 주석으로 뺐다.
# 블로그 프로필(1280x720, 이름 20px/600, 보조 16px)을 따르고, 오렌지는 쓰지 않는다(기준 = ink, 최적화 = teal).
#   python3 fig03_stages.py <images dir>
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from diagram_lib import *

OUT = sys.argv[1]
SLUG = "2026-11-15-eks-vllm-two-models-part1-fig03-cold-start-stages"

c = Canvas("part1-fig03", "콜드 스타트의 네 구간: 측정 근거와 두 구성의 차이",
           "파드 생성에서 Ready까지를 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화의 네 구간으로 나누고, "
           "구간마다 측정 근거, 기준 구성과 최적화 구성의 동작, Gemma 4 31B 콜드 스타트의 측정값을 적은 단계 표")
Z, A, N, T = c.layers["zones"], c.layers["arrows"], c.layers["nodes"], c.layers["top"]

COL_X = [200, 444, 688, 932]
COL_W, LABEL_X = 220, 40
HEAD_Y, HEAD_H = 72, 56
ROW_Y = [152, 248, 344, 440]
ROW_H = 80


def box(x, y, w, h, fill, fill_op, stroke, stroke_op=1.0, dashed=False, name=None):
    g4(x, y, w, h)
    for (bx, by, bw, bh, bn) in c.node_boxes:
        assert not overlap((x, y, w, h), (bx, by, bw, bh)), f"overlap: {name} vs {bn}"
    c.node_boxes.append((x, y, w, h, name or f"box@{x},{y}"))
    dash = ' stroke-dasharray="4,3"' if dashed else ""
    N.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{PAPER}"/>')
    N.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="{fill}" fill-opacity="{fill_op}" '
             f'stroke="{stroke}" stroke-opacity="{stroke_op}" stroke-width="1"{dash}/>')


def cell(col, row, lines, style, fills=None, mono=False):
    x, y = COL_X[col], ROW_Y[row]
    if style == "basis":
        box(x, y, COL_W, ROW_H, PAPER, 1, RULE_SOLID, name=f"basis{col}")
    elif style == "baseline":
        box(x, y, COL_W, ROW_H, INK, 0.06, INK, 0.40, name=f"baseline{col}")
    elif style == "optimized":
        box(x, y, COL_W, ROW_H, SERIES_TEAL, 0.10, SERIES_TEAL, name=f"optimized{col}")
    elif style == "same":
        box(x, y, COL_W, ROW_H, INK, 0.02, INK, 0.30, dashed=True, name=f"same{col}")
    elif style == "value":
        box(x, y, COL_W, ROW_H, PAPER, 1, RULE_SOLID, name=f"value{col}")
    # 두 줄은 28px 간격, 한 줄은 가운데
    ys = [y + 36, y + 64] if len(lines) == 2 else [y + 48]
    for i, (s, yy) in enumerate(zip(lines, ys)):
        fill = fills[i] if fills else (MUTED if style == "same" else INK)
        assert text_w(s) <= COL_W - 24, f"cell text too wide: {s} ({text_w(s)})"
        c.text("nodes", x + 16, yy - 4, s, size=16, fill=fill, mono=mono)


def pill(x, w, label):
    box(x, 80, w, 40, MUTED, 0.10, SOFT, name=label)
    c.text("nodes", x + w // 2, 108, label, size=16, weight=600, fill=INK, anchor="middle")


c.text("top", 40, 44, "콜드 스타트의 네 구간: 측정 근거와 두 구성의 차이", size=20, weight=600)

# ---- 단계 머리줄: 파드 생성 -> 1 -> 2 -> 3 -> 4 -> Ready ----
pill(40, 136, "파드 생성")
pill(1176, 64, "Ready")
stages = ["노드 프로비저닝", "이미지 pull", "가중치 로드", "엔진 초기화"]
for i, (x, name) in enumerate(zip(COL_X, stages)):
    box(x, HEAD_Y, COL_W, HEAD_H, PAPER, 1, INK, name=name)
    N.append(f'<circle cx="{x + 28}" cy="{HEAD_Y + 28}" r="12" fill="{INK}"/>'
             f'<text x="{x + 28}" y="{HEAD_Y + 28}" fill="{PAPER}" font-size="16" font-weight="700" '
             f'font-family="{SANS}" text-anchor="middle" dominant-baseline="central">{i + 1}</text>')
    c.text("nodes", x + 52, HEAD_Y + 36, name, size=20, weight=600)
xs = [176] + [v for x in COL_X for v in (x, x + COL_W)] + [1176]
for a, b in zip(xs[0::2], xs[1::2]):
    c.arrow([(a, 100), (b, 100)], color=MUTED)

# ---- 슬롯 이름 ----
labels = [("측정 근거", None), ("기준 구성", None), ("최적화 구성", None), ("Gemma 4 31B", "콜드 스타트 (초)")]
for (l1, l2), y in zip(labels, ROW_Y):
    if l2:
        c.text("top", LABEL_X, y + 36, l1, size=16, weight=600, fill=INK)
        c.text("top", LABEL_X, y + 60, l2, size=16, fill=MUTED)
    else:
        c.text("top", LABEL_X, y + 44, l1, size=16, weight=600, fill=INK)

# ---- 칸 ----
basis = [["NodeClaim 생성부터", "노드 Ready까지"], ["kubelet의 Pulled", "이벤트에 적힌 시간"],
         ["vLLM 로그의", "Model loading took"], ["vLLM 로그의", "init engine ... took"]]
baseline = [["Karpenter NodePool,", "g6e.4xlarge On-Demand"], ["파드 스케줄 뒤에", "kubelet이 받기 시작"],
            ["Mountpoint 마운트를", "기본 로더로 읽기"], ["compile 캐시 없음,", "매번 torch.compile"]]
optimized = [["기준 구성과 같음"], ["노드 부팅 중에", "사전 pull 시작"],
             ["runai_streamer로", "S3에서 스트리밍"], ["S3의 compile 캐시를", "initContainer가 복원"]]
values = [(55.0, 71.0), (111.1, 71.0), (59.6, 19.2), (95.5, 23.7)]
for i in range(4):
    cell(i, 0, basis[i], "basis")
    cell(i, 1, baseline[i], "baseline")
    cell(i, 2, optimized[i], "same" if i == 0 else "optimized")
    cell(i, 3, [f"기준 {values[i][0]:.1f}", f"최적화 {values[i][1]:.1f}"], "value", fills=[INK, SERIES_TEAL])

# ---- 주석 ----
c.text("top", 200, 556, "기타 = 전체 시간 - 네 구간 (스케줄링 대기, 컨테이너 생성, API 서버 기동 등). 기준 72.7초, 최적화 75.1초",
       size=16, fill=MUTED)
c.text("top", 200, 584, "웜 재시작에서는 노드와 이미지가 이미 있으므로 3, 4 구간과 기타만 남음",
       size=16, fill=MUTED)

# ---- 범례 ----
T.append(f'<line x1="40" y1="648" x2="{c.w - 40}" y2="648" stroke="{RULE}" stroke-width="0.8"/>')
c.text("top", 40, 676, "범례", size=16, weight=600, fill=MUTED)
x = 120
for fill, fo, stroke, so, dashed, label in [
        (INK, 0.06, INK, 0.40, False, "기준 구성"),
        (SERIES_TEAL, 0.10, SERIES_TEAL, 1, False, "최적화 구성"),
        (INK, 0.02, INK, 0.30, True, "두 구성이 같은 구간"),
        (PAPER, 1, RULE_SOLID, 1, False, "측정 근거와 측정값 (2026-11-14 서울 리전, 한 번 측정)")]:
    dash = ' stroke-dasharray="4,3"' if dashed else ""
    T.append(f'<rect x="{x}" y="654" width="40" height="24" rx="4" fill="{fill}" fill-opacity="{fo}" '
             f'stroke="{stroke}" stroke-opacity="{so}"{dash}/>')
    c.text("top", x + 52, 672, label, size=16, fill=MUTED)
    end = x + 52 + text_w(label)
    x += 52 + ((text_w(label) + 40 + 3) // 4) * 4
assert end <= c.w - 40, f"legend too wide: {end}"

c.check()
base = os.path.join(OUT, SLUG)
c.write(base + ".html", base + ".svg")
print("OK fig03")
