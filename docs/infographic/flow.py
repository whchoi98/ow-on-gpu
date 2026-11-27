"""요청 경로와 기동 흐름 인포그래픽. aws-infographic 스킬의 infokit으로 그린다.

  landscape(theme)  16:9 인포그래픽 한 장 (buildkit이 SVG와 PNG로 만든다)
  live_map(theme)   웹 화면(app/web)의 흐름 그림. 같은 구조도에 요소마다 id를 붙이고 값 자리를 비워 둔다
  use(lang)         그릴 언어를 고른다("ko" 또는 "en"). 구조와 좌표는 같고 글만 바뀐다. 영어판은 flow_en.py가 만든다

구조도는 열과 행의 격자로 한 번만 정의한다. 왼쪽 여섯 열이 요청 경로, 일곱째 열이 GPU 노드,
오른쪽 두 열이 모델과 이미지를 대는 쪽이다. 선의 끝점은 그릴 때의 노드 크기로 계산하므로
인포그래픽(늘려 그림)과 웹 화면(그대로 그림)이 같은 정의를 쓴다.

웹 화면이 쓰는 id
  노드  n-<이름>  class fnode   값 자리 v-<이름>  class fnode__value
  틀    n-gpu     class fzone   (GPU 노드. Gemma, compile 캐시, Qwen을 감싼다)
  선    e-<출발>-<도착>  class fedge
  배지  class fbadge, data-step="0".."5"  (아래 흐름 띠의 단계 번호)

수치는 이 환경에서 잰 값이다. Decider 판단만 2026-11-24(v2 12B, g6e.xlarge)의 값이고 나머지는 2026-11-14와 2026-11-15의 값이다.
  구간별 시간과 기동 구간: docs/08-results.md 1절, 2절
  모델 적재: results/2026-11-14-model-sync/summary.jsonl
  Decider 판단: docs/05-decider.md (BFF 파드에서 ask_decider를 부른 20건의 범위 143.8~159.9ms)
  깨우기: docs/07-bff.md
  웹 검색: docs/10-web-search.md (작업 장비에서 us-east-1을 6회 부른 시간. 배포 뒤 BFF가 잰 값은 docs/10-web-search.md)
"""
from infokit import Doc, F, cell, dot_list, footer_note, header, poly_d, rw, section, tag

NODE_W, NODE_H = 136, 84
COLS = [82, 250, 418, 586, 754, 922, 1116, 1328, 1500]
ROWS = [134, 277, 420]
MAP_W, MAP_H = 1582, 500

# GPU 노드 틀과 Karpenter 막대의 치수(노드 배율 k를 곱해 쓴다)
ZONE_PAD_X, ZONE_PAD_TOP, ZONE_PAD_BOTTOM = 16, 26, 12
BAR_H, BAR_GAP = 40, 20
LANE_GAP = 14  # 틀 아래로 지표 선이 지나가는 거리

ELB = "service/Elastic-Load-Balancing"
EKS = "service/Amazon-Elastic-Kubernetes-Service"
EC2 = "service/Amazon-EC2"
S3 = "service/Amazon-Simple-Storage-Service"

