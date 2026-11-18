"""그림 1. 3부 한눈에 보기: 요청 경로와 구간별 시간, 모델 결정 순서, 두 층 우선순위, sleep, 접근 제한.

수치는 모두 원고의 표에 있는 값이다.
  구간별 시간: 표 12 (2026-11-15, 모델마다 20건의 중앙값)
  우선순위: 표 4 (2026-11-14, Gemma 4 31B, 경우마다 90초씩 1회)
  Decider 판단, sleep과 깨우기: 표 5와 그 아래 문단, 표 8과 그 아래 문단
모델 결정 순서의 기본 처리는 2026-11-17에 좁힌 뒤의 동작이다(app/bff/routing.py의 from_decider).
"""
import math

from infokit import Doc, callout, cell, dot_list, footer_note, header, rw, series_nav, tag
from p3kit import EC2, EKS, ELB, S3, SERIES, code, node, sec, stat

NW, NH = 176, 84
ROWS = [210, 338, 466]


def nx(col):
    return 72 + col * 220


# 이름: (열, 행, 아이콘, 이름, 설명, 값)
NODES = {
    "cognito": (1, 0, "service/Amazon-Cognito", "Amazon Cognito", "액세스 토큰 발급, 가입 차단", ""),
    "batch": (2, 0, "resource/Client", "배치 작업", "BFF를 거치지 않는 경로", ""),
    "nlb": (3, 0, ELB, "내부 NLB", "배치 클라이언트만 허용", ""),
    "decider": (4, 0, EC2, "Strands Decider 2B", "g6.xlarge, 판단 3종", "세 판단 139~150ms"),
    "gemma": (5, 0, EC2, "Gemma 4 31B", "vLLM, L40S 1장", "TTFT 63.2ms"),
    "user": (0, 1, "resource/User", "사용자", "로그인, SSE 수신", "엣지까지 1.8 / 1.9ms"),
    "cf": (1, 1, "service/Amazon-CloudFront", "CloudFront", "AWS WAF, /v1/* 분기", "5.0 / 5.0ms"),
    "alb": (2, 1, ELB, "내부 ALB", "VPC origin만 허용", "1.6 / 1.6ms"),
    "bff": (3, 1, EKS, "BFF 파드", "토큰 검증, 모델 결정", "0.1 / 12.8ms"),
    "gw": (4, 1, EKS, "게이트웨이", "agentgateway, EPP", "9.7 / 8.4ms"),
    "pages": (1, 2, S3, "S3 정적 페이지", "OAC로만 읽기", ""),
    "wake": (4, 2, EKS, "깨우기 API", "POST /wake만 제공", "복귀 3.66초"),
    "qwen": (5, 2, EC2, "Qwen3.8-27B", "vLLM, L40S 1장", "TTFT 147.6ms"),
}

