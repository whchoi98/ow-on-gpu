"""Part 3, figure 2: which tool applies what in which step, the apply order inside step 7, and the apply rules.

Sources (ow-on-gpu repository): README.md (install table), app/web/src/deploy-steps.js (commands per step),
k8s/gateway/install.sh, k8s/bff/install.sh and app/bff/build.sh (order and what each script reads),
AGENT.md and docs/onboarding.md (working rules). Step 9 has not been run; its cells are the plan.
"""
from infokit import (CODE_FAMILY, Doc, badge, callout, cell, dot_list, footer_note, header, rw, section, series_nav,
                     wrap_balanced)

from common import PART, SERIES, pick

T_KO = dict(
    title="도구와 적용 순서",
    sub_en="OpenWeight on AWS GPU",
    sub_ko="도구가 맡는 범위, 10개 단계의 순서, 7단계 안의 순서",
    s1=("도구별 담당 범위", "칸의 글은 그 도구가 그 단계에서 적용하는 것, 점선 칸은 아직 실행하지 않은 9단계의 계획"),
    steps=["사전 확인", "EKS 기반", "모델 적재", "vLLM", "게이트웨이", "Decider 12B", "sleep", "앱 계층", "관측, 측정", "정리"],
    # name, where the code lives, color, {step: what it applies}
    lanes=[
        ("AWS CDK", "infra/cdk-vpc", "orange",
         {1: "VPC, 서브넷, 엔드포인트", 9: "VPC 스택 삭제"}),
        ("Terraform", "infra/terraform", "purple",
         {1: "EKS, Karpenter, LBC, 모델 버킷, 역할", 5: "Decider 이미지의 ECR 저장소",
          7: "CloudFront, WAF, Cognito, S3 페이지",
          8: "AMP 워크스페이스", 9: "terraform destroy"}),
        ("kubectl, Helm", "k8s/, jobs/", "blue",
         {1: "NodePool, EC2NodeClass", 2: "모델 적재 Job", 3: "vLLM 파드, 캐시 게시 Job",
          4: "CRD, agentgateway, EPP", 5: "Decider 파드, /decide 경로", 6: "CronJob, 깨우기 API, NetworkPolicy",
          7: "BFF 파드, Ingress, NodePool", 8: "Prometheus agent, 측정 Job", 9: "Deployment, NodePool 삭제"}),
        ("그 밖의 도구", "AWS CLI, Docker, npm, Python", "green",
         {0: "AWS CLI 읽기 전용 조회", 5: "Docker 이미지 빌드", 7: "Docker, npm 빌드", 8: "Python 측정 스크립트"}),
    ],
    s2=("7단계 안의 적용 순서", "내부 ALB를 컨트롤러가 만들기 때문에 Terraform을 앞뒤로 두 번 적용"),
    # tool, color, command, what it does
    order=[
        ("Terraform", "purple", "terraform apply -target=aws_ecr_repository.bff", "BFF 이미지를 올릴 ECR 저장소 생성"),
        ("Docker, npm", "green", "app/bff/build.sh, app/web/build.sh",
         "BFF 이미지(arm64)와 확인용 페이지 빌드, 이미지 안에서 BFF 시험 실행"),
        ("Terraform", "purple", "terraform plan, terraform apply",
         "CloudFront, WAF, Cognito, S3 페이지, BFF의 역할과 Pod Identity 연결"),
        ("kubectl", "blue", "k8s/bff/install.sh diff, apply",
         "NodePool app, BFF 파드, Ingress 적용, 컨트롤러가 내부 ALB 생성"),
        ("Terraform", "purple", "terraform apply", "컨트롤러가 만든 ALB를 태그로 조회해 CloudFront VPC origin에 연결"),
        ("스크립트", "orange", "app/bff/create-user.sh <이메일>", "Cognito 사용자 생성, 비밀번호는 프롬프트나 USER_PASSWORD로 전달"),
    ],
    s3=("모든 단계의 적용 규칙", "차이를 먼저 보고 적용"),
    flow=[("차이 확인", "terraform plan", "kubectl diff"), ("검토", "바뀌는 줄 확인", "모르는 줄은 원인 확인"),
          ("적용", "terraform apply", "kubectl apply"), ("확인", "로그, 상태, 응답", "측정한 값과 비교")],
    rules=[
        "CRD 필드, Helm values, vLLM 플래그는 설치한 버전에서 확인 (kubectl explain, helm show values, vllm serve --help)",
        "자격 증명은 매니페스트에 넣지 않고 EKS Pod Identity로 IAM 역할 연결",
        "환경별 값이 든 파일 5개는 *.example을 복사해 채우고 저장소에 올리지 않음",
        "GPU 노드가 뜨는 적용은 실행 전에 따로 확인",
        "kubectl은 프로젝트 전용 kubeconfig로 사용",
        "측정한 값만 문서에 적고 원시 자료는 results/ 아래에 저장",
    ],
    call=("Terraform 출력을 읽는 스크립트", "install.sh와 build.sh가 이미지 주소와 Cognito 값을 출력에서 읽음, 계정 ID를 파일에 적지 않음"),
    note="명령과 순서는 ow-on-gpu 저장소의 README, k8s/gateway/install.sh, k8s/decider/install.sh, k8s/bff/install.sh, app/bff/build.sh 기준, "
         "9단계는 실행하지 않은 계획",
)