# id: (열, 행, 아이콘, 이름, 설명, 인포그래픽에 적는 값)
# 4열 1행은 비어 있다. BFF가 게이트웨이의 Service를 직접 부르게 되면서(2026-11-15) 그 자리의 내부 NLB를 뺐고,
# 웹 화면이 같은 격자를 쓰므로 다른 노드의 자리는 옮기지 않았다.
NODES = {
    "user": (0, 1, "resource/Client", "브라우저", "로그인, SSE 수신", "첫 내용 81.9ms"),
    "cf": (1, 1, "service/Amazon-CloudFront", "CloudFront", "WAF, IP당 5분 300회", "5.0ms"),
    "alb": (2, 1, ELB, "내부 ALB", "CloudFront만 허용", "1.6ms"),
    "bff": (3, 1, EKS, "BFF", "토큰 검증, 모델 결정", "판단 0.1ms"),
    "gw": (5, 1, EKS, "게이트웨이", "agentgateway, EPP", "9.7ms"),
    "gemma": (6, 0, EC2, "Gemma 4 31B", "L40S 48GB, FP8", "TTFT 63.2ms"),
    "cache": (6, 1, "resource/Disk", "compile 캐시", "initContainer, hostPath", "S3 복원 3.3초"),
    "qwen": (6, 2, EC2, "Qwen3.8-27B", "L40S 48GB, FP8", "TTFT 147.6ms"),
    "cognito": (2, 0, "service/Amazon-Cognito", "Cognito", "액세스 토큰 발급", "토큰 유효 60분"),
    "search": (4, 0, "agentcore", "Web Search", "AgentCore, us-east-1", "검색 481~1,065ms"),
    "decider": (5, 0, EC2, "Decider 12B", "g6e.xlarge, 판단 3종", "판단 144~160ms"),
    "pages": (1, 2, S3, "S3 페이지", "OAC로만 읽기", ""),
    "wake": (4, 2, EKS, "깨우기 API", "NetworkPolicy로 제한", "깨우기 3,662ms"),
    "registry": (7, 0, "category/Containers", "Image registry", "Docker Hub, v0.33.0", "이미지 9.1GiB"),
    "s3": (7, 1, S3, "S3 모델 버킷", "가중치, compile 캐시", "4종 69.8GiB"),
    "identity": (7, 2, "service/AWS-Identity-and-Access-Management", "Pod Identity", "서비스 계정별 S3 역할", ""),
    "hf": (8, 0, "resource/Internet", "Hugging Face", "모델 저장소 원본", ""),
    "sync": (8, 1, EKS, "모델 적재 Job", "model-sync, s5cmd", "491초, 1회"),
    "amp": (8, 2, "service/Amazon-Managed-Service-for-Prometheus", "AMP", "Prometheus agent 수집", "수집 대상 8개"),
}

# 영어판의 이름, 설명, 값. 열과 행, 아이콘은 NODES와 같다.
NODES_EN_TEXT = {
    "user": ("Browser", "Sign-in, SSE stream", "First content 81.9ms"),
    "cf": ("CloudFront", "WAF, 300 req / 5 min", "5.0ms"),
    "alb": ("Internal ALB", "CloudFront only", "1.6ms"),
    "bff": ("BFF", "Token check, routing", "Decision 0.1ms"),
    "gw": ("Gateway", "agentgateway, EPP", "9.7ms"),
    "gemma": ("Gemma 4 31B", "L40S 48GB, FP8", "TTFT 63.2ms"),
    "cache": ("Compile cache", "initContainer, hostPath", "S3 restore 3.3s"),
    "qwen": ("Qwen3.8-27B", "L40S 48GB, FP8", "TTFT 147.6ms"),
    "cognito": ("Cognito", "Issues access tokens", "Token valid 60 min"),
    "search": ("Web Search", "AgentCore, us-east-1", "Search 481~1,065ms"),
    "decider": ("Decider 12B", "g6e.xlarge, 3 outputs", "Decision 144~160ms"),
    "pages": ("S3 pages", "Read via OAC only", ""),
    "wake": ("Wake API", "NetworkPolicy allowlist", "Wake 3,662ms"),
    "registry": ("Image registry", "Docker Hub, v0.33.0", "Image 9.1GiB"),
    "s3": ("Model bucket", "Weights and caches", "4 models 69.8GiB"),
    "identity": ("Pod Identity", "S3 role per SA", ""),
    "hf": ("Hugging Face", "Source model repos", ""),
    "sync": ("Model sync Job", "model-sync, s5cmd", "491s, once"),
    "amp": ("AMP", "Prometheus agent", "8 scrape targets"),
}
NODES_EN = {name: (*NODES[name][:3], *NODES_EN_TEXT[name]) for name in NODES}

