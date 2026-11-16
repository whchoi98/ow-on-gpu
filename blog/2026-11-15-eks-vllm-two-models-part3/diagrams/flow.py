# -*- coding: utf-8 -*-
# 그림 3. BFF의 모델 결정 순서 (aws-diagram-design의 Flowchart 유형, 블로그 프로필 1280x720)
# 모양이 종류를 나타낸다: 타원 = 시작, 마름모 = 판단, 사각형 = 처리와 결과. 순서는 app/bff/routing.py와 bff.py를 따른다.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_lib import *

OUT = os.environ.get("BLOG_IMAGES", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images"))
SLUG = "2026-11-15-eks-vllm-two-models-part3"
CX = 240            # 왼쪽 판단 줄의 가운데
DW, DH = 400, 88    # 마름모 크기
RX, RW = 560, 680   # 결과 상자의 x와 폭


def diamond(c, cy, name):
    x, y = CX - DW // 2, cy - DH // 2
    for (bx, by, bw, bh, bn) in c.node_boxes:
        assert not overlap((x, y, DW, DH), (bx, by, bw, bh)), f"node overlap: {name} vs {bn}"
    c.node_boxes.append((x, y, DW, DH, name))
    pts = f"{x},{cy} {CX},{y} {x + DW},{cy} {CX},{y + DH}"
    c.layers["nodes"].append(f'<polygon points="{pts}" fill="{PAPER}" stroke="{INK}" stroke-width="1"/>')
    c.text("nodes", CX, cy + 8, name, size=20, weight=600, anchor="middle")


def oval(c, x, y, w, h, name):
    c.node_boxes.append((x, y, w, h, name))
    c.layers["nodes"].append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{PAPER}"/>')
    c.layers["nodes"].append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="20" fill="{MUTED}" fill-opacity="0.10" '
                             f'stroke="{SOFT}" stroke-width="1"/>')
    c.text("nodes", x + w // 2, y + h // 2 + 8, name, size=20, weight=600, anchor="middle")


def fig03():
    c = Canvas(f"{SLUG}-fig03", "BFF의 모델 결정 순서",
               "세션에 저장된 결정이 없는 요청을 BFF가 어느 모델로 보낼지 정하는 순서를 나타낸 흐름도. 주민등록번호나 "
               "카드번호 형식, 업무 종류, 이미지 첨부를 차례로 확인하고, 어느 것에도 해당하지 않을 때만 Strands Decider 2B에 묻는다.")
    c.text("top", 40, 44, "BFF의 모델 결정 순서 (규칙을 먼저 적용하고, 정해지지 않은 요청만 Decider에 질문)", size=20, weight=600)

    oval(c, 60, 72, 360, 40, "세션에 저장된 결정이 없는 요청")
    rows = [
        (188, "주민등록번호나 카드번호 형식", "Gemma 4 31B로 보내고 민감으로 표시", "결정 근거 rule / Decider를 부르지 않음"),
        (304, "업무 종류(x-task) 지정", "업무별 배정표의 모델",
         "상담, 번역, 요약 = Gemma / 이미지 이해, OCR, 코딩 = Qwen"),
        (420, "이미지 첨부", "Qwen3.8-27B", "결정 근거 attachment"),
    ]
    c.arrow([(CX, 112), (CX, 144)])
    for i, (cy, cond, res, sub) in enumerate(rows):
        diamond(c, cy, cond)
        c.node(RX, cy - 36, RW, 72, res, sub=sub)
        c.arrow([(CX + DW // 2, cy), (RX, cy)], label="있음")
        nxt = rows[i + 1][0] - DH // 2 if i + 1 < len(rows) else 496
        c.arrow([(CX, cy + DH // 2), (CX, nxt)], label="없음", side="right")

    c.node(CX - DW // 2, 496, DW, 96, "Strands Decider 2B에 질문", sub="게이트웨이 /decide, 제한 2초")
    c.node(RX, 496, RW, 96, "Decider의 판단을 결정으로 변환",
           sub="신뢰도 0.6 이상: 고른 모델, thinking 판단 반영",
           sub2="응답 실패, 2초 초과, 0.6 미만: Gemma, thinking 끔, 민감")
    c.arrow([(CX + DW // 2, 544), (RX, 544)], label="응답")

    # 범례: 모양이 종류를 나타낸다
    y = 664
    L = c.layers["top"]
    L.append(f'<line x1="40" y1="{y-16}" x2="{c.w-40}" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
    c.text("top", 40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    L.append(f'<rect x="120" y="{y-10}" width="40" height="24" rx="12" fill="{MUTED}" fill-opacity="0.10" stroke="{SOFT}"/>')
    c.text("top", 172, y + 8, "시작", size=16, fill=MUTED)
    L.append(f'<polygon points="240,{y+2} 264,{y-10} 288,{y+2} 264,{y+14}" fill="{PAPER}" stroke="{INK}"/>')
    c.text("top", 300, y + 8, "판단", size=16, fill=MUTED)
    L.append(f'<rect x="368" y="{y-10}" width="40" height="24" rx="4" fill="{PAPER}" stroke="{INK}"/>')
    c.text("top", 420, y + 8, "처리와 결과", size=16, fill=MUTED)
    c.text("top", 560, y + 8, "결정은 세션에 저장하고, 민감 정보 형식만 메시지마다 다시 확인", size=16, fill=MUTED)
    c.check()
    c.write(os.path.join(OUT, f"{SLUG}-fig03-bff-decision.html"), os.path.join(OUT, f"{SLUG}-fig03-bff-decision.svg"))
    print("OK fig03")


if __name__ == "__main__":
    fig03()
