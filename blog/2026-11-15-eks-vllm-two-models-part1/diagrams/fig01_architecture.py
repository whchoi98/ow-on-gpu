# -*- coding: utf-8 -*-
# 그림 1. 시리즈 전체 구성 (my-plugins:aws-diagram 워크플로).
# 아이콘은 aws-diagram의 find_icon.py로 찾은 bundle: 참조를 쓰고, embed.py로 내장한다.
# 캔버스와 글자 크기는 블로그 프로필(1280x720, 이름 20px/600, 보조 16px)을 따른다.
#   python3 fig01_architecture.py <aws-diagram skill dir> <images dir>
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from diagram_lib import *

SKILL, OUT = sys.argv[1], sys.argv[2]
BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
os.makedirs(BUILD, exist_ok=True)
SLUG = "2026-11-15-eks-vllm-two-models-part1-fig01-series-architecture"

AWS_CLOUD, VPC_GREEN = "#232F3E", "#7AA116"

c = Canvas("part1-fig01", "시리즈 전체 구성: 요청 경로와 모델, 이미지가 GPU 노드에 올라가는 경로",
           "서울 리전 VPC의 Amazon EKS 클러스터에서 Karpenter가 만든 GPU 노드 세 대가 Gemma 4 31B, Qwen3.8-27B, "
           "Strands Decider 2B를 서빙한다. 요청은 CloudFront와 내부 ALB를 지나 클러스터 안의 BFF 파드와 게이트웨이를 거쳐 들어오고, "
           "가중치와 compile 캐시는 Amazon S3 버킷에서, 컨테이너 이미지는 Docker Hub에서 GPU 노드로 올라간다")
N, Z, T = c.layers["nodes"], c.layers["zones"], c.layers["top"]


def icon(ref, x, y, size=48):
    g4(x, y, size)
    N.append(f'<image href="bundle:{ref}" x="{x}" y="{y}" width="{size}" height="{size}"/>')


def group(x, y, w, h, stroke, label, badge, label_fill=INK, width=2, fill="none", fill_op=1, stroke_op=1):
    g4(x, y, w, h)
    Z.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" fill-opacity="{fill_op}" '
             f'stroke="{stroke}" stroke-opacity="{stroke_op}" stroke-width="{width}"/>')
    Z.append(f'<image href="bundle:{badge}" x="{x + 8}" y="{y + 8}" width="24" height="24"/>')
    c.text("zones", x + 40, y + 28, label, size=20, weight=600, fill=label_fill)


def icon_node(ref, cx, cy, name, name2=None, sub=None):
    """아이콘 아래에 이름을 가운데 정렬로 둔다(aws-diagram의 서비스 노드 관례)."""
    icon(ref, cx - 24, cy - 24)
    c.node_boxes.append((cx - 24, cy - 24, 48, 48, name))
    y = cy + 48
    c.text("nodes", cx, y, name, size=20, weight=600, anchor="middle")
    if name2:
        y += 24
        c.text("nodes", cx, y, name2, size=20, weight=600, anchor="middle")
    if sub:
        y += 24
        c.text("nodes", cx, y, sub, size=16, fill=MUTED, anchor="middle", mono=True)


def badge(n, cx, cy, layer=None):
    (layer if layer is not None else T).append(
        f'<circle cx="{cx}" cy="{cy}" r="12" fill="{INK}"/>'
        f'<text x="{cx}" y="{cy}" fill="{PAPER}" font-size="16" font-weight="700" font-family="{SANS}" '
        f'text-anchor="middle" dominant-baseline="central">{n}</text>')


c.text("top", 40, 44, "시리즈 전체 구성: 요청 경로와 모델, 이미지가 GPU 노드에 올라가는 경로", size=20, weight=600)

# ---- 컨테이너 (바깥에서 안으로) ----
group(232, 64, 840, 552, AWS_CLOUD, "AWS Cloud", "group/AWS-Cloud_32")
group(424, 72, 632, 456, VPC_GREEN, "VPC (서울 리전)", "group/Virtual-private-cloud-VPC_32", label_fill=VPC_GREEN)
group(440, 228, 600, 284, INK, "Amazon EKS 클러스터 (1.37)", "service/Amazon-Elastic-Kubernetes-Service",
      width=1.2, stroke_op=0.45)
group(472, 352, 560, 144, MUTED, "Karpenter가 만든 GPU 노드 (On-Demand)", "service/Amazon-EC2",
      width=1.2, fill=INK, fill_op=0.04)

# ---- 요청 경로 (간략히) ----
# 2026-11-15부터 BFF는 클러스터 안의 파드다. 내부 ALB에서 BFF 파드로 들어오고, BFF가 게이트웨이를 Service로 부른다.
icon_node("resource/Users", 124, 136, "사용자")
icon_node("service/Amazon-CloudFront", 336, 136, "Amazon", "CloudFront")
icon_node("service/Elastic-Load-Balancing", 680, 136, "내부 ALB")
for a, b in [(148, 312), (360, 656)]:
    c.arrow([(a, 136), (b, 136)], color=LINK, width=1.6)