SERIES = None
T = dict(
    title="요청 경로와 구간별 시간",
    sub_en="Request Path and Startup Flow on ow-on-gpu",
    sub_ko="브라우저에서 GPU까지의 경로, 모델과 이미지 공급, 측정값",
    s1=("서빙 구조와 기동 흐름", "실선은 요청과 데이터, 점선은 로그인, 권한, 지표, 번호는 아래 흐름의 단계"),
    s2=("모델 결정 순서", "위에서부터 먼저 맞는 규칙 적용"),
    s3=("구간별 측정값", "Gemma / Qwen, 20건 중앙값"),
    s4=("경계별 접근 제한", "바깥에서 안쪽으로 다섯 겹과 웹 검색"),
    zone="GPU 노드 g6e.4xlarge",
    # 구역 이름, 첫 노드, 마지막 노드
    captions=[("요청 경로, 5번", "user", "decider"), ("모델과 이미지 공급, 0~4번", "registry", "hf")],
    # 선에 붙이는 말. jwks_dx는 "공개 키" 글자를 세로선 왼쪽으로 옮기는 거리(글자 폭에 맞춘다)
    edge=dict(login="로그인", jwks="공개 키", s3="S3 권한", metrics="지표 수집", direct="Service 직접 호출"),
    jwks_dx=52,
    karpenter=("Karpenter NodePool", "gemma-od, qwen-od"),
    # BFF와 Web Search 사이: 선 위아래의 짧은 말과, 위쪽 띠에 적는 한 줄
    search=("도구 호출", "결과 반환",
            "웹 검색을 켠 요청: 모델이 web_search 호출, BFF가 검색, 결과에 번호를 붙여 다시 추론 요청"),
    # 번호, 이름, 값, 색
    steps=[
        ("0", "모델 적재", "4종 69.8GiB, 491초, 1회", "green"),
        ("1", "노드 프로비저닝", "Karpenter, 55.0~71.0초", "orange"),
        ("2", "이미지 pull", "111.1초에서 71.0초", "orange"),
        ("3", "가중치 로드", "59.6초에서 19.2초", "orange"),
        ("4", "엔진 초기화", "95.5초에서 23.7초", "orange"),
        ("5", "추론 요청", "첫 내용 81.9ms, 177.5ms", "purple"),
    ],
    rules=[
        ("규칙", "주민등록번호, 카드번호 형식 발견", "Gemma 고정, Decider 생략", "pink"),
        ("업무", "x-task 헤더의 업무 종류", "배정표의 모델과 우선순위", "blue"),
        ("첨부", "업무 종류 없이 이미지 첨부", "Qwen", "blue"),
        ("판단", "Decider 신뢰도 0.6 이상", "Decider가 고른 모델", "purple"),
        ("기본", "Decider 무응답 또는 낮은 신뢰도", "Gemma, thinking 끔, 민감 처리", "orange"),
    ],
    # 규칙 표에서 조건과 결과가 시작하는 x(이름표 폭에 맞춘다)
    rule_x=(86, 348),
    total="사용자가 본 첫 내용",  # 구간 표에서 굵게 적는 줄(위 여섯 구간을 더한 값)
    measures=[
        ("사용자와 엣지 사이", "1.8ms / 1.9ms", "응답 헤더 도착 기준"),
        ("CloudFront", "5.0ms / 5.0ms", "Server-Timing 헤더"),
        ("내부 ALB", "1.6ms / 1.6ms", "접근 로그"),
        ("BFF", "0.1ms / 12.8ms", "Qwen은 깨우기 확인 포함"),
        ("게이트웨이", "9.7ms / 8.4ms", "agentgateway, EPP"),
        ("vLLM TTFT", "63.2ms / 147.6ms", "vLLM 지표"),
        ("사용자가 본 첫 내용", "81.9ms / 177.5ms", "클라이언트 측정"),
        ("웹 검색 1회", "481~1,065ms", "켠 요청만, 작업 장비에서 6회"),
    ],
    limits=[
        "AWS WAF: IP당 5분 300회 초과 시 403, 약 5분 뒤 해제",
        "Cognito: 가입 차단, 액세스 토큰 없는 /v1 요청은 401",
        "내부 ALB: CloudFront VPC origin 보안 그룹만 허용",
        "게이트웨이 NLB: 배치 클라이언트 보안 그룹만 허용",
        "Qwen 파드: NetworkPolicy로 게이트웨이, EPP, 깨우기 API만 허용",
        "웹 검색: BFF 파드 역할만 InvokeWebSearch 허용, 민감 요청에는 도구 제외",
    ],
    note=("서울 리전 측정(0~4번 2026-11-14, 5번과 구간 표 2026-11-15, Decider 판단 2026-11-24), g6e.4xlarge 2대와 g6e.xlarge 1대, 1~4번은 Gemma 콜드 스타트의 기준 구성과 최적화 구성, "
          "5번은 Gemma와 Qwen, 웹 검색 시간은 작업 장비(서울)에서 us-east-1 호출 6회의 범위"),
)

