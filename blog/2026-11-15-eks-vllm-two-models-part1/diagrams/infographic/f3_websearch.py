"""Part 1, figure 3: how the web search tool runs inside one request.

The left column says when the BFF attaches the tool (the x-bff-search response header) and what was measured.
The right side is the order of events between the browser, the BFF, the model and Amazon Bedrock AgentCore
Web Search. Facts: docs/10-web-search.md, app/bff/bff.py, app/bff/websearch.py.
"""
from infokit import Doc, callout, footer_note, header, rw, section, series_nav, tag

from common import SERIES, SERIES_NAME, pick
from p1kit import CLIENT, EC2, EKS, agentcore, code_chip, node, stat

GEMMA, QWEN = "Gemma 4 31B", "Qwen3.8-27B"

T_KO = dict(
    title="Web Search 도구의 실행 순서",
    sub_ko="검색은 AgentCore Web Search, 추론은 " + GEMMA + "와 " + QWEN,
    s1=("도구를 넣는 조건", "응답 헤더 x-bff-search의 값"),
    conditions=[
        ("on", "도구와 지시문을 추가", "x-web-search: on을 보낸 요청", "green"),
        ("off", "추가하지 않음", "헤더 없음, 성능 평가, 요청이 tools를 지정", "muted"),
        ("sensitive", "민감 정보 요청은 제외", "검색어가 서울 리전 밖으로 나가지 않게 함", "pink"),
        ("fallback", "기본값 요청의 일부는 제외", "개인정보 없음 판단을 얻지 못한 요청", "pink"),
        ("disabled", "설정이 없는 환경", "검색할 리전을 지정하지 않은 배포", "muted"),
    ],
    s2=("한 요청 안에서 일어나는 순서", "모델이 도구를 호출하면 BFF가 실행하고 추론을 다시 요청"),
    lanes=[("브라우저", "확인용 페이지"), ("BFF", "도구 실행과 출처 번호 관리"), ("모델", GEMMA + ", " + QWEN),
           ("AgentCore Web Search", "us-east-1")],
    steps=[
        (0, 1, "질문과 x-web-search: on 헤더", None, "arrow"),
        (1, 2, "web_search 도구 정의와 지시문 추가", "지시문에 오늘 날짜와 출처 번호 규칙", "arrow"),
        (2, 1, "tool_calls로 web_search(query) 호출", "검색 여부와 검색어는 모델이 결정", "purple"),
        (1, 3, "InvokeWebSearch 호출", "Pod Identity 역할의 권한, 민감한 검색어는 차단", "purple"),
        (3, 1, "검색 결과", "주소가 없는 결과는 버림", "purple"),
        (1, 2, "결과 5건과 출처 번호, 본문은 1,200자까지", "Prefill부터 다시 추론", "purple"),
        (2, 1, "번호 [1], [2]를 넣은 답변", "스트리밍 Chunk", "arrow"),
        (1, 0, "답변과 출처 목록", "출처는 SSE 주석 줄로 전달, 화면이 링크로 표시", "arrow"),
    ],
    loop="도구 호출 차례는 최대 3번, 세 번째 뒤에는 tool_choice: none",
    call=("추론은 두 모델, 검색만 AgentCore Web Search",
          "모델이 번호를 빠뜨려도 출처 목록은 화면이 항상 표시, BFF 로그에는 검색어 대신 길이와 결과 수, 걸린 시간만 기록"),
    s3=("측정값과 한도", "검색 1회 기준"),
    stats=[
        ("481~1,065ms", ["검색 1회, 작업 장비에서", "us-east-1을 6회 호출"], "orange"),
        ("547.9, 594.9ms", ["검색 1회, BFF 파드에서", "2026-11-17의 요청 2건"], "orange"),
        ("2,606토큰", [GEMMA + "의 입력", "검색 1회의 결과 5건 포함"], "blue"),
        ("4,328토큰", [QWEN + "의 입력", "검색 2회의 결과 10건 포함"], "blue"),
        ("5건, 1,200자", ["모델에 넘기는 결과 수와", "결과 1건의 본문 길이"], "purple"),
        ("1,000건에 7달러", ["쿼리 요금", "기본 할당량은 초당 10건"], "orange"),
    ],
    note="서울 리전의 BFF가 us-east-1의 API를 호출. 입력 토큰은 2026-11-15에 같은 흐름을 직접 실행한 값, 요금은 같은 날 확인한 공개 단가",
)