T = dict(
    title="모델 라우팅과 요청 경로 한눈에 보기",
    sub_en="Model Routing on Amazon EKS: BFF, Gateway, Priority",
    sub_ko="BFF의 모델 결정, 게이트웨이의 풀 선택, 구간별 시간",
    s1=("요청 경로와 구간별 시간", "BFF가 본문의 model 값을 채우고 게이트웨이가 그 값으로 풀 선택"),
    s2=("BFF의 모델 결정 순서", "위에서부터 먼저 맞는 규칙, 결정은 세션에 저장"),
    s3=("두 층 우선순위의 효과", "배치 32개 부하 중 상담 TTFT p50"),
    s4=("Qwen의 sleep과 깨우기", "업무 시간 밖에는 GPU 메모리 반환"),
    s5=("경계별 접근 제한", "바깥에서 안쪽으로"),
    edge=dict(login="로그인", default="기본 경로", decide="/decide", wake="POST /wake",
              pool=("본문의 model 값으로", "모델별 풀 선택")),
    legend=[("solid", "사용자 요청 경로"), ("dashed", "로그인, 정적 페이지, 배치 경로"),
            ("value", "[orange]{주황 값}: Gemma / Qwen 구간 중앙값")],
    budget_title="사용자가 본 첫 내용까지의 시간",
    budget_note="20건 중앙값",
    # 모델, 첫 내용, 경로 합(사용자부터 게이트웨이까지), vLLM, vLLM 비중
    budget=[("Gemma 4 31B", 81.9, 18.2, 63.2, 77), ("Qwen3.8-27B", 177.5, 29.7, 147.6, 83)],
    budget_words=("첫 내용", "경로", "vLLM", "vLLM 비중"),
    insight=("첫 내용 시간의 77~83%는 vLLM", "사용자부터 게이트웨이까지 다섯 구간의 합은 18.2ms와 29.7ms"),
    budget_bullets=["Qwen의 BFF 12.8ms는 요청마다 하는 깨우기 확인 호출", "요청을 하나씩 보낸 값, vLLM 대기열 시간 0ms"],
    rules=[
        ("규칙", "주민등록번호, 카드번호 형식 발견", "Gemma, 민감 처리, Decider 생략", "pink"),
        ("업무", "x-task 헤더의 업무 종류", "배정표의 모델과 우선순위", "blue"),
        ("첨부", "업무 종류 없이 이미지 첨부", "Qwen", "blue"),
        ("판단", "Decider의 모델 선택과 개인정보 판단 신뢰도 0.6 이상", "Decider가 고른 모델", "purple"),
        ("기본", "모델 선택 신뢰도만 0.6 미만, 개인정보는 없다는 판단", "Gemma, thinking 끔, 민감 처리 없음", "green"),
        ("기본", "무응답, 2초 초과, 개인정보 판단 불확실", "Gemma, thinking 끔, 민감 처리", "orange"),
    ],
    rule_x=(86, 326),
    # 경우, p50(ms), 적는 값, 배치 429 거절, 엔진 대기 요청 수 평균, 막대 색
    cases=[
        ("우선순위 없음", 30895, "30.9초", "0건", "31.0", "orange"),
        ("게이트웨이만", 11183, "11.2초", "1,907건", "15.3", "orange"),
        ("엔진만", 190, "0.19초", "0건", "17.9", "green"),
        ("두 층 모두", 193, "0.19초", "1,988건", "9.3", "green"),
    ],
    case_head=("경우", "상담 TTFT p50, 로그 눈금", "429 거절", "엔진 대기 평균"),
    case_insight=("대기를 없앤 것은 엔진의 priority 스케줄링",
                  "게이트웨이는 배치 요청을 429로 거절해 엔진 대기열을 31.0에서 15.3으로 줄임"),
    sleep=[
        ("40,899에서 2,299MiB", "level 1 sleep 중 GPU 메모리", "yellow"),
        ("3.66초", "복귀, 깨우기 API 응답까지", "green"),
        ("4.06초", "잠든 Qwen에 보낸 요청의 첫 내용", "orange"),
        ("123초", "파드를 다시 띄우는 웜 재시작", "pink"),
    ],
    limits=[
        "AWS WAF: IP 하나가 5분에 300회를 넘으면 차단",
        "Cognito: 액세스 토큰 없는 /v1 요청은 BFF에서 401",
        "내부 ALB: CloudFront VPC origin 보안 그룹만 허용",
        "게이트웨이 NLB: 배치 클라이언트 보안 그룹만 허용",
        "Qwen 파드, 깨우기 API: NetworkPolicy로 정해진 파드만 허용",
    ],
    note=("서울 리전 측정. 구간별 시간은 2026-11-15에 요청을 하나씩 모델마다 20건 보낸 중앙값이라 합이 첫 내용과 정확히 일치하지 않음. "
          "우선순위는 2026-11-14 Gemma 4 31B, 경우마다 90초씩 1회. sleep은 2026-11-14 같은 파드에서 5회, 4.06초는 2026-11-15 1회"),
)


def rect_of(name):
    col, row = NODES[name][:2]
    return nx(col), ROWS[row], NW, NH


