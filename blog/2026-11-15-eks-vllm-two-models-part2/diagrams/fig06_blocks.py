# -*- coding: utf-8 -*-
# 그림 6. Qwen3.8-27B의 KV 캐시 블록 배분: MTP를 켠 구성과 끈 구성.
# my-plugins:aws-diagram-design의 Nested containment 유형(KV 캐시 > 요청 > 그룹 > 블록)으로 그린 단일 HTML.
# 크기와 글자는 블로그 프로필(1280x720, 20px/16px, 4px 그리드)을 따른다.
#   python3 fig06_blocks.py <out.html> <out.svg>
# 값의 출처: docs/08-results.md "Qwen의 동시 3건 한도", results/2026-11-14-slo/qwen, results/2026-11-15-slo-qwen-no-mtp
import sys

W, H = 1280, 720
PAPER, INK, MUTED, SOFT = "#FFFFFF", "#232F3E", "#545B64", "#7D8998"
RULE = "rgba(35,47,62,0.12)"
PURPLE = "#8C4FFF"
SANS = "'Amazon Ember', 'Noto Sans CJK KR', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'Amazon Ember Mono', 'Noto Sans CJK KR', ui-monospace, monospace"
CELL, GAP = 20, 4
out = []


def g4(*v):
    for x in v:
        assert x % 4 == 0, f"not on 4px grid: {x}"


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def text(x, y, s, size=16, weight=400, fill=INK, anchor="start", mono=False):
    g4(x, y)
    out.append(f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" font-weight="{weight}" '
               f'font-family="{MONO if mono else SANS}" text-anchor="{anchor}">{esc(s)}</text>')


def ring(x, y, w, h, stroke, so=1.0, fill=PAPER, fo=1.0, sw=1, rx=6, dash=None):
    g4(x, y, w, h)
    d = f' stroke-dasharray="{dash}"' if dash else ""
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" fill-opacity="{fo}" '
               f'stroke="{stroke}" stroke-opacity="{so}" stroke-width="{sw}"{d}/>')


def cell(x, y, kind):
    g4(x, y)
    style = {
        "state": f'fill="{PURPLE}" fill-opacity="0.55" stroke="{PURPLE}" stroke-width="1"',
        "spec": f'fill="{PURPLE}" fill-opacity="0.14" stroke="{PURPLE}" stroke-width="1"',
        "attn": f'fill="{INK}" fill-opacity="0.30" stroke="{INK}" stroke-width="1"',
        "free": f'fill="{PAPER}" stroke="{MUTED}" stroke-width="1" stroke-dasharray="3,3"',
    }[kind]
    out.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2" {style}/>')


def cells(x, y, kinds):
    for i, k in enumerate(kinds):
        cell(x + i * (CELL + GAP), y, k)
    return x + len(kinds) * (CELL + GAP) - GAP


def zone(x, title, eyebrow):
    ring(x, 72, 584, 536, INK, so=0.30, fill=INK, fo=0.03, sw=1.2, rx=8)
    text(x + 16, 104, title, size=20, weight=600)
    text(x + 16, 128, eyebrow, size=16, fill=SOFT, mono=True)


def summary(x, lines, headline, tail):
    text(x, 472, lines[0], size=16, fill=MUTED, mono=True)
    text(x, 500, lines[1], size=16, fill=MUTED, mono=True)
    text(x, 544, headline, size=20, weight=600)
    text(x, 576, tail, size=16, fill=INK, mono=True)


