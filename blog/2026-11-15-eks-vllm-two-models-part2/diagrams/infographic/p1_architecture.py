"""Part 2, figure 1: the whole architecture. The request path, the model and image supply path (badges 0 to 5),
the model decision order, the measured segments and the access limits on one page.

The drawing is the request path infographic of the repo (docs/infographic/flow.py, "08"), unchanged. This module
only swaps the header text for the series, rewrites the default row of the decision table and adds the series chips.
"""
from infokit import Doc, footer_note, header, series_nav

import flow
from common import LANG, SERIES, SUB, pick

flow.use(LANG)

HEAD = pick(
    dict(title="두 모델을 서빙하는 구조", sub_ko="브라우저에서 GPU까지의 경로, 모델과 이미지 공급, 측정값"),
    dict(title="The Architecture for Serving Two Models",
         sub_ko="Path from browser to GPU, model and image supply, measured values"),
)
# Since 2026-11-17 a request sent by default is marked sensitive only when the Decider gives no answer or its
# personal-data judgment is below the threshold, so the row names the model and leaves the marking to Part 1.
# The count in the subtitle of the access section is written with a numeral, like the counts in the post.
ACCESS = pick(("경계별 접근 제한", "바깥에서 안쪽으로 5겹과 웹 검색"), None)
DEFAULT_RULE = pick(("기본", "Decider 무응답 또는 신뢰도 미달", "Gemma, thinking 끔", "orange"),
                    ("Default", "Decider silent or below 0.6", "Gemma, thinking off", "orange"))


def landscape(theme):
    text = flow.T
    rules = text["rules"]
    text["rules"] = rules[:-1] + [DEFAULT_RULE]
    access = text["s4"]
    if ACCESS:
        text["s4"] = ACCESS
    try:
        d = Doc(1920, 1080, theme)
        d.rect(0, 0, 1920, 1080, fill="bg")
        header(d, 48, 76, HEAD["title"], SUB, HEAD["sub_ko"])
        series_nav(d, 1872, 48, SERIES, "2")
        flow.s1(d, 48, 140, 1824, 628)
        flow.s2(d, 48, 788, 640, 256)
        flow.s3(d, 708, 788, 600, 256)
        flow.s4(d, 1328, 788, 544, 256)
        footer_note(d, 1872, 1064, text["note"])
        return d.svg()
    finally:
        text["rules"] = rules
        text["s4"] = access
