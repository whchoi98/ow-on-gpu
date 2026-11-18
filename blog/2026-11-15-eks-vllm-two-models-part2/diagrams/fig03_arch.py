# -*- coding: utf-8 -*-
# 그림 3. 측정 구성 (my-plugins:aws-diagram 절차: 공식 아이콘을 bundle: 참조로 넣고 embed.py로 내장).
#   python3 fig03_arch.py <draft.svg>      # 초안 SVG(bundle: 참조)를 쓴다
#   python3 <aws-diagram>/scripts/embed.py <draft.svg> <images>/<slug>-fig03-measurement-setup.svg
#   python3 fig03_arch.py --html <final.svg> <final.html>   # 렌더용 HTML로 감싼다
# 좌표, 글자 크기, 색은 블로그 프로필(1280x720, 20px/16px, 4px 그리드)을 따른다.
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diagram_lib import SANS, MONO, INK, MUTED, SOFT, PAPER, RULE, rounded_path, esc, text_w

W, H = 1280, 720
EC2_ORANGE = "#ED7100"      # EC2 instance contents 그룹의 테두리 색
REGION_TEAL = "#00A4A6"
out = []


def g4(*v):
    for x in v:
        assert x % 4 == 0, f"not on 4px grid: {x}"


def text(x, y, s, size=16, weight=400, fill=INK, anchor="start", mono=False):
    g4(x, y)
    out.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
               f'font-family="{MONO if mono else SANS}" text-anchor="{anchor}">{esc(s)}</text>')


def rect(x, y, w, h, fill="none", fo=1, stroke=INK, so=1, sw=1.2, rx=8, dash=None):
    g4(x, y, w, h)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" fill-opacity="{fo}" '
               f'stroke="{stroke}" stroke-opacity="{so}" stroke-width="{sw}"{d}/>')


def icon(ref, x, y, size):
    g4(x, y, size)
    out.append(f'<image href="bundle:{ref}" x="{x}" y="{y}" width="{size}" height="{size}"/>')


def arrow(pts, dashed=False):
    for p in pts:
        g4(*p)
    d = ' stroke-dasharray="6,4"' if dashed else ""
    out.append(f'<path d="{rounded_path(pts, r=8)}" fill="none" stroke="{INK}" stroke-width="1.6"{d} marker-end="url(#p2f1-arrow)"/>')


def node_group(x, y, w, h, title, subs):
    """EC2 인스턴스(노드) 그룹: 주황 테두리 + EC2 instance contents 배지."""
    rect(x, y, w, h, fill=PAPER, stroke=EC2_ORANGE, sw=1.4, rx=6)
    icon("group/EC2-instance-contents_32", x + 12, y + 12, 24)
    text(x + 44, y + 32, title, size=20, weight=600)
    for i, s in enumerate(subs):
        assert text_w(s) <= w - 32, f"sublabel too wide: {s}"
        text(x + 16, y + 60 + 24 * i, s, size=16, fill=MUTED, mono=True)


def pod(x, y, w, h, name, sub):
    """파드: 공식 아이콘이 없으므로 이름을 적은 둥근 사각형으로 그린다."""
    rect(x, y, w, h, fill=PAPER, stroke=INK, sw=1, rx=6)
    assert text_w(name, 20) <= w - 24 and text_w(sub) <= w - 24, f"pod text too wide: {name} / {sub}"
    text(x + 16, y + 36, name, size=20, weight=600)
    text(x + 16, y + 64, sub, size=16, fill=MUTED, mono=True)


