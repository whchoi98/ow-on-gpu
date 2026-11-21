"""Shared helpers for the figures of the series "OpenWeight on AWS GPU".

A figure module holds its layout and two text sets (T_KO and T_EN). FIG_LANG picks one.
The same modules are kept in ow-on-gpu/blog/<part>/diagrams/infographic (Korean set for the AWS blog draft)
and in the figures/ folder of the personal blog post (Korean and English sets).
"""
import os

LANG = os.environ.get("FIG_LANG", "ko")   # "ko" or "en"
SUB = "OpenWeight on AWS GPU"             # the orange line under every figure title


def pick(ko, en):
    """The Korean or the English value, by FIG_LANG."""
    return en if LANG == "en" else ko


SERIES = pick([("1", "API 호출"), ("2", "구조와 최적화"), ("3", "구축 과정")],
              [("1", "API call"), ("2", "Architecture"), ("3", "Build steps")])