T_EN = dict(
    title="Tools and Apply Order",
    sub_en="OpenWeight on AWS GPU",
    sub_ko="What each tool applies, the order of the ten steps, the order inside step 7",
    s1=("What each tool applies", "A cell says what the tool applies in that step, dashed cells are the plan for step 9, not run yet"),
    steps=["Preflight", "EKS base", "Model sync", "vLLM", "Gateway", "Decider 12B", "Sleep", "App layer", "Observability", "Cleanup"],
    lanes=[
        ("AWS CDK", "infra/cdk-vpc", "orange",
         {1: "VPC, subnets, endpoints", 9: "Delete the VPC stack"}),
        ("Terraform", "infra/terraform", "purple",
         {1: "EKS, Karpenter, LBC, model bucket, roles", 5: "ECR repository for the Decider image",
          7: "CloudFront, WAF, Cognito, S3 pages",
          8: "AMP workspace", 9: "terraform destroy"}),
        ("kubectl, Helm", "k8s/, jobs/", "blue",
         {1: "NodePools, EC2NodeClass", 2: "Model sync Job", 3: "vLLM pods, cache publish Job",
          4: "CRDs, agentgateway, EPP", 5: "Decider pod, /decide route", 6: "CronJobs, wake API, NetworkPolicy",
          7: "BFF pods, Ingress, NodePool", 8: "Prometheus agent, bench Jobs", 9: "Delete Deployments, NodePools"}),
        ("Other tools", "AWS CLI, Docker, npm, Python", "green",
         {0: "Read-only AWS CLI queries", 5: "Docker image build", 7: "Docker and npm builds", 8: "Python bench scripts"}),
    ],
    s2=("Apply order inside step 7", "The controller creates the internal ALB, so Terraform runs before and after it"),
    order=[
        ("Terraform", "purple", "terraform apply -target=aws_ecr_repository.bff", "Create the ECR repository for the BFF image"),
        ("Docker, npm", "green", "app/bff/build.sh, app/web/build.sh",
         "Build the BFF image (arm64) and the check page, run the BFF tests inside the image"),
        ("Terraform", "purple", "terraform plan, terraform apply",
         "CloudFront, WAF, Cognito, S3 pages, the BFF role and its Pod Identity association"),
        ("kubectl", "blue", "k8s/bff/install.sh diff, apply",
         "Apply NodePool app, the BFF pods and the Ingress, the controller creates the internal ALB"),
        ("Terraform", "purple", "terraform apply", "Look up the ALB by tag and connect it to the CloudFront VPC origin"),
        ("Script", "orange", "app/bff/create-user.sh <email>", "Create the Cognito user, password by prompt or USER_PASSWORD"),
    ],
    s3=("Apply rules for every step", "Read the difference first, then apply"),
    flow=[("See the diff", "terraform plan", "kubectl diff"), ("Review", "Lines that change", "Explain unknown lines"),
          ("Apply", "terraform apply", "kubectl apply"), ("Verify", "Logs, status, replies", "Compare the values")],
    rules=[
        "Check CRD fields, Helm values and vLLM flags against the installed version (kubectl explain, helm show values, vllm serve --help)",
        "No credentials in manifests, IAM roles are attached with EKS Pod Identity",
        "Five files with environment values are copied from *.example, filled in and kept out of the repository",
        "Confirm separately before an apply that starts GPU nodes",
        "kubectl uses the project kubeconfig only",
        "Only measured values go into the docs, raw data stays under results/",
    ],
    call=("Scripts that read Terraform outputs", "install.sh and build.sh read the image URL and Cognito values from outputs, no account ID in files"),
    note="Commands and order follow README, k8s/gateway/install.sh, k8s/bff/install.sh and app/bff/build.sh of the "
         "ow-on-gpu repository. Step 9 is a plan that has not been run",
)

T = pick(T_KO, T_EN)


def mid_lines(d, cx, mid, w, text, size, lh, weight, color, box):
    """Text centered on (cx, mid), wrapped to the width w."""
    lines = wrap_balanced(text, size, weight, w) if rw(text, size, weight) > w else [text]
    y0 = mid + size * 0.35 - (len(lines) - 1) * lh / 2
    for i, ln in enumerate(lines):
        d.text(cx, y0 + i * lh, ln, size, weight, color, "middle", box=box)


