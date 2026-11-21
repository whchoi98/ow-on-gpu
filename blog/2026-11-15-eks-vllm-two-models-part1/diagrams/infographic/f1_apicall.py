"""Part 1, figure 1: the eight stages of one LLM API call.

The drawing is docs/infographic/apicall.py of the ow-on-gpu repository, used as it is (the web page's "API call"
view shows the same figure). This module picks the language, puts the series name in the subtitle and rewords
one label.
"""
import apicall

from common import LANG, SERIES_NAME

for text in apicall.TEXT.values():
    text["sub_en"] = SERIES_NAME
apicall.TEXT["ko"]["s3_rows"][2] = ("측정", "토큰화 시간은 따로 측정하지 않음")


def landscape(theme):
    apicall.use(LANG)
    return apicall.landscape(theme)
