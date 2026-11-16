#!/usr/bin/env python3
"""AWS 환경을 식별하는 값을 자리 표시로 바꾼다.

이 저장소는 공개 저장소에 올라간다. 계정 ID, ARN, CloudFront 주소, 로드 밸런서 주소, 사용자 풀 ID,
버킷 이름의 무작위 접미사, 리소스 ID 같은 값은 올리지 않는다. 측정 스크립트의 출력과 원시 로그에는
이런 값이 섞여 나오므로, results/에 저장한 뒤 커밋하기 전에 이 스크립트로 가린다.

    python3 scripts/mask-identifiers.py results/2026-11-16-항목      # 가린다
    python3 scripts/mask-identifiers.py --check results               # 가릴 것이 있는지만 본다(있으면 exit 1)
    python3 scripts/mask-identifiers.py --stdout k8s/base/params.yaml # 파일은 두고 가린 내용을 출력한다(예시 파일을 만들 때)

커밋 전 검사(.claude/hooks/secret-scan.sh의 IDENTIFIER_PATTERNS)가 같은 종류의 값을 막는다.
시험(tests/hooks/test-secret-patterns.sh)이 표본마다 "검사기가 잡는다"와 "이 스크립트로 가리면 통과한다"를 함께 확인한다.
프라이빗 IP와 노드 이름(ip-10-...)은 밖에서 쓸 수 없는 값이라 가리지 않는다.
"""
import ipaddress
import os
import re
import sys

# AWS가 공개한 계정. Deep Learning Containers 레지스트리처럼 매니페스트의 이미지 주소에 꼭 필요한 값이다.
PUBLIC_AWS_ACCOUNTS = {"763104351884"}

RESOURCE_KINDS = {"vpc": "vpc-id", "subnet": "subnet-id", "sg": "security-group-id", "sgr": "security-group-rule-id",
                  "eni": "eni-id", "eipalloc": "eip-allocation-id", "nat": "nat-gateway-id", "igw": "internet-gateway-id",
                  "rtb": "route-table-id", "vpce": "vpc-endpoint-id", "i": "instance-id"}


def account(match):
    return match.group(0) if match.group("id") in PUBLIC_AWS_ACCOUNTS else match.group(0).replace(match.group("id"), "<account-id>")


# (이름, 정규식, 바꿀 값). 차례가 중요하다. ARN을 먼저 통째로 바꿔야 그 안의 다른 값과 겹치지 않는다.
RULES = [
    ("arn", re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(?:\d{12}|<account-id>):[^\s\"'\\,\])]+"), "<arn>"),
    ("account-id", re.compile(r"(?<![0-9])(?P<id>\d{12})(?=\.dkr\.ecr\.)"), account),
    ("account-id", re.compile(r"(?:account=|AWSLogs/|amazonaws\.com/|\"Account\": \"|\"OwnerId\": \")(?P<id>\d{12})(?![0-9])"), account),
    ("cloudfront-domain", re.compile(r"\b[a-z0-9]{10,16}\.cloudfront\.net\b"), "<cloudfront-domain>"),
    ("user-pool-id", re.compile(r"\b[a-z]{2}-[a-z]+-\d_[A-Za-z0-9]{9}\b"), "<user-pool-id>"),
    ("elb-dns-name", re.compile(r"\b[A-Za-z0-9-]+\.(?:elb\.[a-z0-9-]+|[a-z0-9-]+\.elb)\.amazonaws\.com\b"), "<elb-dns-name>"),
    ("load-balancer-id", re.compile(r"\b(?:app|net)/[A-Za-z0-9-]{1,32}/[0-9a-f]{16}\b"), "<load-balancer-id>"),
    ("eks-endpoint", re.compile(r"\b[A-Fa-f0-9]{32}\.[a-z0-9]+\.[a-z0-9-]+\.eks\.amazonaws\.com\b"), "<eks-endpoint>"),
    ("amp-workspace-id", re.compile(r"\bws-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b"), "<amp-workspace-id>"),
    ("bucket-suffix", re.compile(r"\b(ow-on-gpu-(?:[a-z]+-)*)[0-9a-f]{16,}\b"), r"\1<suffix>"),
    ("resource-id", re.compile(r"\b(vpc|subnet|sgr|sg|eni|eipalloc|nat|igw|rtb|vpce|i)-[0-9a-f]{8,17}\b"),
     lambda match: f"<{RESOURCE_KINDS[match.group(1)]}>"),
    ("vpc-origin-id", re.compile(r"\bvo_[A-Za-z0-9]{10,}\b"), "<vpc-origin-id>"),
    ("cidr-32", re.compile(r"(?<![\d.])(?!10\.|127\.|192\.168\.|172\.(?:1[6-9]|2[0-9]|3[01])\.)(?:\d{1,3}\.){3}\d{1,3}/32\b"), "<ip>/32"),
]

