"""Part 1, figure 2: how one request gets its model.

Section 1 is the decision order of the BFF (app/bff/routing.py), section 2 what Strands Decider 12B returns and
how the BFF reads it (routing.from_decider, docs/05-decider.md), section 3 the path the decision takes to the
engine (docs/04-gateway.md, docs/06-sleep.md, docs/08-results.md).
"""
from infokit import Doc, footer_note, header, rw, section, series_nav, tag

from common import SERIES, SERIES_NAME, pick
from p1kit import EC2, EKS, chip, code, code_chip, measured, node, stat

GEMMA, QWEN = "Gemma 4 31B", "Qwen3.8-27B"

T_KO = dict(
    title="요청별 모델 결정 순서",
    sub_ko="BFF의 규칙, Decider 12B의 판단, 게이트웨이의 풀 선택",
    s1=("BFF의 결정 순서", "위에서부터 먼저 맞는 규칙 하나를 적용"),
    cols=("조건", "결정", "x-bff-decision"),
    rules=[
        ("민감 정보 형식", "주민등록번호, 카드번호(Luhn 검사)", [(GEMMA, "purple")], "민감 정보 요청으로 표시", "rule"),
        ("업무 종류 헤더", "상담, 번역, 요약 / 이미지 이해, OCR, 코딩", [(GEMMA, "purple"), (QWEN, "blue")],
         "배정표에 적힌 모델", "task"),
        ("이미지 첨부", "업무 종류 없이 이미지가 든 요청", [(QWEN, "blue")], None, "attachment"),
        ("Decider 12B의 판단", "두 신뢰도가 모두 0.6 이상", [("Decider 12B가 고른 모델", "green")], None, "decider"),
        ("기본값", "판단을 얻지 못했거나 신뢰도 미달", [(GEMMA, "purple")], "thinking 끔", "fallback"),
    ],
    stats1=[
        ("30분", ["세션의 결정을 재사용", "민감 정보 형식은 메시지마다 확인"], "purple"),
        ("0.1ms", ["규칙과 업무 종류로 정한", "판단 시간의 중앙값"], "orange"),
        ("422", ["민감 정보와 이미지가", "함께 온 요청은 거절"], "pink"),
    ],
    s2=("Decider 12B의 판단", "글을 생성하지 않고 선택과 확률만 반환"),
    questions=[
        ("route", "모델 선택", "선택지 gemma, qwen", "선택과 신뢰도 반환"),
        ("policy", "개인정보 여부", "이름, 연락처, 주소, 계좌", "예일 확률 반환"),
        ("thinking", "추론 필요 여부", "여러 단계를 거친 추론", "예일 확률 반환"),
    ],
    threshold=("BFF의 기준값 0.6", "route는 신뢰도, policy는 확률이 0.5에서 떨어진 정도"),
    outcomes=[
        ("모델 선택과 개인정보 판단의 신뢰도가 모두 0.6 이상", "Decider 12B가 고른 모델, 개인정보가 있으면 " + GEMMA,
         "decider", None, "green"),
        ("모델 선택만 0.6 미만, 개인정보 없음은 0.6 이상", GEMMA + ", thinking 끔, 웹 검색 가능",
         "fallback", "민감 아님", "orange"),
        ("응답 없음, 2초 초과, 개인정보 판단이 불확실", GEMMA + ", thinking 끔, 웹 검색 제외",
         "fallback", "민감 표시", "pink"),
    ],
    stats2=[
        ("약 89ms", ["질문 1개의 판단 시간", "게이트웨이 경유 89.7~90.6ms"], "orange"),
        ("143.8~159.9ms", ["BFF 파드에서 측정한 왕복", "질문 3개를 한 요청으로, 20건"], "orange"),
        ("g6e.xlarge 1대", ["NVIDIA L40S GPU 노드", "GPU 메모리 23,725MiB 사용"], "blue"),
    ],
    s3=("결정이 엔진까지 전달되는 경로", "BFF가 요청에 적은 값을 게이트웨이와 vLLM이 사용"),
    measured="측정",
    path=[
        dict(icon=EKS, title="BFF", sub="결정을 요청에 기록",
             lines=[("t", "본문에 model, priority 기록"), ("t", "헤더에 우선순위 대상 이름 기록"),
                    ("c", "x-llm-d-inference-objective")]),
        dict(icon=EKS, title="깨우기 API", sub=QWEN + " 요청만", dash=True,
             lines=[("t", "요청마다 POST /wake 호출"), ("t", "잠들어 있으면 깨운 뒤 진행")],
             value="확인 12.8ms, 깨우기 3.66초"),
        dict(icon=EKS, title="agentgateway", sub="게이트웨이 파드 2개",
             lines=[("t", "본문의 model을 헤더로 옮김"), ("t", "HTTPRoute가 모델의 풀 선택")],
             warn="등록하지 않은 model은 404"),
        dict(icon=EKS, title="InferencePool, EPP", sub="모델마다 풀 1개",
             lines=[("t", "풀 안에서 받을 파드 선택"), ("t", "포화 시 배치 요청은 429")],
             value="스케줄링 0.03ms"),
        dict(icon=EC2, title="vLLM", sub=GEMMA + ", " + QWEN,
             lines=[("t", "priority 스케줄러, 작은 값 먼저"), ("t", "상담 0, 배치 10")],
             value="배치 부하 중 상담 TTFT 30.9초 → 0.19초"),
    ],
    note="서울 리전. Decider 12B의 판단과 BFF 왕복은 2026-11-24, 깨우기는 11-15, 우선순위는 11-14에 " + GEMMA + "로 측정",
)

