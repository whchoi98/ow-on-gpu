"""구축 단계와 아키텍처 인포그래픽. aws-infographic 스킬의 infokit으로 그린다.

  landscape(theme)  16:9 인포그래픽 한 장 (buildkit이 SVG와 PNG로 만든다)
  use(lang)         그릴 언어를 고른다("ko" 또는 "en"). 영어판은 build_steps_en.py가 만든다

요청 경로 인포그래픽(flow.py)과 같은 구조도를 쓰고, 구성 요소마다 그것을 만든 구축 단계(0~9)의 번호를 붙인다.
기동 흐름의 번호(0~5)와 측정값은 그리지 않는다. 번호 체계가 둘이면 헷갈리기 때문이다.
아래 표는 구축 단계 열 개이고, 번호와 이름은 웹 화면의 "구축 과정" 보기(app/web/src/deploy-steps.js)와 같다.

단계별로 만든 것의 근거
  1단계  infra/cdk-vpc, infra/terraform(eks.tf, karpenter.tf, storage.tf), k8s/base
  2단계  jobs/model-sync          6단계  k8s/sleep-controller
  3단계  k8s/gemma, k8s/qwen, jobs/cache-publish    7단계  infra/terraform(app.tf, bff_eks.tf), k8s/bff, app/bff, app/web
  4단계  k8s/gateway              8단계  infra/terraform/observability.tf, k8s/observability, bench/
  5단계  k8s/decider              웹 검색  docs/10-web-search.md (8단계 뒤, 2026-11-15)
"""
import flow
from infokit import Doc, badge, footer_note, header, para, rw, section

# 구성 요소를 만든 단계. 여기에 없는 것(브라우저, Hugging Face, Image registry)은 이 환경이 만들지 않은 바깥 요소다.
# "+"는 열 단계에 들지 않고 8단계 뒤에 더한 것(웹 검색)이다.
BUILT = {
    "cf": "7", "alb": "7", "bff": "7", "cognito": "7", "pages": "7",
    "gw": "4", "decider": "5",
    "gemma": "3", "cache": "3", "qwen": "3",
    "wake": "6", "search": "+",
    "s3": "1", "identity": "1", "karpenter": "1", "gpu": "1",
    "sync": "2", "amp": "8",
}

# 노드의 값 자리에 적는 것: 그 구성 요소를 만들 때 쓴 도구
TOOLS = {
    "cf": "Terraform", "alb": "kubectl (LBC)", "bff": "kubectl, Docker", "cognito": "Terraform", "pages": "Terraform",
    "gw": "Helm, kubectl", "decider": "kubectl, Docker",
    "gemma": "kubectl", "cache": "Job, initContainer", "qwen": "kubectl",
    "wake": "kubectl", "s3": "Terraform", "identity": "Terraform",
    "sync": "kubectl (Job)", "amp": "Terraform, kubectl",
}

T = dict(
    title="구축 단계와 아키텍처",
    sub_en="Build Steps Mapped onto the Architecture",
    sub_ko="구성 요소마다 그것을 만든 단계의 번호 표시",
    s1=("아키텍처 위의 구축 단계", "원 안의 번호는 그 구성 요소를 만든 단계, 아래 파란 글자는 쓴 도구, +는 8단계 뒤에 추가"),
    s2=("구축 단계 0~9", "번호는 위 그림과 같음, 0단계는 리소스 없음, 9단계는 남은 단계"),
    captions=[("요청 경로", "user", "decider"), ("모델과 이미지 공급", "registry", "hf")],
    search_tool="BFF 도구로 추가",
    todo="남은 단계",
    # 번호, 이름, 쓴 도구, 만든 것, 상태(done 또는 todo)
    steps=[
        ("0", "사전 확인", "읽기 전용 조회", "버전 조합, 체크포인트, 할당량 확인 (리소스 없음)", "done"),
        ("1", "네트워크와 EKS 기반", "CDK, Terraform, kubectl", "VPC, EKS, Karpenter NodePool, 모델 버킷, Pod Identity", "done"),
        ("2", "모델 적재", "kubectl, Job", "Hugging Face에서 S3로 모델 3종 적재", "done"),
        ("3", "vLLM 배포", "kubectl", "Gemma와 Qwen 파드, compile 캐시 게시와 복원", "done"),
        ("4", "GAIE와 게이트웨이", "kubectl, Helm", "내부 NLB, agentgateway, EPP, InferencePool", "done"),
        ("5", "Strands Decider 12B", "Terraform, kubectl, Docker", "Decider 이미지 빌드, 파드, 게이트웨이의 /decide 경로", "done"),
        ("6", "sleep 컨트롤러", "kubectl", "깨우기 API, CronJob 2개, NetworkPolicy", "done"),
        ("7", "앱 계층", "Terraform, kubectl, Docker",
         "CloudFront, WAF, Cognito, S3 페이지, 내부 ALB, BFF 파드, Graviton NodePool", "done"),
        ("8", "관측과 측정", "kubectl, Python", "Prometheus agent, AMP, 측정 Job", "done"),
        ("9", "정리", "스크립트, Terraform, CDK", "전체 리소스를 만든 순서의 반대로 삭제", "todo"),
    ],
    note=("2026-11-14 서울 리전에서 0~8단계 적용, 웹 검색은 2026-11-15에 BFF의 도구로 추가, "
          "BFF는 2026-11-15에 ECS Fargate에서 EKS 파드로 이관, "
          "브라우저와 Hugging Face, Image registry는 이 환경 밖의 요소라 번호 없음"),
)