# Terraform 적용 로그: 리소스 ID와 출력값
TERRAFORM_LOG = re.compile(r"(^|/)terraform-[a-z-]*\.log$")
TERRAFORM_RULES = [
    ("terraform-id", re.compile(r"\[id=[^\]\n]+\]"), "[id=<id>]"),
    ("terraform-output", re.compile(
        r"^(app_url|bff_alb_dns|bff_repository_url|cluster_endpoint|cognito_client_id|cognito_user_pool_id|model_bucket|"
        r"alb_log_bucket|amp_endpoint|amp_workspace_id|vpc_id|wake_nlb_dns) = .*$", re.M), r"\1 = <masked>"),
]
# 접근 로그: 클라이언트의 공인 IP(CloudFront 엣지 주소 포함)
ACCESS_LOG = re.compile(r"(^|/)(alb-log|cloudfront-log|access-log)[^/]*$")
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def public_ip(match):
    try:
        ip = ipaddress.ip_address(match.group(0))
    except ValueError:
        return match.group(0)
    hidden = not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified)
    return "<ip>" if hidden else match.group(0)


def mask(text, path=""):
    """가린 글과 종류별 횟수를 돌려준다."""
    counts = {}

    def apply(name, pattern, replacement, text):
        changed = 0

        def swap(match):
            nonlocal changed
            new = replacement(match) if callable(replacement) else match.expand(replacement)
            # 공개 계정처럼 그대로 둔 것은 횟수에 넣지 않는다
            if new != match.group(0):
                changed += 1
            return new

        text = pattern.sub(swap, text)
        if changed:
            counts[name] = counts.get(name, 0) + changed
        return text

    before = text
    for name, pattern, replacement in RULES:
        text = apply(name, pattern, replacement, text)
    if TERRAFORM_LOG.search(path):
        for name, pattern, replacement in TERRAFORM_RULES:
            text = apply(name, pattern, replacement, text)
    if ACCESS_LOG.search(path):
        text = apply("public-ip", IPV4, public_ip, text)
    if text == before:
        return text, {}
    return text, counts


def files_under(paths):
    for path in paths:
        if os.path.isdir(path):
            for base, folders, names in os.walk(path):
                folders[:] = [f for f in folders if f not in (".git", "node_modules", ".terraform", "cdk.out", "dist", "__pycache__")]
                for name in names:
                    yield os.path.join(base, name)
        else:
            yield path


def main(argv):
    check = "--check" in argv
    paths = [arg for arg in argv if not arg.startswith("--")]
    if "--stdout" in argv:
        if len(paths) != 1 or not os.path.isfile(paths[0]):
            print("--stdout에는 파일 하나를 줍니다", file=sys.stderr)
            return 2
        with open(paths[0], encoding="utf-8") as handle:
            sys.stdout.write(mask(handle.read(), paths[0])[0])
        return 0
    if not paths:
        print(__doc__.strip().splitlines()[0])
        print("사용법: python3 scripts/mask-identifiers.py [--check] <파일 또는 디렉터리>...")
        return 2
    total, touched = {}, 0
    for path in files_under(paths):
        try:
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except (UnicodeDecodeError, OSError):
            continue  # 그림 같은 바이너리 파일
        masked, counts = mask(text, path)
        if masked == text:
            continue
        touched += 1
        for name, count in counts.items():
            total[name] = total.get(name, 0) + count
        if check:
            print(f"가릴 값이 있음: {path} ({', '.join(sorted(counts))})")
        else:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(masked)
    summary = ", ".join(f"{name} {count}" for name, count in sorted(total.items())) or "없음"
    print(f"{'가릴 값이 있는' if check else '가린'} 파일 {touched}개. 종류별 횟수: {summary}")
    return 1 if check and touched else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