T_EN = dict(
    title="How a Request Gets Its Model",
    sub_ko="BFF rules, the Decider 12B judgment, the gateway picking a pool",
    s1=("Decision order of the BFF", "The first rule that matches, from the top"),
    cols=("Condition", "Decision", "x-bff-decision"),
    rules=[
        ("Sensitive data format", "Resident registration or card number (Luhn check)", [(GEMMA, "purple")],
         "Marked as a sensitive request", "rule"),
        ("Task type header", "Support, translate, summarize / vision, OCR, coding", [(GEMMA, "purple"), (QWEN, "blue")],
         "The model in the assignment table", "task"),
        ("Image attached", "A request with an image and no task type", [(QWEN, "blue")], None, "attachment"),
        ("Decider 12B judgment", "Both confidences at 0.6 or higher", [("The model Decider 12B picked", "green")], None,
         "decider"),
        ("Default", "No judgment, or confidence too low", [(GEMMA, "purple")], "Thinking off", "fallback"),
    ],
    stats1=[
        ("30 min", ["A session reuses its decision", "Sensitive formats checked per message"], "purple"),
        ("0.1 ms", ["Median decision time", "by rule or task type"], "orange"),
        ("422", ["Sensitive data together with", "an image is rejected"], "pink"),
    ],
    s2=("The Decider 12B judgment", "No generated text, only a choice and probabilities"),
    questions=[
        ("route", "Which model", "Choices: gemma, qwen", "Returns choice and confidence"),
        ("policy", "Personal data", "Name, contact, address, account", "Returns probability of yes"),
        ("thinking", "Needs reasoning", "Multi-step reasoning", "Returns probability of yes"),
    ],
    threshold=("BFF threshold 0.6", "route: confidence, policy: distance of the probability from 0.5"),
    outcomes=[
        ("Model choice and personal data both at 0.6 or higher", "The model Decider 12B picked, " + GEMMA + " if personal data",
         "decider", None, "green"),
        ("Only the model choice below 0.6, no personal data at 0.6 or higher", GEMMA + ", thinking off, web search allowed",
         "fallback", "Not sensitive", "orange"),
        ("No answer, over 2 s, or personal data uncertain", GEMMA + ", thinking off, no web search",
         "fallback", "Sensitive", "pink"),
    ],
    stats2=[
        ("About 89 ms", ["One question", "89.7~90.6 ms through the gateway"], "orange"),
        ("143.8~159.9 ms", ["Round trip measured in the BFF pod", "3 questions in one request, 20 runs"], "orange"),
        ("1 x g6e.xlarge", ["NVIDIA L40S GPU node", "23,725 MiB of GPU memory used"], "blue"),
    ],
    s3=("How the decision reaches the engine", "The gateway and vLLM use what the BFF wrote into the request"),
    measured="Measured",
    path=[
        dict(icon=EKS, title="BFF", sub="Writes the decision",
             lines=[("t", "model and priority in the body"), ("t", "Objective name in a header"),
                    ("c", "x-llm-d-inference-objective")]),
        dict(icon=EKS, title="Wake API", sub=QWEN + " requests only", dash=True,
             lines=[("t", "POST /wake on every request"), ("t", "Wakes the model if it sleeps")],
             value="Check 12.8 ms, wake 3.66 s"),
        dict(icon=EKS, title="agentgateway", sub="2 gateway pods",
             lines=[("t", "Copies the body's model to a header"), ("t", "HTTPRoute picks the model's pool")],
             warn="An unregistered model gets 404"),
        dict(icon=EKS, title="InferencePool, EPP", sub="One pool per model",
             lines=[("t", "Picks the pod inside the pool"), ("t", "429 for batch when saturated")],
             value="Scheduling 0.03 ms"),
        dict(icon=EC2, title="vLLM", sub=GEMMA + ", " + QWEN,
             lines=[("t", "Priority scheduler, low value first"), ("t", "Support 0, batch 10")],
             value="Support TTFT: 30.9 s → 0.19 s"),
    ],
    note="Seoul Region. Decider 12B and the BFF round trip: 2026-11-24. Wake: 11-15. Priority: " + GEMMA + ", 11-14",
)