c.arrow([(704, 136), (760, 136), (760, 268)], color=LINK, width=1.6)       # 내부 ALB -> BFF 파드
c.arrow([(784, 300), (824, 300)], color=LINK, width=1.6)                   # BFF -> 게이트웨이 (Service)
c.arrow([(924, 332), (924, 352)], color=LINK, width=1.6)                   # 게이트웨이 -> vLLM

# ---- EKS 안의 워크로드 ----
c.node(448, 268, 176, 64, "모델 적재 Job", sub="system NodePool")
c.node(648, 268, 136, 64, "BFF", sub="파드 2개")
c.node(824, 268, 200, 64, "게이트웨이", sub="agentgateway, EPP")
c.node(480, 392, 168, 96, "Gemma 4 31B", sub="vLLM v0.33.0", sub2="g6e.4xlarge")
c.node(656, 392, 168, 96, "Qwen3.8-27B", sub="vLLM v0.33.0", sub2="g6e.4xlarge")
c.node(832, 392, 192, 96, "Strands", sub=None)   # 이름이 두 줄이라 글자는 아래에서 직접 쓴다
N[-1:] = []                                       # c.node가 쓴 한 줄짜리 이름을 지운다
c.text("nodes", 848, 428, "Strands", size=20, weight=600)
c.text("nodes", 848, 452, "Decider 2B", size=20, weight=600)
c.text("nodes", 848, 476, "g6.xlarge", size=16, fill=MUTED, mono=True)

# ---- 바깥의 원본 저장소 ----
c.node(40, 264, 168, 72, "Hugging Face", sub="체크포인트", kind="external")
c.node(1088, 404, 152, 72, "Docker Hub", sub="vLLM 이미지", kind="external")

# ---- Amazon S3 버킷 (VPC 밖) ----
icon("service/Amazon-Simple-Storage-Service", 632, 560)
c.node_boxes.append((632, 560, 48, 48, "Amazon S3"))
c.text("nodes", 696, 580, "Amazon S3 버킷", size=20, weight=600)
c.text("nodes", 696, 604, "models/, vllm-cache/", size=16, fill=MUTED, mono=True)

# ---- 모델과 이미지가 올라가는 경로 (자세히) ----
c.arrow([(208, 300), (448, 300)], color=INK, width=1.6)                      # 1 Hugging Face -> 적재 Job
c.arrow([(456, 332), (456, 584), (632, 584)], color=INK, width=1.6)          # 1 적재 Job -> S3
c.arrow([(640, 560), (640, 496)], color=INK, width=1.6)                      # 2 S3 -> GPU 노드
c.arrow([(672, 496), (672, 560)], color=INK, width=1.6)                      # 3 GPU 노드 -> S3
c.arrow([(1088, 440), (1032, 440)], color=INK, width=1.6)                    # 4 Docker Hub -> GPU 노드
badge(1, 336, 300); badge(1, 544, 584); badge(2, 612, 544); badge(3, 700, 544); badge(4, 1164, 384)

# ---- 범례 (두 줄) ----
T.append(f'<line x1="40" y1="632" x2="{c.w - 40}" y2="632" stroke="{RULE}" stroke-width="0.8"/>')
c.text("top", 40, 660, "범례", size=16, weight=600, fill=MUTED)


def legend_row(y, items):
    x = 120
    for kind, label in items:
        if kind == "line":
            T.append(f'<line x1="{x}" y1="{y - 6}" x2="{x + 40}" y2="{y - 6}" stroke="{LINK}" stroke-width="2"/>')
            tx = x + 52
        elif kind == "note":
            tx = x
        else:
            badge(kind, x + 12, y - 6)
            tx = x + 36
        c.text("top", tx, y, label, size=16, fill=MUTED)
        end = tx + text_w(label)
        x = ((end + 40 + 3) // 4) * 4
    assert end <= c.w - 40, f"legend row too wide: {end}"


legend_row(660, [("line", "요청 경로 (3부)"), (1, "모델 적재: Hugging Face에서 S3로 (쓰기 역할)"),
                 (2, "가중치 스트리밍, compile 캐시 복원 (읽기 역할)")])
legend_row(688, [(3, "compile 캐시 게시 (쓰기 역할)"), (4, "컨테이너 이미지 사전 pull (노드 부팅 중)"),
                 ("note", "S3 권한: EKS Pod Identity로 연결한 IAM 역할")])

c.check()
draft_html, draft_svg = os.path.join(BUILD, SLUG + ".draft.html"), os.path.join(BUILD, SLUG + ".draft.svg")
c.write(draft_html, draft_svg)
for src, ext in ((draft_html, ".html"), (draft_svg, ".svg")):
    out = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "embed.py"), src,
                          os.path.join(OUT, SLUG + ext)], capture_output=True, text=True)
    print(out.stdout.strip(), out.stderr.strip())
    assert out.returncode == 0 and "missing" not in out.stdout.lower().replace("0 missing", ""), out.stdout
print("OK fig01")