T_EN = dict(
    title="Request Path and Segment Latency",
    sub_en="ow-on-gpu: Multi-Model vLLM Serving on Amazon EKS",
    sub_ko="Path from browser to GPU, model and image supply, measured values",
    s1=("Serving architecture and startup flow",
        "Solid: requests and data, dashed: sign-in, permissions, metrics, badges: steps in the strip below"),
    s2=("Model decision order", "First matching rule from the top"),
    s3=("Segment measurements", "Gemma / Qwen, median of 20"),
    s4=("Access limits", "Five layers outside in, plus web search"),
    zone="GPU node g6e.4xlarge",
    # 번호는 그림의 번호 배지를 가리킨다. "step"이라고 쓰면 API 호출 보기의 단계 번호와 헷갈린다.
    captions=[("Request path, badge 5", "user", "decider"), ("Model and image supply, badges 0~4", "registry", "hf")],
    edge=dict(login="Sign-in", jwks="Public keys", s3="S3 access", metrics="Metrics", direct="Direct Service call"),
    jwks_dx=70,
    karpenter=("Karpenter NodePool", "gemma-od, qwen-od"),
    search=("Tool call", "Results",
            "Web search on: model calls web_search, BFF searches, numbers results, re-infers"),
    steps=[
        ("0", "Model sync", "4 models 69.8GiB, 491s, once", "green"),
        ("1", "Node provisioning", "Karpenter, 55.0~71.0s", "orange"),
        ("2", "Image pull", "111.1s to 71.0s", "orange"),
        ("3", "Weight load", "59.6s to 19.2s", "orange"),
        ("4", "Engine init", "95.5s to 23.7s", "orange"),
        ("5", "Inference request", "First content 81.9ms, 177.5ms", "purple"),
    ],
    rules=[
        ("Rule", "RRN or card number format found", "Gemma only, Decider skipped", "pink"),
        ("Task", "Task type in the x-task header", "Model, priority from the table", "blue"),
        ("Image", "Image attached, no task type", "Qwen", "blue"),
        ("Decider", "Decider confidence 0.6 or higher", "Model the Decider picked", "purple"),
        ("Default", "Decider silent or low confidence", "Gemma, thinking off, sensitive", "orange"),
    ],
    rule_x=(108, 362),
    total="First content seen",
    measures=[
        ("User to edge", "1.8ms / 1.9ms", "Until response headers arrive"),
        ("CloudFront", "5.0ms / 5.0ms", "Server-Timing header"),
        ("Internal ALB", "1.6ms / 1.6ms", "Access log"),
        ("BFF", "0.1ms / 12.8ms", "Qwen includes the wake check"),
        ("Gateway", "9.7ms / 8.4ms", "agentgateway, EPP"),
        ("vLLM TTFT", "63.2ms / 147.6ms", "vLLM metrics"),
        ("First content seen", "81.9ms / 177.5ms", "Measured at the client"),
        ("One web search", "481~1,065ms", "Search-on requests, 6 calls"),
    ],
    limits=[
        "AWS WAF: 403 above 300 requests per 5 min per IP, lifted in about 5 min",
        "Cognito: sign-up disabled, /v1 without an access token gets 401",
        "Internal ALB: only the CloudFront VPC origin security group",
        "Gateway NLB: only the batch client security group",
        "Qwen pod: NetworkPolicy allows gateway, EPP, and wake API only",
        "Web search: BFF pod role only, no tool on sensitive requests",
    ],
    note=("Seoul Region, two g6e.4xlarge and one g6e.xlarge. Steps 0~4 measured 2026-11-14, step 5 and the segment table 2026-11-15, the Decider 2026-11-24. Steps 1~4: Gemma cold start, "
          "baseline and optimized. Step 5: Gemma and Qwen. Web search: range of 6 us-east-1 calls from the work machine (Seoul)"),
)

TEXT = {"ko": (NODES, T), "en": (NODES_EN, T_EN)}


def use(lang):
    """그릴 언어를 고른다. 구조와 좌표는 같고 글만 바뀐다."""
    global NODES, T
    NODES, T = TEXT[lang]


