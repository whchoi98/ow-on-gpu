---
description: BFF 파드나 확인용 페이지를 빌드하고, 차이를 보여 준 뒤 승인을 받아 배포합니다
allowed-tools: Read, Glob, Grep, Bash(bash tests/run-all.sh:*), Bash(npm test --prefix app/web:*), Bash(git status:*)
---

# 배포

실제 AWS 계정과 클러스터를 바꿉니다. AGENT.md의 작업 규칙대로 `terraform plan` 또는 `kubectl diff` 결과를 먼저 보여 주고 승인을 받은 뒤 적용합니다. 빌드, 차이 보기, 적용 명령은 일부러 미리 허용하지 않았습니다. 명령마다 사용자가 승인합니다.

$ARGUMENTS로 대상을 고릅니다: `bff`, `web`, 또는 둘 다. 그 밖의 대상(vLLM, 게이트웨이, Decider, Terraform의 다른 리소스)은 이 명령이 다루지 않습니다. GPU 노드가 뜨거나 다시 시작되는 작업은 실행 전에 그 사실을 따로 알립니다.

## 1단계: 사전 확인

1. `KUBECONFIG=infra/terraform/.kubeconfig`을 씁니다. 공유 장비의 기본 컨텍스트를 바꾸지 않습니다
2. 시험을 돌립니다: `bash tests/run-all.sh`, `npm test --prefix app/web`, BFF 시험(`/test-all`)
3. 헤더 값이나 응답 형식이 바뀌는 변경이면 받는 쪽을 먼저 배포합니다. 화면이 새 값을 모르면 잘못 표시합니다(웹 먼저, BFF 나중)

## 2단계: 빌드와 차이

### BFF
```bash
app/bff/build.sh                 # arm64 이미지를 만들어 ECR에 올리고 태그를 infra/terraform/bff.auto.tfvars에 적음
k8s/bff/install.sh diff          # 서버 dry-run. 클러스터의 웹훅이 더하는 줄까지 보임
```
diff에 이미지 태그 말고 다른 줄이 있으면 적용하지 않고 무엇이 더하는지 먼저 확인합니다. 2026-11-16부터 이 클러스터에는 파드 템플릿이 바뀌는 Deployment에 자동 계측 애노테이션을 붙이는 웹훅이 있습니다(`docs/07-bff.md`).

### 웹
```bash
app/web/build.sh                                                        # npm ci, npm test, npm run build
terraform -chdir=infra/terraform plan -target=aws_s3_object.web -out=<계획 파일>
```
`-target` 없이 plan을 하면 `helm_release.karpenter`의 레지스트리 로그인에서 실패합니다. 앱 변경은 `-target`으로 좁힙니다.

## 3단계: 승인

diff와 plan의 요약(추가, 수정, 삭제 수와 바뀌는 줄)을 본문에 보여 주고 사용자의 승인을 기다립니다. 승인받은 내용과 다른 줄이 생기면 다시 보여 줍니다.

## 4단계: 적용과 확인

```bash
terraform -chdir=infra/terraform apply <계획 파일>
k8s/bff/install.sh apply
kubectl -n app rollout status deploy/bff --timeout=300s
```

적용 뒤에 확인합니다.
- 파드의 이미지 태그, 재시작 횟수, init 컨테이너가 없는지, ALB 대상이 healthy인지
- 라이브 사이트: `python bench/bff/lang_check_live.py <사이트 주소>` (토큰 없는 요청의 401, 화면이 보내는 헤더, 페이지 오류)
- 모델까지 가는 경로: `kubectl -n app exec -i <BFF 파드> -- python - < bench/bff/lang_check_in_pod.py` (비밀번호 없이 확인. 잠든 Qwen을 깨우지 않으려면 이름을 인자로 줍니다)
- 로그인한 브라우저로 하는 확인에는 데모 계정 비밀번호가 필요합니다. 사용자에게 받아 명령의 환경 변수로만 넘기고 어디에도 남기지 않습니다

## 5단계: 보고

- 배포한 것(이미지 태그, S3 객체 수)과 확인한 결과
- 확인하지 않은 것과 그 이유
- 고친 문서(`docs/07-bff.md` 등)

## 막혔을 때

### diff나 plan이 예상과 다를 때
적용하지 않습니다. 차이를 그대로 보여 주고 원인을 확인합니다(다른 주체가 클러스터를 바꿨는지는 CloudTrail의 `CreateAddon` 같은 기록으로 봅니다).

### 롤아웃이 끝나지 않을 때
`kubectl -n app describe pod`과 `kubectl -n app logs`로 원인을 봅니다. 이전 이미지로 되돌리려면 `bff.auto.tfvars`의 태그를 되돌리고 diff부터 다시 합니다.

### 계획 파일이 낡았을 때 ("Saved plan is stale")
plan을 다시 만들고 요약을 다시 보여 줍니다.
