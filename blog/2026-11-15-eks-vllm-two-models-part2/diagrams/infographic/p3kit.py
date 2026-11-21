"""Drawing helpers shared by the priority and sleep figures of Part 2 (p4_priority, p5_sleep)."""
from infokit import CODE_FAMILY, F, badge, card, cw, rw

from common import SERIES  # noqa: F401  (re-exported for the figure modules)

EKS = "service/Amazon-Elastic-Kubernetes-Service"
EC2 = "service/Amazon-EC2"
ELB = "service/Elastic-Load-Balancing"
S3 = "service/Amazon-Simple-Storage-Service"


def sec(d, x, y, w, h, num, title, take=None, k=1.0):
    """infokit.section과 같은 모양을 배율 k로 그린다. 내용이 시작하는 y를 돌려준다."""
    box = (x, y, w, h)
    card(d, x, y, w, h)
    badge(d, x + 34 * k, y + 33 * k, num, r=15 * k, size=F(16, k))
    runs = [(title, F(21, k), 700, "text", 0, 0.2)]
    if take:
        runs.append((take, F(15, k), 400, "muted", round(14 * k)))
    d.runs(x + 58 * k, y + 40 * k, runs, box=box)
    return y + 66 * k


def node(d, x, y, w, h, icon, title, sub=None, value=None, k=1.0, stroke="line2", value_color="orange", sw=1.3):
    """아이콘, 이름, 설명 한 줄, 값 한 줄이 든 구성 요소 칸."""
    box = (x, y, w, h)
    d.rect(x, y, w, h, rx=10 * k, fill="panel", stroke=stroke, sw=sw)
    d.icon(icon, x + 10 * k, y + 9 * k, 26 * k)
    size = F(13.5, k)
    while rw(title, size, 700) > w - 52 * k and size > 10:  # 긴 이름은 글자를 줄여 칸에 맞춘다
        size -= 0.5
    d.text(x + 43 * k, y + 27 * k, title, size, 700, "text", box=box)
    if sub:
        d.text(x + 10 * k, y + 53 * k, sub, F(11.5, k), 400, "muted", box=box)
    if value:
        d.text(x + 10 * k, y + 72 * k, value, F(12, k), 700, value_color, box=box)


def code(d, x, y, s, size, color="text2", anchor="start", box=None):
    """실제 코드, 헤더, 경로에만 쓰는 D2Coding 글자. 폭을 돌려준다."""
    d.text(x, y, s, size, 400, color, anchor, box=box, family=CODE_FAMILY)
    return cw(s, size)


def chip(d, x, y, w, h, text, color, size=13, fo=0.16, txt=None, box=None, sw=1.2, dash=None):
    """요청 하나를 나타내는 작은 칸(색이 종류를 나타낸다)."""
    d.rect(x, y, w, h, rx=min(6, h / 2), fill=color + "F", fo=fo, stroke=color, sw=sw, dash=dash)
    if text:
        d.text(x + w / 2, y + h / 2 + size * 0.36, text, size, 700, txt or color, "middle", box=box)


def stat(d, x, y, w, h, value, label, color, k=1.0, box=None, vsize=19, lsize=12.5):
    """값 하나와 그 뜻을 적은 칸."""
    d.rect(x, y, w, h, rx=10, fill="panel", stroke="cardline", sw=1.2)
    d.rect(x, y + 10 * k, 4 * k, h - 20 * k, rx=2 * k, fill=color + "F")
    d.text(x + 16 * k, y + h / 2 - 3 * k, value, F(vsize, k), 700, color, box=box)
    d.text(x + 16 * k, y + h / 2 + 17 * k, label, F(lsize, k), 400, "muted", box=box)