class Geo:
    """격자 좌표를 그릴 좌표로 바꾼다. (ox, oy)는 왼쪽 위, sx와 sy는 위치의 배율, k는 노드와 글자의 배율."""

    def __init__(self, ox, oy, sx, sy, k):
        self.ox, self.oy, self.sx, self.sy, self.k = ox, oy, sx, sy, k
        self.nw, self.nh = NODE_W * k, NODE_H * k

    def center(self, name):
        col, row = NODES[name][:2]
        return self.ox + COLS[col] * self.sx, self.oy + ROWS[row] * self.sy

    def rect(self, name):
        k = self.k
        if name == "gpu":  # Gemma, compile 캐시, Qwen을 감싸는 틀
            x, top = self.rect("gemma")[:2]
            bottom = self.rect("qwen")[1] + self.nh
            return (x - ZONE_PAD_X * k, top - ZONE_PAD_TOP * k, self.nw + 2 * ZONE_PAD_X * k,
                    bottom - top + (ZONE_PAD_TOP + ZONE_PAD_BOTTOM) * k)
        if name == "karpenter":  # 틀 위의 막대
            x, y, w, _ = self.rect("gpu")
            return (x, y - (BAR_GAP + BAR_H) * k, w, BAR_H * k)
        cx, cy = self.center(name)
        return (cx - self.nw / 2, cy - self.nh / 2, self.nw, self.nh)

    def side(self, name, where, shift=0.0):
        """테두리의 한 점. where는 left, right, top, bottom. shift는 변을 따라 옮기는 거리."""
        x, y, w, h = self.rect(name)
        s = shift * self.k
        return {"left": (x, y + h / 2 + s), "right": (x + w, y + h / 2 + s),
                "top": (x + w / 2 + s, y), "bottom": (x + w / 2 + s, y + h)}[where]

    @property
    def lane(self):
        """GPU 노드 틀 아래로 지표 선이 지나가는 높이."""
        _, y, _, h = self.rect("gpu")
        return y + h + LANE_GAP * self.k


def fit(ox, top, sx, height, k):
    """주어진 높이에 구조도가 꼭 맞도록 세로 배율과 원점을 정한다."""
    fixed = (NODE_H + ZONE_PAD_TOP + BAR_GAP + BAR_H + ZONE_PAD_BOTTOM + LANE_GAP) * k + 6
    g = Geo(ox, 0, sx, (height - fixed) / (ROWS[-1] - ROWS[0]), k)
    g.oy = top - g.rect("karpenter")[1] + 2
    return g


def via_x(start, end, x):
    return [start, (x, start[1]), (x, end[1]), end]


def via_y(start, end, y):
    return [start, (start[0], y), (end[0], y), end]


def corner_h(start, end):
    """세로로 나가서 가로로 들어간다."""
    return [start, (start[0], end[1]), end]


def middle(points, index=0):
    (x0, y0), (x1, y1) = points[index], points[index + 1]
    return (x0 + x1) / 2, (y0 + y1) / 2