def flow_map(d, box):
    """요청 경로. 가운데 줄이 사용자 요청이 지나는 순서이고 위아래 줄은 곁가지다."""
    mid = {name: (rect_of(name)[0] + NW / 2, rect_of(name)[1] + NH / 2) for name in NODES}
    left = {name: rect_of(name)[0] for name in NODES}
    right = {name: rect_of(name)[0] + NW for name in NODES}
    top = {name: rect_of(name)[1] for name in NODES}
    bottom = {name: rect_of(name)[1] + NH for name in NODES}
    e = T["edge"]

    # 가운데 줄: 사용자, CloudFront, 내부 ALB, BFF, 게이트웨이
    chain = ["user", "cf", "alb", "bff", "gw"]
    for a, b in zip(chain, chain[1:]):
        d.arrow([(right[a], mid[a][1]), (left[b], mid[b][1])])
    # 게이트웨이에서 두 모델의 풀로
    trunk = right["gw"] + 22
    d.arrow([(right["gw"], mid["gw"][1]), (trunk, mid["gw"][1]), (trunk, mid["gemma"][1]), (left["gemma"], mid["gemma"][1])])
    d.arrow([(trunk, mid["gw"][1]), (trunk, top["qwen"] + 28), (left["qwen"], top["qwen"] + 28)])
    for i, line in enumerate(e["pool"]):
        d.text(trunk + 12, mid["gw"][1] - 4 + i * 17, line, 12, 400, "muted", box=box)
    # 게이트웨이의 /decide 경로
    d.arrow([(mid["gw"][0], top["gw"]), (mid["decider"][0], bottom["decider"])])
    code(d, mid["gw"][0] + 10, top["gw"] - 17, e["decide"], 11.5, "muted", box=box)
    # 배치 작업은 내부 NLB로 게이트웨이에 들어온다
    d.arrow([(right["batch"], mid["batch"][1]), (left["nlb"], mid["nlb"][1])], dash="5 5")
    lane = bottom["nlb"] + 22
    d.arrow([(mid["nlb"][0], bottom["nlb"]), (mid["nlb"][0], lane), (left["gw"] + 40, lane), (left["gw"] + 40, top["gw"])],
            dash="5 5", r=8)
    # 로그인과 정적 페이지
    d.arrow([(mid["user"][0], top["user"]), (mid["user"][0], mid["cognito"][1]), (left["cognito"], mid["cognito"][1])],
            dash="5 5")
    d.text(mid["user"][0] + 40, mid["cognito"][1] - 8, e["login"], 12, 400, "muted", box=box)
    d.arrow([(mid["cf"][0], bottom["cf"]), (mid["pages"][0], top["pages"])], dash="5 5")
    d.text(mid["cf"][0] + 10, bottom["cf"] + 26, e["default"], 12, 400, "muted", box=box)
    # Qwen 요청마다 깨우기 API를 먼저 호출
    d.arrow([(mid["bff"][0], bottom["bff"]), (mid["bff"][0], mid["wake"][1]), (left["wake"], mid["wake"][1])])
    code(d, mid["bff"][0] + 12, mid["wake"][1] - 9, e["wake"], 11.5, "muted", box=box)
    d.arrow([(right["wake"], top["wake"] + 58), (left["qwen"], top["qwen"] + 58)])

    for name, (_, _, icon, title, sub, value) in NODES.items():
        x, y, w, h = rect_of(name)
        model = name in ("gemma", "qwen")
        node(d, x, y, w, h, icon, title, sub, value, stroke="purple" if model else "line2", sw=1.5 if model else 1.3)

    # 범례
    lx, ly = nx(2), ROWS[2] + 20
    for i, (kind, text) in enumerate(T["legend"]):
        y = ly + i * 22
        if kind == "value":
            d.text(lx, y + 4, text, 12, 400, "muted", box=box)
            continue
        d.line(lx, y, lx + 34, y, stroke="arrow", sw=1.6, dash="5 5" if kind == "dashed" else None)
        d.text(lx + 44, y + 4, text, 12, 400, "muted", box=box)


def budget(d, x, y, w, box):
    """첫 내용까지의 시간을 경로와 vLLM으로 나눈 막대. 두 모델에 같은 눈금을 쓴다."""
    first, path, vllm, share = T["budget_words"]
    d.text(x, y + 16, T["budget_title"], 15, 700, "text", box=box)
    d.text(x + w, y + 16, T["budget_note"], 12, 400, "muted", "end", box=box)
    scale = 400 / max(total for _, total, *_ in T["budget"])
    yy = y + 46
    for name, total, path_ms, vllm_ms, pct in T["budget"]:
        d.text(x, yy, name, 13, 700, "text", box=box)
        d.text(x + w, yy, f"{first} {total}ms", 14, 700, "orange", "end", box=box)
        pw, vw = path_ms * scale, vllm_ms * scale
        d.rect(x, yy + 8, pw, 26, rx=4, fill="purpleF")
        d.rect(x + pw + 2, yy + 8, vw - 2, 26, rx=4, fill="blueF")
        d.text(x + pw + 2 + (vw - 2) / 2, yy + 26, f"{vllm} {vllm_ms}ms", 12, 700, "badgetext", "middle", box=box)
        d.text(x, yy + 52, f"{path} {path_ms}ms", 12, 700, "purple", box=box)
        d.text(x + max(pw + 2, rw(f"{path} {path_ms}ms", 12, 700) + 16), yy + 52, f"{share} {pct}%", 12, 700, "blue", box=box)
        yy += 84
    bottom = callout(d, x, yy - 16, w, *T["insight"], box=box)
    dot_list(d, x, bottom + 26, w, T["budget_bullets"], 13, 19, 6, dot="muted", box=box)