T_EN = dict(
    title="Build Steps on the Architecture",
    sub_en="ow-on-gpu: Multi-Model vLLM Serving on Amazon EKS",
    sub_ko="Each component carries the number of the step that built it",
    s1=("Build steps on the architecture",
        "Circle: the step that built the component, blue text: the tool used, +: added after step 8"),
    s2=("Build steps 0~9", "Same numbers as the map, step 0 creates no resources, step 9 is still to do"),
    captions=[("Request path", "user", "decider"), ("Model and image supply", "registry", "hf")],
    search_tool="Added as BFF tool",
    todo="Not done yet",
    steps=[
        ("0", "Preflight", "Read-only queries", "Version matrix, checkpoints, quotas checked (no resources)", "done"),
        ("1", "Network and EKS base", "CDK, Terraform, kubectl", "VPC, EKS, Karpenter NodePools, model bucket, Pod Identity", "done"),
        ("2", "Model sync", "kubectl, Job", "3 models from Hugging Face to S3", "done"),
        ("3", "vLLM deployment", "kubectl", "Gemma and Qwen pods, compile cache publish and restore", "done"),
        ("4", "GAIE and gateway", "kubectl, Helm", "Internal NLB, agentgateway, EPP, InferencePools", "done"),
        ("5", "Strands Decider 12B", "Terraform, kubectl, Docker", "Decider image build, pod, /decide route on the gateway", "done"),
        ("6", "Sleep controller", "kubectl", "Wake API, 2 CronJobs, NetworkPolicy", "done"),
        ("7", "App layer", "Terraform, kubectl, Docker",
         "CloudFront, WAF, Cognito, S3 pages, internal ALB, BFF pods, Graviton NodePool", "done"),
        ("8", "Observability and measurement", "kubectl, Python", "Prometheus agent, AMP, bench Jobs", "done"),
        ("9", "Cleanup", "Script, Terraform, CDK", "Delete every resource in reverse order of creation", "todo"),
    ],
    note=("Steps 0~8 applied 2026-11-14 in the Seoul Region. Web search added 2026-11-15 as a BFF tool. "
          "BFF moved from ECS Fargate to EKS pods 2026-11-15. "
          "The browser, Hugging Face, and the image registry are outside this environment and carry no number"),
)

TEXT = {"ko": T, "en": T_EN}
LANG = "ko"


def use(lang):
    """그릴 언어를 고른다. 구조도의 글은 flow.py가 그리므로 함께 바꾼다."""
    global T, LANG
    T, LANG = TEXT[lang], lang
    flow.use(lang)


def step_mark(d, cx, cy, num, r=11, size=13, todo=False):
    """구축 단계의 번호. 웹 화면의 단계 표식과 같은 모양(짙은 원에 흰 숫자)이고, 남은 단계는 점선 테두리다."""
    if todo:
        d.circle(cx, cy, r, fill="card", stroke="text", sw=1.4)
        d.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="none" stroke="{d.c("card")}" stroke-width="1.6" '
              f'stroke-dasharray="3 3"/>')
        d.text(cx, cy + size * 0.35, num, size, 700, "text", "middle")
    else:
        badge(d, cx, cy, num, r=r, size=size)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    top = cy - 8
    g = flow.fit(x + 24, top, (w - 48) / flow.MAP_W, y + h - 18 - top, 1.08)
    tools = {**TOOLS, "search": T["search_tool"]}
    flow.flow_map(d, g, box=box, captions=T["captions"], values=tools, value_color="blue", badges=False)
    # 번호는 구성 요소의 오른쪽 위 모서리에 걸쳐 놓는다. 이름과 선이 지나지 않는 자리다.
    for name, num in BUILT.items():
        nx, ny, nw, _ = g.rect(name)
        step_mark(d, nx + nw - 2, ny + 2, num, r=11 * g.k, size=round(13 * g.k))


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    cols, gap = 5, 14
    ix, iw = x + 24, w - 48
    cw = (iw - gap * (cols - 1)) / cols
    ch = (y + h - 16 - cy - gap) / 2
    for index, (num, title, tools, makes, status) in enumerate(T["steps"]):
        cx = ix + (index % cols) * (cw + gap)
        ty = cy + (index // cols) * (ch + gap)
        todo = status == "todo"
        d.rect(cx, ty, cw, ch, rx=10, fill="panel", stroke="line2", sw=1.2, dash="6 5" if todo else None)
        step_mark(d, cx + 26, ty + 31, num, r=13, size=15, todo=todo)
        d.text(cx + 50, ty + 27, title, 15, 700, "text", box=box)
        # 도구는 이름 아래 줄에 둔다. 이름 옆에 두면 긴 이름(영어판)과 겹친다.
        d.text(cx + 50, ty + 45, f"{tools}, {T['todo']}" if todo else tools, 11.5, 400, "pink" if todo else "blue", box=box)
        para(d, cx + 16, ty + 70, cw - 32, makes, 13, 18, 400, "text2", box=box, maxl=2)


def landscape(theme):
    flow.use(LANG)
    try:
        d = Doc(1920, 1080, theme)
        d.rect(0, 0, 1920, 1080, fill="bg")
        header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
        s1(d, 48, 140, 1824, 584)
        s2(d, 48, 744, 1824, 300)
        footer_note(d, 1872, 1064, T["note"])
        return d.svg()
    finally:
        flow.use("ko")