def s1(d, x, y, w, h):
    cy = section(d, x, y, w, h, 1, *T["s1"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    label_w, head_h = 196, 36
    gx = ix + label_w + 8
    col_w = (ix + iw - gx) / len(T["steps"])
    lane_h = (y + h - 16 - cy - head_h) / len(T["lanes"])
    # step header: number and short name
    d.rect(gx, cy, ix + iw - gx, head_h, rx=6, fill="panel")
    for i, name in enumerate(T["steps"]):
        cx = gx + i * col_w
        badge(d, cx + 18, cy + head_h / 2, str(i), r=11, size=13)
        d.text(cx + 35, cy + head_h / 2 + 5, name, 13.5, 700, "text", box=box)
    for r, (name, where, color, cells) in enumerate(T["lanes"]):
        ly = cy + head_h + r * lane_h
        if r:
            d.line(ix, ly, ix + iw, ly, stroke="cardline", sw=1.0)
        d.rect(ix, ly + 10, 4, lane_h - 20, rx=2, fill=color + "F")
        d.text(ix + 16, ly + lane_h / 2 - 3, name, 16, 700, "text", box=box)
        d.text(ix + 16, ly + lane_h / 2 + 17, where, 12, 400, "muted", box=box)
        for step, text in cells.items():
            cx = gx + step * col_w
            plan = step == 9
            d.rect(cx + 4, ly + 6, col_w - 8, lane_h - 12, rx=8, fill=color + "F", fo=0.05 if plan else 0.13,
                   stroke=color, sw=1.2, dash="5 4" if plan else None)
            mid_lines(d, cx + col_w / 2, ly + lane_h / 2, col_w - 24, text, 12.5, 16, 400 if plan else 700,
                      "text2" if plan else "text", box)


def s2(d, x, y, w, h):
    cy = section(d, x, y, w, h, 2, *T["s2"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    rh = (y + h - 14 - cy) / len(T["order"])
    cmd_x, desc_x = ix + 164, ix + 500
    for i, (tool, color, cmd, desc) in enumerate(T["order"]):
        top = cy + i * rh
        mid = top + rh / 2
        if i:
            d.line(ix, top, ix + iw, top, stroke="cardline", sw=1.0)
            d.line(ix + 16, top - 8, ix + 16, top + 8, stroke="arrow", sw=1.4, so=0.6)
        badge(d, ix + 16, mid, str(i + 1), r=13, size=14)
        tw_ = rw(tool, 12.5, 700) + 20
        d.rect(ix + 42, mid - 12, tw_, 24, rx=12, fill=color + "F", fo=0.14, stroke=color, sw=1.1)
        d.text(ix + 42 + tw_ / 2, mid + 4.5, tool, 12.5, 700, color, "middle", box=box)
        d.text(cmd_x, mid + 4.5, cmd, 13, 400, "text", box=box, family=CODE_FAMILY)
        cell(d, desc_x, mid, ix + iw - desc_x, desc, 14, 19, 400, "text2", box)


def s3(d, x, y, w, h):
    cy = section(d, x, y, w, h, 3, *T["s3"])
    box = (x, y, w, h)
    ix, iw = x + 24, w - 48
    gap = 26
    cw_ = (iw - gap * (len(T["flow"]) - 1)) / len(T["flow"])
    ch = 82
    for i, (title, a, b) in enumerate(T["flow"]):
        cx = ix + i * (cw_ + gap)
        color = "green" if i == 3 else "blue"
        d.rect(cx, cy, cw_, ch, rx=10, fill=color + "F", fo=0.1, stroke=color, sw=1.3)
        d.text(cx + cw_ / 2, cy + 26, title, 15, 700, "text", "middle", box=box)
        d.text(cx + cw_ / 2, cy + 47, a, 12, 400, "text2", "middle", box=box)
        d.text(cx + cw_ / 2, cy + 64, b, 12, 400, "text2", "middle", box=box)
        if i + 1 < len(T["flow"]):
            d.arrow([(cx + cw_ + 4, cy + ch / 2), (cx + cw_ + gap - 4, cy + ch / 2)], sw=1.6, r=0)
    last = dot_list(d, ix + 2, cy + ch + 34, iw - 4, T["rules"], size=14, lh=20, gap=9, box=box)
    callout(d, ix, max(last + 22, y + h - 16 - 58), iw, *T["call"], box=box)


def landscape(theme):
    d = Doc(1920, 1080, theme)
    d.rect(0, 0, 1920, 1080, fill="bg")
    header(d, 48, 76, T["title"], T["sub_en"], T["sub_ko"])
    series_nav(d, 1872, 48, SERIES, PART)
    s1(d, 48, 140, 1824, 392)
    s2(d, 48, 552, 1100, 492)
    s3(d, 1168, 552, 704, 492)
    footer_note(d, 1872, 1064, T["note"])
    return d.svg()
