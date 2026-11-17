# Infrastructure as Code / IaC 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The VPC is one AWS CDK stack (EksVpcStack). Everything else is Terraform with a local state file; Terraform looks the VPC up instead of creating it. Kubernetes objects are not in Terraform except the Helm releases for Karpenter and the AWS Load Balancer Controller.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| VPC stack | `infra/cdk-vpc/lib/eks-vpc-stack.ts` | Subnets in four AZs, NAT gateways, gateway and interface endpoints |
| Cluster | `infra/terraform/eks.tf` | EKS cluster, managed node group for add-ons, add-ons |
| Karpenter | `infra/terraform/karpenter.tf` | Helm release, node role, Pod Identity association |
| Load Balancer Controller | `infra/terraform/lbc.tf` | Helm release and IAM policy |
| Storage | `infra/terraform/storage.tf` | Model bucket, roles and Pod Identity for serving pods and jobs |
| Observability | `infra/terraform/observability.tf` | Prometheus workspace, collector role, ALB access-log bucket |
| App layer | `infra/terraform/app.tf` | CloudFront, WAF, Cognito, static page bucket and objects, ECR repository, security groups |
| BFF on EKS | `infra/terraform/bff_eks.tf` | BFF pod role, Pod Identity, CloudFront VPC origin |
| Network lookup | `infra/terraform/network.tf` | Looks up `eks-vpc` and tags subnets |

### 3. Key Decisions
- The VPC is a separate CDK stack; Terraform looks it up and creates no VPC, subnet or endpoint.
- AWS permissions are granted only through EKS Pod Identity and IAM roles; no credentials in code or state.
- The internal ALB is created by the AWS Load Balancer Controller from an Ingress, not by Terraform.
- Cognito users are created with a script so passwords never enter the Terraform state.
- App-layer changes are planned with `-target`, because a plan without it fails at the Karpenter Helm release registry login.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `infra/terraform/app.tf`: CloudFront behaviours, WAF rate rule, Cognito client
- `infra/terraform/bff_eks.tf`: VPC origin that points at the controller-made ALB
- `infra/terraform/outputs.tf`: Outputs read by `k8s/*/install.sh` and `app/bff/build.sh`
- `infra/terraform/variables.tf`: Inputs such as the WAF rate limit
- `infra/cdk-vpc/bin/eks-vpc.ts`: CDK app entry point

### 5. Cross-references
- Related modules: `infra/CLAUDE.md`
- Related documents: `docs/00-versions.md`, `docs/07-bff.md`, `docs/architecture.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
VPC는 AWS CDK 스택 하나(EksVpcStack)입니다. 그 밖의 리소스는 로컬 상태 파일을 쓰는 Terraform이 만들고, Terraform은 VPC를 만들지 않고 조회합니다. 쿠버네티스 객체는 Karpenter와 AWS Load Balancer Controller의 Helm 릴리스만 Terraform에 있습니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| VPC stack | `infra/cdk-vpc/lib/eks-vpc-stack.ts` | 4개 AZ의 서브넷, NAT 게이트웨이, 게이트웨이와 인터페이스 엔드포인트 |
| Cluster | `infra/terraform/eks.tf` | EKS 클러스터, 애드온용 관리형 노드 그룹, 애드온 |
| Karpenter | `infra/terraform/karpenter.tf` | Helm 릴리스, 노드 역할, Pod Identity 연결 |
| Load Balancer Controller | `infra/terraform/lbc.tf` | Helm 릴리스와 IAM 정책 |
| Storage | `infra/terraform/storage.tf` | 모델 버킷, 서빙 파드와 Job의 역할과 Pod Identity |
| Observability | `infra/terraform/observability.tf` | Prometheus 작업 공간, 수집기 역할, ALB 접근 로그 버킷 |
| App layer | `infra/terraform/app.tf` | CloudFront, WAF, Cognito, 정적 페이지 버킷과 객체, ECR 저장소, 보안 그룹 |
| BFF on EKS | `infra/terraform/bff_eks.tf` | BFF 파드의 역할, Pod Identity, CloudFront VPC origin |
| Network lookup | `infra/terraform/network.tf` | `eks-vpc`를 조회하고 서브넷에 태그를 붙임 |

### 3. 주요 결정
- VPC는 별도 CDK 스택입니다. Terraform은 VPC, 서브넷, 엔드포인트를 만들지 않고 조회해서 씁니다.
- AWS 권한은 EKS Pod Identity와 IAM 역할로만 부여합니다. 자격 증명을 코드와 상태에 두지 않습니다.
- 내부 ALB는 Terraform이 아닌 AWS Load Balancer Controller가 Ingress에서 만듭니다.
- Cognito 사용자는 스크립트로 만들어 비밀번호가 Terraform 상태에 들어가지 않게 합니다.
- 앱 계층 변경은 `-target`으로 plan합니다. `-target` 없는 plan은 Karpenter Helm 릴리스의 레지스트리 로그인에서 실패합니다.

ADR은 `docs/decisions/ADR-001-narrow-decider-fallback.md` 하나입니다(Decider 기본값 처리의 범위). 그 밖의 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `infra/terraform/app.tf`: CloudFront behavior, WAF 속도 규칙, Cognito 클라이언트
- `infra/terraform/bff_eks.tf`: 컨트롤러가 만든 ALB를 가리키는 VPC origin
- `infra/terraform/outputs.tf`: `k8s/*/install.sh`와 `app/bff/build.sh`가 읽는 출력
- `infra/terraform/variables.tf`: WAF 속도 제한 같은 입력
- `infra/cdk-vpc/bin/eks-vpc.ts`: CDK 앱의 진입점

### 5. 상호 참조
- 관련 모듈: `infra/CLAUDE.md`
- 관련 문서: `docs/00-versions.md`, `docs/07-bff.md`, `docs/architecture.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