T = pick(T_KO, T_EN)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    cx_cond, w_cond = x + 62, 380
    cx_res, w_res = cx_cond + w_cond + 44, 330
    cx_head = cx_res + w_res + 24
    w_head = x + w - 24 - cx_head
    d.text(cx_cond + 2, cy + 9, T["cols"][0], 12, 700, "faint", box=box)
    d.text(cx_res + 2, cy + 9, T["cols"][1], 12, 700, "faint", box=box)
    code(d, cx_head + w_head / 2, cy + 9, T["cols"][2], 12, "faint", "middle", box=box)
    top0, rh, gap = cy + 20, 70, 8
    for index, (title, sub, chips, note, value) in enumerate(T["rules"]):
        top = top0 + index * (rh + gap)
        mid = top + rh / 2
        d.circle(x + 36, mid, 13, fill="badge")
        d.text(x + 36, mid + 5.2, str(index + 1), 14, 700, "badgetext", "middle")
        d.rect(cx_cond, top, w_cond, rh, rx=10, fill="panel", stroke="line2", sw=1.2)
        d.text(cx_cond + 16, top + 30, title, 15, 700, "text", box=box)
        d.text(cx_cond + 16, top + 51, sub, 12.5, 400, "muted", box=box)
        d.arrow([(cx_cond + w_cond + 7, mid), (cx_res - 7, mid)], sw=1.6, r=0)
        d.rect(cx_res, top, w_res, rh, rx=10, fill="panel", stroke="line2", sw=1.2)
        cx = cx_res + 14
        for text, color in chips:
            cx += chip(d, cx, top + (9 if note else (rh - 28) / 2), text, color, box=box) + 8
        if note:
            d.text(cx_res + 16, top + 58, note, 12.5, 400, "muted", box=box)
        code_chip(d, cx_head, mid - 15, w_head, value, box=box)
    sy = top0 + len(T["rules"]) * (rh + gap) + 4
    sh = y + h - 16 - sy
    sw_ = (w - 48 - 2 * 12) / 3
    for index, (value, lines, color) in enumerate(T["stats1"]):
        stat(d, x + 24 + index * (sw_ + 12), sy, sw_, sh, value, lines, color, box=box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    qy, qh = cy + 4, 106
    qw = (iw - 2 * 12) / 3
    for index, (name, title, line1, line2) in enumerate(T["questions"]):
        qx = ix + index * (qw + 12)
        d.rect(qx, qy, qw, qh, rx=10, fill="panel", stroke="purple", sw=1.2)
        width = code(d, qx + 16, qy + 30, name, 14, "purple", box=box, weight=700)
        d.text(qx + 16 + width + 10, qy + 30, title, 15, 700, "text", box=box)
        d.text(qx + 16, qy + 58, line1, 12.5, 400, "text2", box=box)
        d.text(qx + 16, qy + 80, line2, 12.5, 400, "muted", box=box)
    ty = qy + qh + 30
    d.runs(ix + 2, ty, [(T["threshold"][0], 14, 700, "text"), (T["threshold"][1], 12.5, 400, "muted", 12)], box=box)
    oy, oh, gap = ty + 14, 68, 8
    chip_w = 104
    for index, (cond, result, value, flag, color) in enumerate(T["outcomes"]):
        top = oy + index * (oh + gap)
        d.rect(ix, top, iw, oh, rx=10, fill=color + "F", fo=0.06, stroke=color, sw=1.3)
        d.rect(ix, top + 10, 4, oh - 20, rx=2, fill=color + "F")
        d.text(ix + 18, top + 28, cond, 14, 700, "text", box=box)
        d.text(ix + 18, top + 49, result, 12.5, 400, "text2", box=box)
        code_chip(d, ix + iw - 14 - chip_w, top + oh / 2 - 15, chip_w, value, box=box)
        if flag:  # the tag sits right-aligned next to the header value
            width = rw(flag, 11.5, 700) + 16
            tag(d, ix + iw - 14 - chip_w - 10 - width, top + oh / 2 - 10, flag, color, 11.5, 20, 8, box=box)
    sy = oy + len(T["outcomes"]) * (oh + gap) + 4
    sh = y + h - 16 - sy
    sw_ = (iw - 2 * 12) / 3
    for index, (value, lines, color) in enumerate(T["stats2"]):
        stat(d, ix + index * (sw_ + 12), sy, sw_, sh, value, lines, color, box=box, vsize=18)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    gap = 44
    nw = (w - 48 - 4 * gap) / 5
    ny, nh = cy + 4, 78
    for index, item in enumerate(T["path"]):
        nx = x + 24 + index * (nw + gap)
        dashed = item.get("dash")
        node(d, nx, ny, nw, nh, item["icon"], item["title"], item["sub"], stroke="purple" if dashed else "line2",
             dash="7 5" if dashed else None, box=box)
        if index:
            d.arrow([(nx - gap + 6, ny + nh / 2), (nx - 6, ny + nh / 2)], sw=1.8, r=0)
        ty = ny + nh + 30
        for kind, text in item["lines"]:
            if kind == "c":
                code(d, nx + 6, ty, text, 12.5, "purple", box=box)
            else:
                d.text(nx + 6, ty, text, 13.5, 400, "text2", box=box)
            ty += 23
        if item.get("value"):
            measured(d, nx + 6, ny + nh + 30 + 2 * 23 + 12, T["measured"], item["value"], box=box, size=12.5)
        if item.get("warn"):
            d.text(nx + 6, ny + nh + 30 + 2 * 23 + 12, item["warn"], 12.5, 700, "pink", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], SERIES_NAME, T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "1")
    s1(d, 48, 140, 1010, 596)
    s2(d, 1078, 140, 794, 596)
    s3(d, 48, 756, 1824, 288)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
