# infra 모듈

## Role

AWS 리소스를 코드로 관리합니다. VPC는 CDK가, 그 밖의 리소스는 Terraform이 만듭니다. Terraform은 VPC를 만들지 않고 CDK가 만든 `eks-vpc`를 조회해서 씁니다.

## Key Files

| 파일 | 내용 |
|---|---|
| `cdk-vpc/lib/eks-vpc-stack.ts` | 스택 EksVpcStack. 4개 AZ의 Public, Private, Isolated 서브넷, AZ별 NAT 게이트웨이, 게이트웨이와 인터페이스 엔드포인트 |
| `terraform/versions.tf`, `variables.tf`, `outputs.tf` | 프로바이더 버전, 변수, 출력. `k8s/*/install.sh`와 `app/bff/build.sh`가 출력을 읽음 |
| `terraform/network.tf` | `eks-vpc`와 서브넷 조회, 서브넷 태그 |
| `terraform/eks.tf` | EKS 클러스터, 애드온용 관리형 노드 그룹, 애드온 |
| `terraform/karpenter.tf` | Karpenter(Helm), 노드 역할, Pod Identity |
| `terraform/lbc.tf` | AWS Load Balancer Controller(Helm), IAM 정책 |
| `terraform/storage.tf` | 모델 버킷, 서빙 파드와 적재 Job의 역할과 Pod Identity |
| `terraform/observability.tf` | Amazon Managed Service for Prometheus 작업 공간, 수집기 역할, ALB 접근 로그 버킷 |
| `terraform/app.tf` | CloudFront, WAF, Cognito, 정적 페이지 버킷과 객체, ECR 저장소, 보안 그룹 |
| `terraform/bff_eks.tf` | BFF 파드의 역할과 Pod Identity, CloudFront VPC origin |
| `terraform/bff.auto.tfvars` | `app/bff/build.sh`가 적는 BFF 이미지 태그. 커밋하지 않음 |

## Rules

- AWS 리소스를 만들거나 바꾸거나 지우기 전에 `terraform plan`(CDK는 `cdk diff`) 결과를 보여 주고 승인을 받은 뒤 실행합니다. GPU 노드가 뜨는 변경은 따로 알립니다
- `terraform plan`을 `-target` 없이 실행하면 `helm_release.karpenter`의 레지스트리 로그인에서 실패합니다. 변경 범위를 `-target`으로 좁힙니다. `-target` 없이 적용할 일이 생기면 이 문제를 먼저 풉니다
- 서로 참조하는 보안 그룹은 참조하는 쪽의 규칙을 먼저 고친 뒤 지웁니다. 순서가 반대면 삭제가 `DependencyViolation`으로 실패합니다
- 상태 파일(`terraform.tfstate*`)은 읽지 않고 커밋하지 않습니다. 레지스트리 토큰 같은 값이 들어 있습니다
- `cdk-vpc/cdk.context.json`은 계정 ID가 들어 있어 커밋하지 않습니다. 없으면 CDK가 합성할 때 AZ를 다시 조회합니다
- `terraform/terraform.tfvars`(EKS API에 접근을 허용할 공인 IP)는 커밋하지 않습니다. 추적하는 것은 `terraform/terraform.tfvars.example`입니다
- 자격 증명과 비밀번호를 변수, 상태, 코드에 넣지 않습니다. Cognito 사용자는 `app/bff/create-user.sh`로 만듭니다
- 외부 접근 경로는 CloudFront, 내부 ALB, 프라이빗 파드뿐입니다. ALB는 Private 서브넷에 둡니다
- 리소스를 바꾸면 `docs/architecture.md`의 Infrastructure 표와 `docs/reference/iac.md`를 함께 고칩니다
