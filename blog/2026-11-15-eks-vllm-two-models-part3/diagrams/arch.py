# -*- coding: utf-8 -*-
# 그림 2. 요청 경로와 접근 제한 (aws-diagram 스킬의 공식 아이콘과 중첩 규칙, 블로그 프로필 1280x720)
# draft SVG에 bundle: 참조를 쓰고, aws-diagram의 embed.py로 아이콘을 내장한 뒤 HTML로 감싼다.
import os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_lib import SANS, MONO, PAPER, INK, MUTED, SOFT, RULE, esc, rounded_path

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get("BLOG_IMAGES", os.path.join(HERE, "..", "images"))
EMBED = os.environ["AWS_DIAGRAM_EMBED"]          # aws-diagram 스킬의 scripts/embed.py
SLUG = "2026-11-15-eks-vllm-two-models-part3"
NAME = f"{SLUG}-fig02-request-path"
W, H = 1280, 720
VPC_GREEN, TEAL = "#7AA116", "#00A4A6"

zones, arrows, labels, nodes, top = [], [], [], [], []


def g4(*v):
    for x in v:
        assert x % 4 == 0, f"not on 4px grid: {x}"


def text(layer, x, y, s, size=16, weight=400, fill=INK, anchor="start", mono=False):
    g4(x, y)
    layer.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
                 f'font-family="{MONO if mono else SANS}" text-anchor="{anchor}">{esc(s)}</text>')


def zone(x, y, w, h, label, stroke, badge=None, dashed=False, fill="none", lx=None):
    g4(x, y, w, h)
    dash = ' stroke-dasharray="6,4"' if dashed else ""
    zones.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}" '
                 f'stroke-width="1.6"{dash}/>')
    tx = x + 12
    if badge:
        zones.append(f'<image href="bundle:{badge}" x="{x+8}" y="{y+8}" width="24" height="24"/>')
        tx = x + 40
    text(zones, tx, y + 28, label, size=16, weight=600, fill=stroke if stroke != TEAL else INK)


def icon_node(cx, cy, ref, name, sub=None, tag=None, sub2=None):
    """아이콘(48px)과 그 아래 이름, 부제. ref가 없으면 AWS 아이콘이 없는 구성 요소이므로 글자 표식을 넣은 사각형을 쓴다."""
    g4(cx, cy)
    x, y = cx - 24, cy - 24
    if ref:
        nodes.append(f'<image href="bundle:{ref}" x="{x}" y="{y}" width="48" height="48"/>')
    else:
        nodes.append(f'<rect x="{x}" y="{y}" width="48" height="48" rx="6" fill="{PAPER}" stroke="{INK}" stroke-width="1.2"/>')
        text(nodes, cx, cy + 4, tag, size=16, weight=600, fill=INK, anchor="middle", mono=True)
    text(nodes, cx, cy + 48, name, size=20, weight=600, anchor="middle")
    if sub:
        text(nodes, cx, cy + 68, sub, size=16, fill=MUTED, anchor="middle", mono=True)
    if sub2:
        text(nodes, cx, cy + 88, sub2, size=16, fill=MUTED, anchor="middle", mono=True)