def layout(g):
    """선과 배지의 좌표.

    선은 id: (경로, 점선 여부, 라벨, 라벨 위치), 배지는 (단계 번호, x, y)의 목록이다.
    라벨 자리에 목록을 주면 (글, 위치)를 여러 개 적고, 다섯째 값이 True면 양쪽에 화살촉을 단다.
    """
    s, k = g.side, g.k
    zone = g.rect("gpu")
    fork_gw = (s("gw", "right")[0] + zone[0]) / 2            # 게이트웨이와 GPU 노드 틀 사이
    fork_s3 = (zone[0] + zone[2] + s("s3", "left")[0]) / 2   # 틀과 모델 버킷 사이
    row0 = g.center("cognito")[1]
    edges = {
        # 요청 경로
        "user-cf": ([s("user", "right"), s("cf", "left")], False, None, None),
        "cf-alb": ([s("cf", "right"), s("alb", "left")], False, None, None),
        "alb-bff": ([s("alb", "right"), s("bff", "left")], False, None, None),
        # BFF는 게이트웨이의 Service를 직접 부른다. 사이의 칸(4열 1행)은 비어 있고 그 위에 라벨을 둔다.
        "bff-gw": ([s("bff", "right"), s("gw", "left")], False, T["edge"]["direct"],
                   ((s("bff", "right")[0] + s("gw", "left")[0] - rw(T["edge"]["direct"], F(11.5, k))) / 2,
                    s("bff", "right")[1] - 8 * k)),
        "gw-gemma": (via_x(s("gw", "right", -14), s("gemma", "left"), fork_gw), False, None, None),
        "gw-qwen": (via_x(s("gw", "right", 14), s("qwen", "left", -14), fork_gw), False, None, None),
        "gw-decider": ([s("gw", "top"), s("decider", "bottom")], False, "/decide",
                       (s("gw", "top")[0] + 8 * k, (s("gw", "top")[1] + s("decider", "bottom")[1]) / 2 + 4 * k)),
        "bff-wake": (corner_h(s("bff", "bottom"), s("wake", "left")), False, "POST /wake",
                     (s("bff", "bottom")[0] + 10 * k, s("wake", "left")[1] - 8 * k)),
        "wake-qwen": ([s("wake", "right", 14), s("qwen", "left", 14)], False, None, None),
        "user-cognito": (corner_h(s("user", "top"), s("cognito", "left")), True, T["edge"]["login"],
                         (s("user", "top")[0] + 10 * k, row0 - 8 * k)),
        "bff-cognito": (corner_h(s("bff", "top", -22), s("cognito", "right")), True, T["edge"]["jwks"],
                        (s("bff", "top", -22)[0] - T["jwks_dx"] * k, row0 - 8 * k)),
        # 모델이 도구를 부르면 BFF가 검색하고 결과를 받아 다시 추론을 요청한다. 왕복이라 화살촉이 양쪽에 있다.
        "bff-search": (corner_h(s("bff", "top", 22), s("search", "left")), False, [
            (T["search"][0], (s("bff", "top", 22)[0] + 10 * k, row0 - 8 * k)),
            (T["search"][1], (s("bff", "top", 22)[0] + 10 * k, row0 + 17 * k)),
            (T["search"][2], (s("bff", "left")[0], g.rect("search")[1] - 12 * k)),
        ], None, True),
        "cf-pages": ([s("cf", "bottom"), s("pages", "top")], True, None, None),
        # 모델과 이미지를 대는 쪽
        "hf-sync": ([s("hf", "bottom"), s("sync", "top")], False, None, None),
        "sync-s3": ([s("sync", "left"), s("s3", "right")], False, None, None),
        "karpenter-gpu": ([s("karpenter", "bottom"), s("gpu", "top")], False, None, None),
        "registry-gpu": ([s("registry", "left", -14), (zone[0] + zone[2], s("registry", "left", -14)[1])],
                         False, None, None),
        "s3-gemma": (via_x(s("s3", "left", -20), s("gemma", "right", 14), fork_s3), False, None, None),
        "s3-cache": ([s("s3", "left"), s("cache", "right")], False, None, None),
        "s3-qwen": (via_x(s("s3", "left", 20), s("qwen", "right", -14), fork_s3), False, None, None),
        "cache-gemma": ([s("cache", "top"), s("gemma", "bottom")], False, None, None),
        "cache-qwen": ([s("cache", "bottom"), s("qwen", "top")], False, None, None),
        "identity-s3": ([s("identity", "top"), s("s3", "bottom")], True, T["edge"]["s3"],
                        (s("identity", "top")[0] + 8 * k, (s("identity", "top")[1] + s("s3", "bottom")[1]) / 2 + 4 * k)),
        # 지표
        "gw-amp": (via_y(s("gw", "bottom"), s("amp", "bottom", -14), g.lane), True, T["edge"]["metrics"],
                   (s("gw", "bottom")[0] + 10 * k, g.lane - 6 * k)),
        "gpu-amp": (via_y(s("gpu", "bottom"), s("amp", "bottom", 14), g.lane), True, None, None),
    }
    bar = g.rect("karpenter")
    badges = [
        ("0", *middle(edges["hf-sync"][0])),
        ("1", bar[0] + 18 * k, bar[1] + bar[3] / 2),
        ("2", fork_s3, edges["registry-gpu"][0][0][1]),
        ("3", *middle(edges["s3-gemma"][0], 1)),
        ("3", *middle(edges["s3-qwen"][0], 1)),
        ("4", fork_s3, s("s3", "left")[1]),
        ("5", fork_gw, s("gw", "right")[1]),
    ]
    return edges, badges


STEP_COLORS = {step[0]: step[3] for step in T["steps"]}


def arrow_head(points, size):
    """마지막 선분 방향의 화살촉 세 점."""
    (x0, y0), (x1, y1) = points[-2], points[-1]
    length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 or 1.0
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    bx, by = x1 - ux * size, y1 - uy * size
    return [(x1, y1), (bx - uy * size * 0.5, by + ux * size * 0.5), (bx + uy * size * 0.5, by - ux * size * 0.5)]