def build():
    text(40, 44, "Qwen3.8-27B의 KV 캐시 블록 배분: MTP를 켠 구성과 끈 구성 (S1 짧은 채팅, vLLM v0.33.0)", size=20, weight=600)

    # ---------------- 왼쪽: MTP 켬
    zone(40, "MTP 켬 (추측 토큰 3개)", "KV 캐시 2.45GiB, 46블록")
    used = 0
    gx = [144, 260, 376]            # Mamba 그룹 고리 3개의 x
    for i, name in enumerate(["Mamba 1", "Mamba 2", "Mamba 3"]):
        text(gx[i] + 56, 160, name, size=16, fill=SOFT, anchor="middle")
    text(512, 160, "attention", size=16, fill=SOFT, anchor="middle")
    for r in range(3):
        y = 172 + r * 64
        text(64, y + 32, f"요청 {r+1}", size=16, fill=INK)
        ring(136, y, 400, 52, MUTED)                                   # 요청 고리 (13블록)
        for x in gx:
            ring(x, y + 8, 108, 36, SOFT, sw=0.8, dash="4,3")          # Mamba 그룹 고리 (4블록)
            cells(x + 8, y + 16, ["state", "spec", "spec", "spec"])
            used += 4
        ring(492, y + 8, 36, 36, SOFT, sw=0.8, dash="4,3")             # attention 그룹 (1블록)
        cell(500, y + 16, "attn")
        used += 1
    assert used == 39
    end = cells(144, 376, ["free"] * (46 - used))
    text(end + 16, 392, "남은 7블록", size=16, fill=MUTED)
    text(144, 428, "네 번째 요청은 13블록이 필요해 대기 (사유 capacity)", size=16, fill=MUTED)
    summary(56, ["요청당 13블록 = Mamba 그룹 3개 × (1 + 추측 3) + attention 1",
                 "46블록 ÷ 13블록 = 3건 (KV 캐시 사용률 0.848)"],
            "동시 실행 3건", "요청 하나 32.5 tok/s (동시성 1), 최대 처리량 91.2 tok/s")

    # ---------------- 오른쪽: MTP 끔
    zone(656, "MTP 끔", "KV 캐시 4.0GiB, 82블록")
    text(672, 160, "요청 번호", size=16, fill=SOFT)
    used = 0
    for r in range(5):
        y = 172 + r * 44
        text(672, y + 24, f"{r*4+1}~{r*4+4}", size=16, fill=INK, mono=True)
        for k in range(4):
            x = 752 + k * 120
            ring(x, y, 108, 36, MUTED)                                 # 요청 고리 (4블록)
            cells(x + 8, y + 8, ["state", "state", "state", "attn"])
            used += 4
    assert used == 80
    end = cells(760, 400, ["free"] * (82 - used))
    text(end + 16, 416, "남은 2블록 (21번째 요청부터 대기)", size=16, fill=MUTED)
    summary(672, ["요청당 4블록 = Mamba 그룹 3개 × 1 + attention 1",
                  "82블록 ÷ 4블록 = 20건 (KV 캐시 사용률 0.976)"],
            "동시 실행 20건", "요청 하나 19.2 tok/s (동시성 1), 최대 처리량 281.8 tok/s")

    # ---------------- 범례 (아래쪽 가로 띠)
    y = 648
    out.append(f'<line x1="40" y1="{y-16}" x2="{W-40}" y2="{y-16}" stroke="{RULE}" stroke-width="0.8"/>')
    text(40, y + 12, "범례", size=16, weight=600, fill=MUTED)
    x = 120
    for kind, label, adv in [("state", "Mamba 상태 블록", 184), ("spec", "추측 토큰용 블록 (MTP)", 236),
                             ("attn", "attention 블록", 168), ("free", "남은 블록", 132)]:
        cell(x, y - 8, kind)
        text(x + 32, y + 8, label, size=16, fill=MUTED)
        x += adv
    ring(x, y - 12, 44, 28, MUTED)
    text(x + 56, y + 8, "요청 하나가 잡은 블록", size=16, fill=MUTED)
    assert x + 56 + 170 <= W - 40


TITLE = "Qwen3.8-27B의 KV 캐시 블록 배분: MTP를 켠 구성과 끈 구성"
DESC = ("MTP를 켠 구성은 KV 캐시 46블록에서 요청 하나가 Mamba 그룹 3개에 4블록씩과 attention 1블록, 모두 13블록을 잡아 "
        "3건만 동시에 실행하고 7블록이 남는다. MTP를 끈 구성은 82블록에서 요청 하나가 4블록을 잡아 20건을 동시에 실행하고 "
        "2블록이 남는다. 요청 하나의 속도는 32.5에서 19.2 tok/s로 줄고 최대 처리량은 91.2에서 281.8 tok/s로 늘어난다")
FONT_FACE = """@font-face{font-family:'Amazon Ember';font-weight:400;src:local('Amazon Ember'),local('AmazonEmber-Regular');}
@font-face{font-family:'Amazon Ember';font-weight:600;src:local('Amazon Ember Medium'),local('Amazon Ember SemiBold'),local('Amazon Ember Bold');}
@font-face{font-family:'Amazon Ember';font-weight:700;src:local('Amazon Ember Bold');}
@font-face{font-family:'Amazon Ember Mono';font-weight:400;src:local('Amazon Ember Mono'),local('AmazonEmberMono-Regular');}"""


def svg(standalone=False):
    style = f"<defs><style>{FONT_FACE}</style></defs>\n" if standalone else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'role="img" aria-labelledby="p2-fig06-title p2-fig06-desc">\n'
            f'<title id="p2-fig06-title">{esc(TITLE)}</title>\n<desc id="p2-fig06-desc">{esc(DESC)}</desc>\n'
            f'{style}<rect width="100%" height="100%" fill="{PAPER}"/>\n' + "\n".join(out) + "\n</svg>")


if __name__ == "__main__":
    build()
    html = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{esc(TITLE)}</title>
<style>
{FONT_FACE}
html,body{{margin:0;background:#fff;}} svg{{display:block;width:{W}px;height:{H}px;}}
</style></head><body>{svg()}</body></html>'''
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        f.write(html)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n' + svg(standalone=True))
    print("wrote", sys.argv[1], sys.argv[2])