def arrow(pts, label=None, side="above", shift=0, marker=True, pw=None, dashed=False):
    for p in pts:
        g4(*p)
    m = ' marker-end="url(#arrow)"' if marker else ""
    d = ' stroke-dasharray="6,4"' if dashed else ""
    arrows.append(f'<path d="{rounded_path(pts, r=8)}" fill="none" stroke="{MUTED}" stroke-width="1.4"{d}{m}/>')
    if label:
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        mx, my = (x1 + x2) // 2 + shift, (y1 + y2) // 2
        pw = pw or (len(label) * 10 + 16) // 8 * 8
        px = (mx - pw // 2) // 4 * 4
        py = my - 32 if side == "above" else my + 8
        labels.append(f'<rect x="{px}" y="{py}" width="{pw}" height="24" rx="2" fill="{PAPER}"/>')
        text(labels, px + pw // 2, py + 20, label, size=16, fill=SOFT, anchor="middle", mono=True)


# ---- 제목과 그룹 (AWS Cloud > VPC > EKS 클러스터) ----
# 2026-11-15부터 BFF는 EKS 파드다. 내부 ALB만 클러스터 밖(VPC)에 있고, BFF는 게이트웨이와 깨우기 API를 Service로 부른다.
text(top, 40, 44, "요청 경로와 접근 제한 (서울 리전, 인터넷에 열린 곳은 CloudFront 하나)", size=20, weight=600)
zone(144, 60, 1108, 572, "AWS Cloud", INK, badge="group/AWS-Cloud_32")
zone(304, 96, 936, 524, "VPC (프라이빗 서브넷)", VPC_GREEN, badge="group/Virtual-private-cloud-VPC_32")
zone(528, 104, 700, 508, "Amazon EKS 클러스터", TEAL, badge="service/Amazon-Elastic-Kubernetes-Service",
     dashed=True, fill="#F4FAFB")

# ---- 노드 ----
ROW, R_DEC, R_NLB, R_QWEN, R_WAKE = 288, 152, 168, 424, 536
X_BFF, X_GW, X_EPP, X_LLM = 608, 800, 976, 1136
icon_node(80, ROW, "resource/Users", "사용자", "HTTPS")
icon_node(224, 152, "service/AWS-WAF", "AWS WAF", "IP당 5분 300회")
icon_node(224, ROW, "service/Amazon-CloudFront", "CloudFront")
icon_node(224, 424, "service/Amazon-Simple-Storage-Service", "S3", "정적 페이지")
icon_node(224, 552, "service/Amazon-Cognito", "Cognito", "로그인")
icon_node(384, R_NLB, "service/Elastic-Load-Balancing", "게이트웨이 NLB", "SG: 배치")
icon_node(384, ROW, "service/Elastic-Load-Balancing", "내부 ALB", "SG: CloudFront")
icon_node(X_BFF, ROW, None, "BFF", "파드 2개", tag="BFF", sub2="Graviton 노드")
icon_node(X_GW, ROW, None, "agentgateway", "파드 2개", tag="GW")
icon_node(X_GW, R_WAKE, None, "깨우기 API", "NetworkPolicy", tag="API")
icon_node(X_EPP, ROW, None, "EPP", "풀 gemma", tag="EPP")
icon_node(X_EPP, R_QWEN, None, "EPP", "풀 qwen", tag="EPP")
icon_node(X_LLM, R_DEC, None, "Decider 2B", "g6.xlarge", tag="2B")
icon_node(X_LLM, ROW, None, "Gemma 4 31B", "g6e.4xlarge", tag="vLLM")
icon_node(X_LLM, R_QWEN, None, "Qwen3.8-27B", "g6e.4xlarge", tag="vLLM")

# ---- 연결 ----
arrow([(104, ROW), (200, ROW)])
arrows.append(f'<path d="M224 244 L224 264" fill="none" stroke="{MUTED}" stroke-width="1.4"/>')   # WAF 연결(화살표 없음)
arrow([(224, 348), (224, 400)])                                    # 기본 경로: S3
arrow([(80, 368), (80, 552), (200, 552)])                          # 로그인
arrow([(248, ROW), (360, ROW)], label="/v1/*")
arrow([(408, ROW), (584, ROW)], label="8080", shift=-24)           # 내부 ALB -> BFF 파드
arrow([(632, ROW), (776, ROW)], label="Service")                   # BFF -> 게이트웨이 Service
arrow([(632, ROW + 12), (688, ROW + 12), (688, R_WAKE), (776, R_WAKE)], label="/wake")   # BFF -> 깨우기 API Service
arrow([(408, R_NLB), (X_GW, R_NLB), (X_GW, ROW - 24)], dashed=True)                       # 배치 작업: NLB -> 게이트웨이
arrow([(824, ROW - 12), (872, ROW - 12), (872, R_DEC), (1112, R_DEC)], label="/decide", side="below")
arrow([(824, ROW), (952, ROW)])
arrow([(824, ROW + 12), (896, ROW + 12), (896, R_QWEN), (952, R_QWEN)])
arrow([(1000, ROW), (1112, ROW)])
arrow([(1000, R_QWEN), (1112, R_QWEN)])
arrow([(824, R_WAKE), (1212, R_WAKE), (1212, R_QWEN), (1160, R_QWEN)])
labels.append(f'<rect x="968" y="504" width="96" height="24" rx="2" fill="{PAPER}"/>')
text(labels, 1016, 524, "/wake_up", size=16, fill=SOFT, anchor="middle", mono=True)

# ---- 범례 ----
y = 664
top.append(f'<line x1="40" y1="{y-16}" x2="{W-40}" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
text(top, 40, y + 12, "범례", size=16, weight=600, fill=MUTED)
top.append(f'<line x1="120" y1="{y+2}" x2="160" y2="{y+2}" stroke="{MUTED}" stroke-width="1.4" marker-end="url(#arrow)"/>')
text(top, 172, y + 8, "요청 경로", size=16, fill=MUTED)
top.append(f'<line x1="272" y1="{y+2}" x2="312" y2="{y+2}" stroke="{MUTED}" stroke-width="1.4" stroke-dasharray="6,4" '
           f'marker-end="url(#arrow)"/>')
text(top, 324, y + 8, "배치 작업 경로", size=16, fill=MUTED)
text(top, 464, y + 8, "SG = 보안 그룹이 허용하는 출발지 / Service = 로드 밸런서 없이 클러스터 안에서 호출",
     size=16, fill=MUTED)

TITLE = "요청 경로와 접근 제한"
DESC = ("사용자의 요청이 CloudFront와 AWS WAF, VPC origin, 내부 ALB를 지나 Amazon EKS 클러스터 안의 BFF 파드, agentgateway, "
        "모델별 EPP를 거쳐 Gemma 4 31B와 Qwen3.8-27B의 vLLM 파드에 도달하고, BFF 파드가 게이트웨이와 깨우기 API를 "
        "클러스터 안의 Service로 호출하며, 배치 작업은 게이트웨이의 내부 NLB로 들어오는 경로를 나타낸 아키텍처 그림")
defs = (f'<defs><marker id="arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
        f'<polygon points="0 0, 10 4, 0 8" fill="{MUTED}"/></marker></defs>')
body = "\n".join(zones + arrows + labels + nodes + top)
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
       f'aria-labelledby="{SLUG}-fig02-title {SLUG}-fig02-desc">\n<title id="{SLUG}-fig02-title">{esc(TITLE)}</title>\n'
       f'<desc id="{SLUG}-fig02-desc">{esc(DESC)}</desc>\n{defs}\n<rect width="100%" height="100%" fill="{PAPER}"/>\n{body}\n</svg>')

draft = os.path.join(HERE, "fig02-draft.svg")
final = os.path.join(OUT, NAME + ".svg")
with open(draft, "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + svg)
print(subprocess.run([sys.executable, EMBED, draft, final], capture_output=True, text=True).stdout.strip())
embedded = open(final, encoding="utf-8").read().split("?>\n", 1)[1]
html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{esc(TITLE)}</title>
<style>
@font-face{{font-family:'Amazon Ember';font-weight:400;src:local('Amazon Ember'),local('AmazonEmber-Regular');}}
@font-face{{font-family:'Amazon Ember';font-weight:600;src:local('Amazon Ember Medium'),local('Amazon Ember SemiBold'),local('Amazon Ember Bold');}}
@font-face{{font-family:'Amazon Ember Mono';font-weight:400;src:local('Amazon Ember Mono'),local('AmazonEmberMono-Regular');}}
html,body{{margin:0;background:#fff;}} svg{{display:block;width:{W}px;height:{H}px;}}
</style></head><body>{embedded}</body></html>'''
with open(os.path.join(OUT, NAME + ".html"), "w", encoding="utf-8") as f:
    f.write(html)
print("OK fig02")