T_EN = dict(
    title="How the Web Search Tool Runs",
    sub_ko="AgentCore Web Search searches, " + GEMMA + " and " + QWEN + " do the inference",
    s1=("When the tool is attached", "The x-bff-search header"),
    conditions=[
        ("on", "Tool and instruction added", "The request sent x-web-search: on", "green"),
        ("off", "Not added", "No header, a benchmark request, or its own tools", "muted"),
        ("sensitive", "Sensitive requests are left out", "Keeps search queries inside the Seoul Region", "pink"),
        ("fallback", "Some default requests are left out", "No judgment that personal data is absent", "pink"),
        ("disabled", "Not configured", "A deployment with no search Region set", "muted"),
    ],
    s2=("What happens inside one request", "The model calls the tool, the BFF runs it and asks for inference again"),
    lanes=[("Browser", "Check page"), ("BFF", "Runs tools, numbers sources"), ("Model", GEMMA + ", " + QWEN),
           ("AgentCore Web Search", "us-east-1")],
    steps=[
        (0, 1, "Question with the x-web-search: on header", None, "arrow"),
        (1, 2, "Adds the web_search tool and an instruction", "Today's date and the source numbering rule", "arrow"),
        (2, 1, "tool_calls: web_search(query)", "The model decides whether and what to search", "purple"),
        (1, 3, "Calls InvokeWebSearch", "Pod Identity role, sensitive queries are blocked", "purple"),
        (3, 1, "Search results", "Results without a URL are dropped", "purple"),
        (1, 2, "5 results with source numbers, up to 1,200 characters each", "Inference starts again from prefill", "purple"),
        (2, 1, "Answer with [1], [2] numbers", "Streaming chunks", "arrow"),
        (1, 0, "Answer and the source list", "Sources arrive as SSE comment lines, the page links them", "arrow"),
    ],
    loop="At most 3 tool rounds, then tool_choice: none",
    call=("The two models infer, AgentCore Web Search only searches",
          "The page always shows the source list even when the model omits a number. "
          "BFF logs keep the query length, result count and time, not the query"),
    s3=("Measured values and limits", "Per search"),
    stats=[
        ("481~1,065 ms", ["One search from the work machine", "6 calls to us-east-1"], "orange"),
        ("547.9, 594.9 ms", ["One search from a BFF pod", "2 requests on 2026-11-17"], "orange"),
        ("2,606 tokens", [GEMMA + " input", "After 1 search, 5 results"], "blue"),
        ("4,328 tokens", [QWEN + " input", "After 2 searches, 10 results"], "blue"),
        ("5 results, 1,200 chars", ["Results passed to the model", "and text length per result"], "purple"),
        ("7 USD per 1,000", ["Query price", "Default quota 10 per second"], "orange"),
    ],
    note="The BFF in the Seoul Region calls the API in us-east-1. Input tokens: the same flow run by hand on 2026-11-15. "
         "Price: public rate checked the same day",
)

T = pick(T_KO, T_EN)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    top0, gap = cy + 2, 6
    rh = (y + h - 18 - top0 - 4 * gap) / 5
    chip_w = 112
    for index, (value, line1, line2, color) in enumerate(T["conditions"]):
        top = top0 + index * (rh + gap)
        d.rect(x + 24, top, w - 48, rh, rx=10, fill="panel", stroke="cardline", sw=1.2)
        d.rect(x + 24, top + 10, 4, rh - 20, rx=2, fill=color if color == "muted" else color + "F")
        code_chip(d, x + 40, top + rh / 2 - 15, chip_w, value, box=box)
        d.text(x + 40 + chip_w + 14, top + rh / 2 - 4, line1, 14, 700, "text", box=box)
        d.text(x + 40 + chip_w + 14, top + rh / 2 + 16, line2, 12.5, 400, "muted", box=box)


def label(d, x, y, text, size, weight, color, anchor, box):
    """Text on a card-colored strip, so the dashed lifelines do not run through the letters."""
    width = rw(text, size, weight)
    left = x if anchor == "start" else x - width
    d.rect(left - 6, y - size, width + 12, size + 6, fill="card")
    d.text(x, y, text, size, weight, color, anchor, box=box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    step = (w - 60) / 4
    centers = [x + 30 + step / 2 + index * step for index in range(4)]
    icons = [CLIENT, EKS, EC2, agentcore(d)]
    ny, nh, nw = cy + 6, 64, 244
    call_h = 58
    call_y = y + h - 18 - call_h
    line_end = call_y - 16
    for index, (cx, (name, sub)) in enumerate(zip(centers, T["lanes"])):
        d.line(cx, ny + nh + 4, cx, line_end, stroke="line2", sw=1.3, dash="5 6")
        node(d, cx - nw / 2, ny, nw, nh, icons[index], name, sub, box=box)
    first = ny + nh + 52
    gap = (line_end - 30 - first) / (len(T["steps"]) - 1)
    ys = [first + index * gap for index in range(len(T["steps"]))]
    # the tool loop: steps 3 to 6
    fx, fw = centers[1] - 150, centers[3] + 150 - (centers[1] - 150)
    fy, fh = ys[2] - 46, ys[5] + 34 - (ys[2] - 46)
    d.rect(fx, fy, fw, fh, rx=12, fill="none", stroke="purple", sw=1.3, dash="7 5")
    loop_w = rw(T["loop"], 12, 700) + 20
    d.rect(fx + fw - 16 - loop_w, fy - 12, loop_w, 24, rx=12, fill="card")
    tag(d, fx + fw - 16 - loop_w, fy - 12, T["loop"], "purple", 12, 24, 10, box=box)
    for index, (a, b, text, sub, color) in enumerate(T["steps"]):
        sy = ys[index]
        ax, bx = centers[a], centers[b]
        direction = 1 if bx > ax else -1
        d.arrow([(ax + direction * 16, sy), (bx - direction * 5, sy)], color=color, sw=2.0, r=0)
        # the texts start next to the sender, so a long one runs past the receiver instead of over the badge
        anchor = "start" if direction > 0 else "end"
        label(d, ax + direction * 24, sy - 12, text, 13.5, 700, "text", anchor, box)
        if sub:
            label(d, ax + direction * 24, sy + 21, sub, 12, 400, "muted", anchor, box)
        d.circle(ax, sy, 13, fill="badge")
        d.text(ax, sy + 5.2, str(index + 1), 14, 700, "badgetext", "middle")
    callout(d, x + 24, call_y, w - 48, T["call"][0], T["call"][1], box=box)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    top0, gap = cy + 4, 10
    sw_ = (w - 48 - 12) / 2
    sh = (y + h - 18 - top0 - 2 * gap) / 3
    for index, (value, lines, color) in enumerate(T["stats"]):
        stat(d, x + 24 + (index % 2) * (sw_ + 12), top0 + (index // 2) * (sh + gap), sw_, sh, value, lines, color,
             box=box, vsize=18)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], SERIES_NAME, T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, "1")
    s1(d, 48, 140, 560, 452)
    s3(d, 48, 612, 560, 432)
    s2(d, 628, 140, 1244, 904)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
