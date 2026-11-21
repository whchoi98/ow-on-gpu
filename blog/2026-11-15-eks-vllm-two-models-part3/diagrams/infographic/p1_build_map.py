"""Part 3, figure 1: the architecture with the build step on each component, and the ten step cards.

The drawing is infographic "10" of the ow-on-gpu repository (docs/infographic/build_steps.py), used as is:
the same map, the same step numbers and the same step cards as the "Build steps" view of the web page.
This module only adds the series chips and sets the footer note and the English subtitle of the blog series.
"""
import build_steps
from infokit import Doc, footer_note, header, series_nav

from common import LANG, PART, SERIES, pick

NOTE = pick(
    "2026-11-14 서울 리전에서 0~8단계 적용, 웹 검색은 2026-11-15에 BFF의 도구로 추가, "
    "브라우저와 Hugging Face, Image registry는 이 환경 밖의 요소라 번호 없음",
    "Steps 0~8 applied 2026-11-14 in the Seoul Region. Web search added 2026-11-15 as a BFF tool. "
    "The browser, Hugging Face, and the image registry are outside this environment and carry no number",
)
# The Korean header keeps the English title of the figure, the English header carries the series name.
SUB_EN = "OpenWeight on AWS GPU"   # the series name, in both languages


def landscape(theme):
    build_steps.use(LANG)
    try:
        t = build_steps.T
        d = Doc(1920, 1080, theme)
        d.rect(0, 0, 1920, 1080, fill="bg")
        header(d, 48, 76, t["title"], SUB_EN or t["sub_en"], t["sub_ko"])
        series_nav(d, 1872, 48, SERIES, PART)
        build_steps.s1(d, 48, 140, 1824, 584)
        build_steps.s2(d, 48, 744, 1824, 300)
        footer_note(d, 1872, 1064, NOTE)
        return d.svg()
    finally:
        build_steps.use("ko")
