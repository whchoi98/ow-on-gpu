# Security / 보안 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The only way in from outside is CloudFront with AWS WAF, then an internal ALB, then pods in private subnets. Users sign in to a Cognito user pool and the BFF verifies the access token on every path. Requests with sensitive data go only to Gemma, and AWS permissions are granted only through EKS Pod Identity.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| Edge | `infra/terraform/app.tf` | CloudFront, WAF rate rule, Cognito user pool and client, security groups |
| Token verification | `app/bff/auth.py` | RS256 only, issuer and client checks, access tokens only |
| Data policy | `app/bff/routing.py` | Resident registration and card number patterns; sensitive requests go to Gemma |
| Network policies | `k8s/sleep-controller/networkpolicies.yaml` | Limits who may call the wake API |
| Pod identity | `infra/terraform/storage.tf` | Roles for serving pods and jobs; `bff_eks.tf` for the BFF |
| Pod hardening | `k8s/bff/bff.yaml` | Non-root user, read-only root filesystem, dropped capabilities |
| User creation | `app/bff/create-user.sh` | Creates a Cognito user; the password comes from an environment variable |
| Commit check | `.claude/hooks/secret-scan.sh` | Blocks commits that contain secret-like strings, environment identifiers or forbidden files |
| Identifier masking | `scripts/mask-identifiers.py` | Replaces environment identifiers in result files with placeholders |

### 3. Key Decisions
- The public URL requires a Cognito login and sign-up is disabled (decided 2026-11-14).
- The demo password is never stored in code, Terraform state, documents or result files.
- The ALB stays in private subnets and accepts traffic only from the CloudFront VPC origin.
- Web search is not attached to sensitive requests, so search queries with personal data never leave the Region.
- Environment identifiers (account IDs, ARNs, CloudFront and load balancer addresses, resource IDs, public IPs) are never committed; a pre-commit check blocks them and `scripts/mask-identifiers.py` masks result files.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `app/bff/auth.py`: `CognitoVerifier.verify`
- `app/bff/bff.py`: `require_login` middleware
- `app/bff/routing.py`: `sensitive_kind` and the `RRN`, `CARD` patterns
- `infra/terraform/app.tf`: WAF web ACL and security group rules
- `.claude/settings.json`: Deny list for dangerous commands and secret-bearing files

### 5. Cross-references
- Related modules: `app/CLAUDE.md`, `infra/CLAUDE.md`, `k8s/CLAUDE.md`
- Related documents: `docs/07-bff.md`, `docs/10-web-search.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
밖에서 들어오는 길은 AWS WAF가 붙은 CloudFront, 내부 ALB, Private 서브넷의 파드 하나뿐입니다. 사용자는 Cognito 사용자 풀에 로그인하고 BFF가 모든 경로에서 액세스 토큰을 검증합니다. 민감 정보가 있는 요청은 Gemma로만 보내고, AWS 권한은 EKS Pod Identity로만 부여합니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| Edge | `infra/terraform/app.tf` | CloudFront, WAF 속도 규칙, Cognito 사용자 풀과 클라이언트, 보안 그룹 |
| Token verification | `app/bff/auth.py` | RS256 고정, 발급자와 클라이언트 확인, 액세스 토큰만 받음 |
| Data policy | `app/bff/routing.py` | 주민등록번호와 카드번호 형식. 민감 정보 요청은 Gemma로 |
| Network policies | `k8s/sleep-controller/networkpolicies.yaml` | 깨우기 API를 부를 수 있는 호출자 제한 |
| Pod identity | `infra/terraform/storage.tf` | 서빙 파드와 Job의 역할. BFF는 `bff_eks.tf` |
| Pod hardening | `k8s/bff/bff.yaml` | 비루트 사용자, 읽기 전용 루트 파일 시스템, capability 제거 |
| User creation | `app/bff/create-user.sh` | Cognito 사용자를 만듦. 비밀번호는 환경 변수로 받음 |
| Commit check | `.claude/hooks/secret-scan.sh` | 비밀 값으로 보이는 문자열, 환경 식별 값, 금지한 파일이 든 커밋을 막음 |
| Identifier masking | `scripts/mask-identifiers.py` | 결과 파일의 환경 식별 값을 자리 표시로 바꿈 |

### 3. 주요 결정
- 공개 주소는 Cognito 로그인을 요구하고 가입은 막았습니다(2026-11-14 결정).
- 데모 계정 비밀번호는 코드, Terraform 상태, 문서, 결과 파일 어디에도 남기지 않습니다.
- ALB는 Private 서브넷에 두고 CloudFront VPC origin에서 오는 트래픽만 받습니다.
- 민감 정보 요청에는 웹 검색을 붙이지 않습니다. 개인정보가 든 검색어가 리전 밖으로 나가지 않습니다.
- 환경 식별 값(계정 ID, ARN, CloudFront와 로드 밸런서 주소, 리소스 ID, 공인 IP)은 커밋하지 않습니다. 커밋 전 검사가 막고, 결과 파일은 `scripts/mask-identifiers.py`로 가립니다.

ADR은 아직 없습니다. 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `app/bff/auth.py`: `CognitoVerifier.verify`
- `app/bff/bff.py`: `require_login` 미들웨어
- `app/bff/routing.py`: `sensitive_kind`와 `RRN`, `CARD` 형식
- `infra/terraform/app.tf`: WAF web ACL과 보안 그룹 규칙
- `.claude/settings.json`: 위험한 명령과 비밀 값이 든 파일의 deny 목록

### 5. 상호 참조
- 관련 모듈: `app/CLAUDE.md`, `infra/CLAUDE.md`, `k8s/CLAUDE.md`
- 관련 문서: `docs/07-bff.md`, `docs/10-web-search.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