def step_badge(d, cx, cy, num, r, size):
    color = STEP_COLORS[num]
    d.add(f'<g class="fbadge" data-step="{num}">')
    d.circle(cx, cy, r, fill=color + "F", stroke="bg", sw=2)
    d.text(cx, cy + size * 0.36, num, size, 700, "badgetext" if color == "purple" else "onwarm", "middle")
    d.add("</g>")


def flow_map(d, g, live=False, box=None, captions=None, values=None, value_color="orange", badges=True):
    """구조도를 그린다. live면 값 자리를 비워 둔다(웹 화면이 채운다).

    뒤의 네 인자는 같은 구조도에 다른 번호를 붙이는 그림(build_steps.py)이 쓴다.
    captions는 위쪽 띠의 구역 이름, values는 노드의 값 자리에 적을 글({이름: 글})과 그 색,
    badges=False면 기동 흐름의 번호(0~5)를 그리지 않는다.
    """
    k = g.k
    edges, marks = layout(g)

    # 위쪽 띠의 구역 이름. 왼쪽 여섯 열이 요청 경로, 오른쪽 두 열이 공급 쪽이다.
    bar = g.rect("karpenter")
    for text, first, last in captions or T["captions"]:
        x0, x1 = g.rect(first)[0], g.rect(last)[0] + g.rect(last)[2]
        mid = bar[1] + bar[3] / 2
        d.add('<g class="fcaption">')
        d.text(x0, mid + 4 * k, text, F(12, k), 700, "faint", box=box)
        d.line(x0 + rw(text, F(12, k), 700) + 12 * k, mid, x1, mid, stroke="line2", sw=1)
        d.add("</g>")

    zx, zy, zw, zh = g.rect("gpu")
    d.add('<g id="n-gpu" class="fzone">')
    d.rect(zx, zy, zw, zh, rx=12 * k, fill="blueF", fo=0.05, stroke="blue", sw=1.3)
    d.text(zx + 12 * k, zy + 17 * k, T["zone"], F(11.5, k), 700, "blue", box=box)
    d.add("</g>")

    for name, (points, dashed, label, label_at, *both) in edges.items():
        heads = [arrow_head(points, 9 * k)] + ([arrow_head(points[::-1], 9 * k)] if both and both[0] else [])
        line = list(points)
        for index, head in zip((-1, 0), heads):  # 선은 화살촉의 밑변에서 끝낸다
            line[index] = ((head[1][0] + head[2][0]) / 2, (head[1][1] + head[2][1]) / 2)
        d.add(f'<g id="e-{name}" class="fedge{" fedge--dashed" if dashed else ""}">')
        d.path(poly_d(line, 8 * k), stroke="arrow", sw=1.6 * k, dash=f"{5 * k:.0f} {5 * k:.0f}" if dashed else None)
        for head in heads:
            d.add('<path class="fedge__head" d="M' + " L".join(f"{x:.1f},{y:.1f}" for x, y in head)
                  + f' z" fill="{d.c("arrow")}"/>')
        for text, at in (label if isinstance(label, list) else [(label, label_at)] if label else []):
            d.text(at[0], at[1], text, F(11.5, k), 400, "muted", box=box)
        d.add("</g>")

    for name, (_, _, icon, title, sub, value) in NODES.items():
        if values is not None:
            value = values.get(name, "")
        x, y, nw, nh = g.rect(name)
        nbox = (x, y, nw, nh)
        d.add(f'<g id="n-{name}" class="fnode">')
        d.rect(x, y, nw, nh, rx=10 * k, fill="card", stroke="line2", sw=1.3)
        # AgentCore 아이콘은 세트 이름이 글리프의 색이다. 밝은 바탕에는 어두운 글리프를 쓴다.
        if icon == "agentcore":
            icon = "agentcore-dark/Agentcore" if d.theme == "light" else "agentcore-light/Agentcore"
        d.icon(icon, x + 10 * k, y + 9 * k, 26 * k)
        size = F(13, k)
        while rw(title, size, 700) > nw - 51 * k and size > 11:  # 긴 이름은 글자를 줄여 칸에 맞춘다
            size -= 0.5
        d.text(x + 43 * k, y + 27 * k, title, size, 700, "text", box=nbox)
        d.text(x + 10 * k, y + 53 * k, sub, F(11, k), 400, "muted", box=nbox)
        # 값 자리. 인포그래픽에는 측정값을, 웹 화면에는 그 요청이나 단계의 값을 넣는다.
        d.add(f'<text id="v-{name}" class="fnode__value" x="{x + 10 * k:.1f}" y="{y + 72 * k:.1f}" '
              f'font-size="{F(11.5, k)}" font-weight="800" fill="{d.c(value_color)}">{"" if live else value}</text>')
        d.add("</g>")

    bx, by, bw, bh = g.rect("karpenter")
    bbox = (bx, by, bw, bh)
    d.add('<g id="n-karpenter" class="fnode">')
    d.rect(bx, by, bw, bh, rx=10 * k, fill="card", stroke="line2", sw=1.3)
    d.text(bx + 34 * k, by + 17 * k, T["karpenter"][0], F(12, k), 700, "text", box=bbox)
    d.text(bx + 34 * k, by + 32 * k, T["karpenter"][1], F(11, k), 400, "muted", box=bbox)
    d.add("</g>")

    if badges:
        for num, cx, cy in marks:
            step_badge(d, cx, cy, num, 10 * k, F(12, k))