def s1(d, x, y, w, h):
    sec(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    flow_map(d, box)
    d.line(1364, y + 70, 1364, y + h - 18, stroke="cardline", sw=1)
    budget(d, 1380, y + 66, 468, box)


def s2(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    rh = (y + h - cy - 12) / len(T["rules"])
    when_x, then_x = T["rule_x"]
    for index, (name, when, then, color) in enumerate(T["rules"]):
        mid = cy + index * rh + rh / 2
        d.text(ix + 8, mid + 5, str(index + 1), 14, 700, "faint", "middle", box=box)
        tag(d, ix + 24, mid - 12, name, color, 13, 24, 10, box=box)
        cell(d, ix + when_x, mid, then_x - when_x - 14, when, 14, 19, 400, "text2", box)
        cell(d, ix + then_x, mid, iw - then_x, then, 14, 19, 700, "text", box)
        if index:
            d.line(ix, mid - rh / 2, ix + iw, mid - rh / 2, stroke="cardline", sw=1)


def s3(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    bar_x, bar_w = ix + 112, 190
    rejected_x, waiting_x = ix + 432, ix + iw
    head = T["case_head"]
    d.text(ix, cy + 14, head[0], 12, 400, "muted", box=box)
    d.text(bar_x, cy + 14, head[1], 12, 400, "muted", box=box)
    d.text(rejected_x, cy + 14, head[2], 12, 400, "muted", "end", box=box)
    d.text(waiting_x, cy + 14, head[3], 12, 400, "muted", "end", box=box)
    top = cy + 28
    insight_h = 58
    rh = (y + h - 18 - insight_h - 14 - top) / len(T["cases"])
    low, high = 2.0, math.log10(40000)  # 100ms에서 40초까지
    for index, (name, ms, shown, rejected, waiting, color) in enumerate(T["cases"]):
        mid = top + index * rh + rh / 2
        d.line(ix, mid - rh / 2, ix + iw, mid - rh / 2, stroke="cardline", sw=1)
        d.text(ix, mid + 5, name, 14, 700, "text", box=box)
        bw = (math.log10(ms) - low) / (high - low) * bar_w
        d.rect(bar_x, mid - 11, bw, 22, rx=4, fill=color + "F")
        d.text(bar_x + bw + 10, mid + 6, shown, 16, 700, color, box=box)
        d.text(rejected_x, mid + 5, rejected, 14, 400, "pink" if rejected != "0건" else "muted", "end", box=box)
        d.text(waiting_x, mid + 5, waiting, 14, 400, "text2", "end", box=box)
    callout(d, ix, y + h - 18 - insight_h, iw, *T["case_insight"], color="green", box=box)


def s4(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 4, *T["s4"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 10
    tw_, th = (iw - gap) / 2, (y + h - 16 - cy - gap) / 2
    for index, (value, label, color) in enumerate(T["sleep"]):
        stat(d, ix + (index % 2) * (tw_ + gap), cy + (index // 2) * (th + gap), tw_, th, value, label, color,
             box=box, vsize=17, lsize=12)


def s5(d, x, y, w, h):
    cy = sec(d, x, y, w, h, 5, *T["s5"])
    box = (x, y, w, h)
    dot_list(d, x + 24, cy + 10, w - 48, T["limits"], 14, 20, 6, dot="green", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "3")
    s1(d, 48, 140, 1824, 428)
    s2(d, 48, 588, 600, 456)
    s3(d, 668, 588, 580, 456)
    s4(d, 1268, 588, 604, 218)
    s5(d, 1268, 826, 604, 218)
    footer_note(d, 1872, 1064, T["note"], size=12)
    return d.svg()
