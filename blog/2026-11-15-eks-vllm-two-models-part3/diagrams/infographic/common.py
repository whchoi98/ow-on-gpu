"""Shared helpers for the figures of the series "OpenWeight on AWS GPU".

A figure module holds its layout and two text sets (T_KO and T_EN). FIG_LANG picks one.
The same modules build the Korean figures of the AWS blog draft
(ow-on-gpu/blog/2026-11-15-eks-vllm-two-models-part3/diagrams/infographic) and the Korean and English
figures of the personal blog post.
"""
import os

LANG = os.environ.get("FIG_LANG", "ko")   # "ko" or "en"


def pick(ko, en):
    """The Korean or the English value, by FIG_LANG."""
    return en if LANG == "en" else ko


SERIES = pick([("1", "API 호출"), ("2", "구조와 최적화"), ("3", "구축 과정")],
              [("1", "API call"), ("2", "Architecture"), ("3", "Build steps")])
PART = "3"