def strip(d, x, y, w, h, box):
    """0번에서 5번까지의 흐름 띠."""
    steps = T["steps"]
    gap = 30
    cw = (w - gap * (len(steps) - 1)) / len(steps)
    for index, (num, title, value, color) in enumerate(steps):
        cx = x + index * (cw + gap)
        d.rect(cx, y, cw, h, rx=10, fill=color + "F", fo=0.1, stroke=color, sw=1.3)
        d.circle(cx + 26, y + h / 2, 13, fill=color + "F")
        d.text(cx + 26, y + h / 2 + 5.4, num, 15, 700, "badgetext" if color == "purple" else "onwarm", "middle")
        d.text(cx + 50, y + 24, title, 15, 700, "text", box=box)
        d.text(cx + 50, y + 44, value, 13, 400, "text2", box=box)
        if index + 1 < len(steps):
            d.arrow([(cx + cw + 5, y + h / 2), (cx + cw + gap - 5, y + h / 2)], sw=1.6, r=0)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    strip_h = 56
    strip_y = y + h - 18 - strip_h
    top = cy - 8
    g = fit(x + 24, top, (w - 48) / MAP_W, strip_y - 12 - top, 1.08)
    flow_map(d, g, box=box)
    strip(d, x + 24, strip_y, w - 48, strip_h, box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    rh = (y + h - cy - 12) / len(T["rules"])
    for index, (name, when, then, color) in enumerate(T["rules"]):
        mid = cy + index * rh + rh / 2
        d.text(ix + 8, mid + 5, str(index + 1), 14, 700, "faint", "middle", box=box)
        tag(d, ix + 24, mid - 12, name, color, 13, 24, 10, box=box)
        when_x, then_x = T["rule_x"]
        cell(d, ix + when_x, mid, then_x - when_x - 12, when, 14, 19, 400, "text2", box)
        d.text(ix + then_x, mid + 5, then, 14, 700, "text", box=box)
        if index:
            d.line(ix, mid - rh / 2, ix + iw, mid - rh / 2, stroke="cardline", sw=1)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    rh = (y + h - cy - 12) / len(T["measures"])
    for index, (name, value, note) in enumerate(T["measures"]):
        mid = cy + index * rh + rh / 2
        total = name == T["total"]  # 위 여섯 구간을 더한 값
        d.text(ix, mid + 5, name, 14, 700 if total else 400, "text" if total else "text2", box=box)
        d.text(ix + 300, mid + 5, value, 15, 700, "orange", "end", box=box)
        d.text(ix + 320, mid + 5, note, 13, 400, "muted", box=box)
        if index:
            d.line(ix, mid - rh / 2, ix + iw, mid - rh / 2, stroke="cardline", sw=1)


def s4(d, x, y, w, h):
    cy = section(d, x, y, w, h, 4, *T["s4"])
    box = (x, y, w, h)
    dot_list(d, x + 24, cy + 12, w - 48, T["limits"], 14, 20, 7, dot="green", box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    s1(d, 48, 140, 1824, 628)
    s2(d, 48, 788, 640, 256)
    s3(d, 708, 788, 600, 256)
    s4(d, 1328, 788, 544, 256)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()


def live_map(theme="light"):
    """웹 화면용 구조도. 배경과 섹션 틀 없이 구조도만 그리고, 값 자리는 비워 둔다."""
    d = Doc(MAP_W, MAP_H, theme)
    flow_map(d, Geo(0, 0, 1, 1, 1), live=True)
    return d.svg()