def build():
    # 제목
    text(40, 44, "측정 구성: 측정 Job은 vLLM Service를 직접 호출하고, 지표는 Prometheus agent가 수집", size=20, weight=600)
    # AWS Cloud, 리전
    rect(40, 64, 1200, 560, stroke=INK, sw=2)
    icon("group/AWS-Cloud_32", 52, 68, 28)
    text(88, 88, "AWS Cloud", size=16, weight=600)
    rect(64, 100, 1152, 512, stroke=REGION_TEAL, sw=2, dash="6,4")
    icon("group/Region_32", 76, 108, 28)
    text(112, 128, "서울 리전 (ap-northeast-2)", size=16, weight=600, fill=REGION_TEAL)
    # EKS 클러스터
    rect(88, 144, 912, 456, fill=INK, fo=0.03, stroke=INK, so=0.35)
    icon("service/Amazon-Elastic-Kubernetes-Service", 104, 152, 32)
    text(148, 176, "Amazon EKS 클러스터 (Kubernetes 1.37)", size=16, weight=600)

    # 그리는 순서: 노드 그룹 -> 화살표 -> 파드. 화살표 끝이 파드의 변에 닿고, 그룹의 흰 바탕에 가려지지 않는다.
    text(112, 256, "게이트웨이를 거치지 않고", size=16, fill=SOFT)
    text(112, 280, "vLLM Service(8000)를 직접 호출", size=16, fill=SOFT)
    node_group(112, 296, 224, 208, "측정 전용 노드", ["NodePool bench", "c7i-flex.2xlarge"])
    node_group(432, 208, 272, 176, "GPU 노드", ["g6e.4xlarge, L40S 1장"])
    node_group(432, 408, 272, 176, "GPU 노드", ["g6e.4xlarge, L40S 1장"])
    text(768, 280, "/metrics를 5초마다 수집", size=16, fill=SOFT)
    node_group(768, 296, 208, 176, "system 노드", [])

    arrow([(320, 428), (384, 428), (384, 324), (448, 324)])                # Job -> vLLM Gemma
    arrow([(320, 460), (384, 460), (384, 524), (448, 524)])                # Job -> vLLM Qwen
    arrow([(688, 324), (736, 324), (736, 396), (784, 396)], dashed=True)   # Gemma /metrics -> agent
    arrow([(688, 524), (736, 524), (736, 428), (784, 428)], dashed=True)   # Qwen /metrics -> agent
    arrow([(960, 412), (1060, 412)], dashed=True)                          # agent -> AMP

    pod(128, 400, 192, 88, "측정 Job", "bench_serve.py")
    pod(448, 280, 240, 88, "vLLM: Gemma 4 31B", "vllm-gemma:8000")
    pod(448, 480, 240, 88, "vLLM: Qwen3.8-27B", "vllm-qwen:8000")
    pod(784, 368, 176, 88, "Prometheus", "agent 모드")
    # Amazon Managed Service for Prometheus
    icon("service/Amazon-Managed-Service-for-Prometheus", 1064, 380, 64)
    for i, s in enumerate(["Amazon Managed", "Service for", "Prometheus"]):
        text(1096, 468 + 24 * i, s, size=16, weight=600, anchor="middle")
    for i, s in enumerate(["remote write", "SigV4 서명", "EKS Pod Identity"]):
        text(1096, 308 + 24 * i, s, size=16, fill=SOFT, anchor="middle", mono=True)

    # 범례
    y = 664
    out.append(f'<line x1="40" y1="{y-16}" x2="{W-40}" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
    text(40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    x = 120
    out.append(f'<line x1="{x}" y1="{y+2}" x2="{x+40}" y2="{y+2}" stroke="{INK}" stroke-width="1.6" marker-end="url(#p2f1-arrow)"/>')
    text(x + 52, y + 8, "측정 요청 (OpenAI 호환 API, 스트리밍)", size=16, fill=MUTED)
    x = 464
    out.append(f'<line x1="{x}" y1="{y+2}" x2="{x+40}" y2="{y+2}" stroke="{INK}" stroke-width="1.6" stroke-dasharray="6,4" marker-end="url(#p2f1-arrow)"/>')
    text(x + 52, y + 8, "지표 수집과 전송", size=16, fill=MUTED)
    x = 684
    out.append(f'<rect x="{x}" y="{y-10}" width="40" height="24" rx="4" fill="{PAPER}" stroke="{EC2_ORANGE}" stroke-width="1.4"/>')
    text(x + 52, y + 8, "노드 (Amazon EC2 인스턴스)", size=16, fill=MUTED)
    x = 980
    out.append(f'<rect x="{x}" y="{y-10}" width="40" height="24" rx="4" fill="{PAPER}" stroke="{INK}"/>')
    text(x + 52, y + 8, "파드", size=16, fill=MUTED)


TITLE = "측정 구성: 측정 Job에서 vLLM Service로, 지표는 Prometheus agent에서 Amazon Managed Service for Prometheus로"
DESC = ("서울 리전의 Amazon EKS 클러스터에서 측정 전용 노드(c7i-flex.2xlarge)의 측정 Job이 게이트웨이를 거치지 않고 "
        "g6e.4xlarge 두 대의 vLLM 파드(Gemma 4 31B, Qwen3.8-27B)를 Service로 직접 호출하고, system 노드의 Prometheus agent가 "
        "두 파드의 /metrics를 5초마다 수집해 Amazon Managed Service for Prometheus로 remote write하는 구성")


def svg():
    build()
    defs = (f'<defs><marker id="p2f1-arrow" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto">'
            f'<polygon points="0 0, 10 4, 0 8" fill="{INK}"/></marker></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-labelledby="p2-fig03-title p2-fig03-desc">\n'
            f'<title id="p2-fig03-title">{esc(TITLE)}</title>\n<desc id="p2-fig03-desc">{esc(DESC)}</desc>\n'
            f'{defs}\n<rect width="100%" height="100%" fill="{PAPER}"/>\n' + "\n".join(out) + "\n</svg>")


def html(svg_text):
    body = svg_text.split("?>", 1)[-1].strip() if svg_text.lstrip().startswith("<?xml") else svg_text
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{esc(TITLE)}</title>
<style>
@font-face{{font-family:'Amazon Ember';font-weight:400;src:local('Amazon Ember'),local('AmazonEmber-Regular');}}
@font-face{{font-family:'Amazon Ember';font-weight:600;src:local('Amazon Ember Medium'),local('Amazon Ember SemiBold'),local('Amazon Ember Bold');}}
@font-face{{font-family:'Amazon Ember';font-weight:700;src:local('Amazon Ember Bold');}}
@font-face{{font-family:'Amazon Ember Mono';font-weight:400;src:local('Amazon Ember Mono'),local('AmazonEmberMono-Regular');}}
html,body{{margin:0;background:#fff;}} svg{{display:block;width:{W}px;height:{H}px;}}
</style></head><body>{body}</body></html>'''


if __name__ == "__main__":
    if sys.argv[1] == "--html":
        with open(sys.argv[2], encoding="utf-8") as f:
            s = f.read()
        with open(sys.argv[3], "w", encoding="utf-8") as f:
            f.write(html(s))
        print("wrote", sys.argv[3])
    else:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + svg())
        print("wrote", sys.argv[1])
