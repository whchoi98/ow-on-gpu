// "구축 과정" 보기의 내용. 이 환경을 만든 열 단계(prompts.md의 0~9단계)와 측정에서 확인한 주요 내용이다.
// 화면과 무관한 자료만 둔다.
//
// 수치는 2026-11-14와 2026-11-15에 서울 리전에서 잰 값이고, 단계마다 적은 문서에서 옮겼다.
//   0단계  docs/00-versions.md           5단계  docs/05-decider.md
//   2단계  jobs/model-sync/README.md     6단계  docs/06-sleep.md
//   3단계  docs/03-vllm.md               7단계  docs/07-bff.md
//   4단계  docs/04-gateway.md            8단계  docs/08-results.md, 웹 검색은 docs/10-web-search.md
// 9단계(정리)는 아직 하지 않았다. 계획만 적고 명령, 수치, 기록 문서는 넣지 않는다.
import { localized, tr } from './i18n.js';

// tools: 그 단계에서 쓴 도구. status: done(끝남), todo(남음)
export const DEPLOY = localized(() => ({
  lede: tr(
    '이 환경은 열 단계로 만들었습니다. VPC는 AWS CDK로, EKS와 CloudFront, AWS WAF, Cognito는 Terraform으로, BFF를 포함한 클러스터 안의 ' +
      '리소스는 kubectl과 Helm으로 적용했습니다. 단계마다 terraform plan이나 kubectl diff를 먼저 확인한 뒤 적용했고, 플래그와 필드 이름은 ' +
      '실제 설치 버전에서 확인했습니다.',
    'This environment was built in ten steps. The VPC comes from AWS CDK, EKS, CloudFront, AWS WAF, and Cognito from Terraform, and ' +
      'in-cluster resources, including the BFF, from kubectl and Helm. Each step was applied only after reviewing terraform plan or ' +
      'kubectl diff, and flags and field names were checked against the installed versions.',
  ),
  facts: [
    [tr('리전', 'Region'), tr('서울 (ap-northeast-2)', 'Seoul (ap-northeast-2)')],
    [tr('GPU 노드', 'GPU nodes'), tr('g6e.4xlarge 2대, g6e.xlarge 1대', '2 x g6e.4xlarge, 1 x g6e.xlarge')],
    [tr('모델', 'Models'), 'Gemma 4 31B, Qwen3.8-27B (FP8), Decider 12B'],
    [tr('추론 엔진', 'Inference engine'), 'vLLM v0.33.0'],
    [tr('클러스터', 'Cluster'), 'EKS 1.37, Karpenter 1.15'],
    [tr('게이트웨이', 'Gateway'), 'GAIE v1.6.2, agentgateway v1.7.0'],
    [tr('고정 비용', 'Fixed cost'), tr('시간당 약 11.35달러', 'about 11.35 USD per hour')],
  ],
  steps: [
    {
      n: 0,
      status: 'done',
      title: tr('사전 확인', 'Preflight'),
      tools: [tr('읽기 전용 조회', 'Read-only queries')],
      text: tr(
        '리소스를 만들기 전에 버전 조합, 체크포인트, 서비스 할당량을 확인했습니다. 이 단계에서는 아무것도 만들지 않았습니다.',
        'Before creating anything, we checked the version matrix, the checkpoints, and the service quotas. Nothing was created in this step.',
      ),
      points: [
        tr(
          '구성 요소는 배포 시점의 최신 버전을 쓰되 서로의 지원 범위 안에서 맞췄습니다. 최신을 쓰지 않은 것은 Gateway API CRD 하나입니다(v1.7.0 대신 v1.6.3).',
          'Every component uses the latest version available at deploy time, within what the others support. The one exception is the Gateway API CRD (v1.6.3 instead of v1.7.0).',
        ),
        tr(
          'L40S(Ada)에는 vLLM 문서가 Ada 지원을 명시한 FP8 체크포인트를 골랐습니다. Qwen은 공식 block FP8 대신 per-channel FP8-dynamic을 씁니다. block FP8의 CUTLASS 커널은 SM 9.0 이상에서만 지원됩니다.',
          'For the L40S (Ada), we chose FP8 checkpoints, which the vLLM docs list as supported on Ada. Qwen uses per-channel FP8-dynamic instead of the official block FP8, whose CUTLASS kernel is supported only on SM 9.0 and later.',
        ),
        tr(
          'G 계열 On-Demand 할당량은 768 vCPU이고 이 구성은 36 vCPU를 씁니다. g6e.4xlarge는 서울의 2a와 2b에서만 제공됩니다.',
          'The On-Demand quota for G instances is 768 vCPU and this setup uses 36. In Seoul, g6e.4xlarge is offered only in 2a and 2b.',
        ),
      ],
      command: 'aws service-quotas list-service-quotas --service-code ec2 --region ap-northeast-2',
      rows: [
        [tr('클러스터', 'Cluster'), 'EKS 1.37, Karpenter v1.15.2'],
        [tr('게이트웨이 계층', 'Gateway layer'), 'Gateway API v1.6.3, GAIE v1.6.2, llm-d-router v1.0.0'],
        [tr('추론 엔진', 'Inference engine'), 'vLLM v0.33.0 (CUDA 13.0.2)'],
      ],
      doc: 'docs/00-versions.md',
    },
    {
      n: 1,
      status: 'done',
      title: tr('네트워크와 EKS 기반', 'Network and EKS base'),
      tools: ['AWS CDK', 'Terraform', 'kubectl'],
      text: tr(
        'VPC는 CDK 스택 EksVpcStack으로 만들고, EKS, Karpenter, AWS Load Balancer Controller, 모델 버킷, Pod Identity 역할은 Terraform으로 만들었습니다.',
        'The VPC comes from the CDK stack EksVpcStack. EKS, Karpenter, the AWS Load Balancer Controller, the model bucket, and the Pod Identity roles come from Terraform.',
      ),
      points: [
        tr(
          'VPC는 10.200.0.0/16이고 4개 AZ에 Public, Private, Isolated 서브넷을 둡니다. 워크로드는 Private 서브넷에서 실행합니다.',
          'The VPC is 10.200.0.0/16 with public, private, and isolated subnets in four AZs. Workloads run in the private subnets.',
        ),
        tr(
          'NodePool은 gemma-od, qwen-od(g6e.4xlarge), decider(g6e.xlarge), system(CPU)입니다. GPU NodePool에는 taint를 두고 GPU 1장까지만 허용합니다.',
          'NodePools: gemma-od and qwen-od (g6e.4xlarge), decider (g6e.xlarge), and system (CPU). GPU NodePools are tainted and limited to one GPU each.',
        ),
        tr(
          'EC2NodeClass는 NVIDIA 드라이버가 든 EKS 최적화 AMI를 쓰고, userData로 vLLM 이미지를 미리 받고, 로컬 NVMe를 인스턴스 스토어로 씁니다.',
          'The EC2NodeClass uses the EKS optimized AMI with NVIDIA drivers, pre-pulls the vLLM image in userData, and uses local NVMe as instance store.',
        ),
        tr(
          '서빙 파드에는 읽기 전용 역할을, 적재와 캐시 게시 Job에는 쓰기 역할을 EKS Pod Identity로 연결했습니다. 자격 증명을 매니페스트에 넣지 않습니다.',
          'Serving pods get a read-only role and the sync and cache-publish Jobs get a write role through EKS Pod Identity. No credentials are stored in manifests.',
        ),
      ],
      command:
        '(cd infra/cdk-vpc && npx cdk deploy)\n' +
        'terraform -chdir=infra/terraform plan\n' +
        'terraform -chdir=infra/terraform apply\n' +
        'kubectl apply -k k8s/base',
      rows: [
        ['VPC', tr('10.200.0.0/16, AZ 4개', '10.200.0.0/16, 4 AZs')],
        [tr('애드온용 노드', 'Add-on nodes'), tr('m7g.large 2대', '2 x m7g.large')],
        [tr('GPU 노드', 'GPU nodes'), tr('g6e.4xlarge 2대, g6e.xlarge 1대', '2 x g6e.4xlarge, 1 x g6e.xlarge')],
      ],
      doc: 'infra/cdk-vpc, infra/terraform, k8s/base',
    },
    {
      n: 2,
      status: 'done',
      title: tr('모델 적재', 'Model sync'),
      tools: ['kubectl', 'Job'],
      text: tr(
        '적재 Job이 Hugging Face의 체크포인트를 받는 대로 s5cmd로 S3에 올립니다. 한 번만 실행하고, 그 뒤로 서빙 파드는 S3에서만 읽습니다.',
        'A sync Job streams the Hugging Face checkpoints to S3 with s5cmd as it downloads them. It runs once, and serving pods read only from S3 afterward.',
      ),
      points: [
        tr(
          '저장소 세 개를 리비전 해시로 고정했습니다. Gemma, Qwen, Decider입니다. Decider v2는 기반 모델이 따로 없습니다.',
          'Three repositories are pinned by revision hash: Gemma, Qwen, and Decider. Decider v2 needs no separate base model.',
        ),
        tr(
          '받으면서 해시를 계산해 Hugging Face가 알려 준 값과 비교하고, 끝나면 S3의 객체 목록을 기대값과 비교합니다.',
          'Hashes are computed during download and compared with the values from Hugging Face, and the S3 listing is checked against the expected objects at the end.',
        ),
        tr(
          '가중치를 로컬 디스크에 쌓지 않습니다. 파일 8개를 동시에 처리합니다.',
          'Weights are never staged on local disk. Eight files are processed at a time.',
        ),
      ],
      command: 'kubectl apply -k jobs/model-sync\nkubectl -n model-jobs logs -f job/model-sync',
      rows: [
        [tr('처음 올린 양 (2026-11-14)', 'First upload (2026-11-14)'), tr('모델 4종, 객체 73개, 69.8GiB', '4 models, 73 objects, 69.8GiB')],
        [tr('걸린 시간', 'Duration'), tr('491초', '491s')],
        [tr('Decider v2 추가 (2026-11-24)', 'Decider v2 added (2026-11-24)'), tr('객체 13개, 22.3GiB, 315초', '13 objects, 22.3GiB, 315s')],
      ],
      doc: 'jobs/model-sync/README.md',
    },
    {
      n: 3,
      status: 'done',
      title: tr('vLLM 배포', 'vLLM deployment'),
      tools: ['kubectl'],
      text: tr(
        'Gemma와 Qwen을 g6e.4xlarge 노드에 한 대씩 올렸습니다. 가중치는 runai_streamer로 S3에서 직접 읽고, compile 캐시는 S3에서 복원합니다.',
        'Gemma and Qwen each run on their own g6e.4xlarge node. Weights are read straight from S3 with runai_streamer, and the compile cache is restored from S3.',
      ),
      points: [
        tr(
          '플래그는 v0.33.0 이미지 안에서 vllm serve --help로 확인한 뒤 썼습니다.',
          'Flags were checked with vllm serve --help inside the v0.33.0 image before use.',
        ),
        tr(
          'Qwen은 --gpu-memory-utilization 0.85에서 KV 캐시가 0.24GiB만 남아 시작하지 못했고 0.90에서 시작했습니다.',
          'Qwen failed to start at --gpu-memory-utilization 0.85, which left only 0.24GiB for the KV cache, and started at 0.90.',
        ),
        tr(
          'initContainer가 S3의 compile 캐시를 노드의 hostPath로 내려받습니다. 첫 기동 뒤에는 캐시 게시 Job이 캐시를 S3에 올립니다.',
          'An initContainer downloads the compile cache from S3 to a hostPath on the node. After the first start, a cache-publish Job uploads the cache to S3.',
        ),
        tr(
          'Qwen은 sleep mode를 켜고 readinessProbe로 /is_sleeping을 확인합니다. /health는 잠든 동안에도 200을 돌려주기 때문입니다.',
          'Qwen runs with sleep mode on, and its readinessProbe checks /is_sleeping because /health still returns 200 while asleep.',
        ),
      ],
      command: 'kubectl diff -k k8s/gemma\nkubectl apply -k k8s/gemma\nkubectl apply -k k8s/qwen\nkubectl apply -k jobs/cache-publish',
      rows: [
        [tr('가중치 로드', 'Weight load'), tr('Gemma 19.1초, Qwen 34.3초', 'Gemma 19.1s, Qwen 34.3s')],
        [tr('가중치의 GPU 메모리', 'GPU memory for weights'), 'Gemma 30.63GiB, Qwen 34.39GiB'],
        [tr('KV 캐시', 'KV cache'), tr('Gemma 5.37GiB (34,052토큰), Qwen 2.46GiB (42,780토큰)', 'Gemma 5.37GiB (34,052 tokens), Qwen 2.46GiB (42,780 tokens)')],
      ],
      doc: 'docs/03-vllm.md',
    },
    {
      n: 4,
      status: 'done',
      title: tr('GAIE와 게이트웨이', 'GAIE and gateway'),
      tools: ['kubectl', 'Helm'],
      text: tr(
        '요청 본문의 model 값으로 모델별 InferencePool을 고르는 게이트웨이 계층을 설치했습니다.',
        'We installed the gateway layer that picks a per-model InferencePool from the model value in the request body.',
      ),
      points: [
        tr(
          'agentgateway가 본문의 model 값을 헤더로 옮기고 HTTPRoute가 그 헤더로 풀을 고릅니다. 별도의 ext-proc 배포가 필요 없습니다.',
          'agentgateway copies the model value from the body into a header, and the HTTPRoute matches on it. No separate ext-proc deployment is needed.',
        ),
        tr(
          'HTTPRoute에는 /v1/chat/completions와 /v1/models만 등록했습니다. /sleep과 /wake_up은 게이트웨이로 노출되지 않습니다.',
          'The HTTPRoutes list only /v1/chat/completions and /v1/models, so /sleep and /wake_up are not reachable through the gateway.',
        ),
        tr(
          'InferenceObjective는 풀마다 두 개입니다. interactive는 priority 10, batch는 priority -1입니다.',
          'Each pool has two InferenceObjectives: interactive at priority 10 and batch at priority -1.',
        ),
        tr(
          '게이트웨이 Service는 내부 NLB(IP 대상)에 연결됩니다. 이 NLB는 배치 클라이언트만 쓰고 BFF는 Service를 직접 부릅니다. 게이트웨이 파드 2개와 EPP 파드 4개는 system 노드에서 실행합니다.',
          'The gateway Service sits behind an internal NLB with IP targets. Only the batch client uses this NLB, and the BFF calls the Service directly. Two gateway pods and four EPP pods run on system nodes.',
        ),
      ],
      command: 'k8s/gateway/install.sh render | kubectl diff -f -\nk8s/gateway/install.sh apply',
      rows: [
        [tr('설치에 걸린 시간', 'Install time'), tr('72초', '72s')],
        [tr('버전', 'Versions'), 'agentgateway v1.7.0, llm-d-router v1.0.0'],
      ],
      doc: 'docs/04-gateway.md',
    },
    {
      n: 5,
      status: 'done',
      title: 'Strands Decider 12B',
      tools: ['kubectl'],
      text: tr(
        '업무 종류가 없는 요청의 모델을 고르는 Decider 12B(v2)를 g6e.xlarge 노드에 올렸습니다. 2026-11-24에 v1의 Decider 2B(g6.xlarge)에서 바꿨습니다.',
        'Decider 12B (v2), which picks the model for requests that carry no task type, runs on a g6e.xlarge node. It replaced the v1 Decider 2B (g6.xlarge) on 2026-11-24.',
      ),
      points: [
        tr(
          'strands-decider 저장소 v0.4.0의 Dockerfile로 이미지를 빌드했습니다. 공개 서빙 이미지에는 v2 체크포인트를 읽는 버전이 아직 없습니다.',
          'The image is built from the Dockerfile of the strands-decider repository at v0.4.0. The public serving image does not yet carry a version that reads v2 checkpoints.',
        ),
        tr(
          '가중치 24GB는 S3에서 받고, HF_HUB_OFFLINE=1로 Hugging Face 접근을 막았습니다.',
          'The 24 GB of weights come from S3, and HF_HUB_OFFLINE=1 blocks access to Hugging Face.',
        ),
        tr(
          '예열이 끝날 때까지 /health가 실패하므로 파드는 예열 뒤에 Ready가 됩니다. 컨테이너 시작부터 Ready까지 43초 걸렸습니다.',
          '/health fails until warm-up finishes, so the pod becomes Ready only after warm-up. It took 43s from container start to Ready.',
        ),
        tr(
          '게이트웨이의 /decide가 경로를 /v1/systemone으로 바꿔 보냅니다. InferencePool은 쓰지 않습니다.',
          'The gateway route /decide rewrites the path to /v1/systemone. No InferencePool is used.',
        ),
      ],
      command: 'k8s/decider/install.sh build\nk8s/decider/install.sh apply',
      rows: [
        [tr('판단 1회 (게이트웨이 경유, 중앙값)', 'One decision (via gateway, median)'), '89.7~90.6ms'],
        [tr('BFF의 판단 요청 왕복 (20건)', 'Round trip of the BFF decision request (20 requests)'), '143.8~159.9ms'],
      ],
      doc: 'docs/05-decider.md',
    },
    {
      n: 6,
      status: 'done',
      title: tr('sleep 컨트롤러', 'Sleep controller'),
      tools: ['kubectl'],
      text: tr(
        '업무 시간 외에 Qwen을 재우고 필요할 때 깨우는 구성을 넣었습니다.',
        'This step adds what puts Qwen to sleep outside business hours and wakes it on demand.',
      ),
      points: [
        tr(
          'CronJob 두 개가 평일 19:00에 재우고 08:30에 깨웁니다(Asia/Seoul). 진행 중인 요청이 끝난 뒤에 잠들게 합니다.',
          'Two CronJobs put it to sleep at 19:00 and wake it at 08:30 on weekdays (Asia/Seoul). It goes to sleep only after in-flight requests finish.',
        ),
        tr(
          '깨우기 API는 POST /wake만 제공하고 HTTPRoute에 등록하지 않았습니다. BFF는 클러스터 안의 Service로 직접 부르고 NetworkPolicy가 BFF 파드와 ow-on-gpu/wake-client 라벨이 붙은 파드만 허용합니다.',
          'The wake API serves only POST /wake and is not registered in any HTTPRoute. The BFF calls it directly through its in-cluster Service, and a NetworkPolicy allows only BFF pods and pods labeled ow-on-gpu/wake-client.',
        ),
        tr(
          'NetworkPolicy로 Qwen의 8000 포트에 게이트웨이, EPP, 깨우기 API만 허용합니다. VPC CNI의 enableNetworkPolicy를 켜야 적용됩니다.',
          'A NetworkPolicy allows only the gateway, EPP, and wake API to reach Qwen on port 8000. It takes effect only with enableNetworkPolicy turned on in the VPC CNI.',
        ),
      ],
      command: 'kubectl apply -k k8s/sleep-controller',
      rows: [
        [tr('sleep 진입', 'Enter sleep'), tr('2.98초', '2.98s')],
        [tr('복귀 (깨우기 API 응답까지)', 'Wake (until the wake API responds)'), tr('3.66초', '3.66s')],
        [tr('그 뒤 게이트웨이 요청이 성공하기까지', 'Then until a gateway request succeeds'), tr('1.3~1.4초', '1.3~1.4s')],
      ],
      doc: 'docs/06-sleep.md',
    },
    {
      n: 7,
      status: 'done',
      title: tr('앱 계층', 'App layer'),
      tools: ['Terraform', 'kubectl', 'Docker'],
      text: tr(
        'BFF(EKS 파드), 내부 ALB, CloudFront, AWS WAF, Cognito 로그인을 만들었습니다. 지금 보고 있는 이 페이지도 이 단계에서 올렸습니다. ' +
          'BFF는 처음에 ECS Fargate로 만들었고 2026년 11월 15일에 EKS 파드로 옮겼습니다.',
        'This step creates the BFF (EKS pods), the internal ALB, CloudFront, AWS WAF, and the Cognito sign-in. The page you are reading was deployed here too. ' +
          'The BFF was first built on ECS Fargate and moved to EKS pods on November 15, 2026.',
      ),
      points: [
        tr(
          '요청은 CloudFront, 내부 ALB, BFF, 게이트웨이 순서로 갑니다. ALB는 CloudFront VPC origin만 허용하고 BFF는 클러스터 안의 Service로 게이트웨이를 직접 부릅니다.',
          'Requests go through CloudFront, the internal ALB, the BFF, and the gateway. The ALB accepts only the CloudFront VPC origin, and the BFF calls the gateway directly through its in-cluster Service.',
        ),
        tr(
          'BFF는 네임스페이스 app의 파드 2개이고 AZ 두 곳에 나눠 둡니다. Karpenter NodePool app이 Graviton On-Demand 노드(c7g.large) 2대를 띄웁니다. ' +
            'BFF의 AWS 권한은 EKS Pod Identity로 연결한 역할 하나이고 웹 검색 호출만 허용합니다.',
          'The BFF runs as 2 pods in the app namespace, spread across two AZs. The Karpenter NodePool app brings up 2 Graviton On-Demand nodes (c7g.large). ' +
            'The only AWS permission of the BFF is one role attached through EKS Pod Identity, and it allows only the web search call.',
        ),
        tr(
          '내부 ALB는 AWS Load Balancer Controller가 Ingress에서 만듭니다. 그래서 Terraform으로 IAM 역할과 Pod Identity 연결을 먼저 만들고 ' +
            'k8s/bff/install.sh로 NodePool, 파드, Ingress를 적용합니다. 그 뒤에 Terraform이 그 ALB를 조회해 CloudFront에 연결합니다.',
          'The AWS Load Balancer Controller creates the internal ALB from an Ingress. So Terraform first creates the IAM role and the Pod Identity association, ' +
            'and k8s/bff/install.sh applies the NodePool, the pods, and the Ingress. Terraform then looks up that ALB and connects it to CloudFront.',
        ),
        tr(
          'BFF는 민감 정보 규칙, 업무 종류, 첨부, Decider, 기본값 순서로 모델을 정합니다.',
          'The BFF picks the model in this order: sensitive data rule, task type, attachment, Decider, default.',
        ),
        tr(
          'Qwen으로 갈 요청은 깨우기 API를 먼저 부릅니다. SSE 응답은 받은 Chunk 그대로 흘려보냅니다.',
          'Requests bound for Qwen call the wake API first. SSE responses are relayed chunk by chunk as they arrive.',
        ),
        tr(
          '가입은 막아 두었고 사용자는 스크립트로 만듭니다. 비밀번호는 코드와 Terraform state에 두지 않습니다.',
          'Sign-up is disabled and users are created by a script. Passwords are never stored in code or Terraform state.',
        ),
      ],
      command:
        'app/bff/build.sh\n' +
        'app/web/build.sh\n' +
        'terraform -chdir=infra/terraform plan\n' +
        'terraform -chdir=infra/terraform apply\n' +
        'k8s/bff/install.sh diff\n' +
        'k8s/bff/install.sh apply\n' +
        'terraform -chdir=infra/terraform apply\n' +
        tr('app/bff/create-user.sh <이메일>', 'app/bff/create-user.sh <email>'),
      rows: [
        [tr('처음 적용에서 만든 리소스 (Fargate 구성)', 'Resources in the first apply (Fargate setup)'), tr('33개', '33')],
        [tr('BFF 파드와 노드', 'BFF pods and nodes'), tr('파드 2개, c7g.large 2대', '2 pods, 2 x c7g.large')],
        [tr('WAF 한도', 'WAF limit'), tr('IP당 5분 300회', '300 requests per 5 min per IP')],
        [tr('앱 계층 고정 비용', 'App layer fixed cost'), tr('시간당 0.1857달러', '0.1857 USD per hour')],
      ],
      doc: 'docs/07-bff.md',
    },
    {
      n: 8,
      status: 'done',
      title: tr('관측과 측정', 'Observability and measurement'),
      tools: ['kubectl', 'Python'],
      text: tr(
        '지표를 Amazon Managed Service for Prometheus로 모으고 네 가지 측정을 실행했습니다.',
        'Metrics go to Amazon Managed Service for Prometheus, and four measurements were run.',
      ),
      points: [
        tr(
          'Prometheus agent 하나가 vLLM, EPP, 게이트웨이 파드 8개를 수집해 AMP로 보냅니다. 대시보드는 패널 15개입니다.',
          'One Prometheus agent scrapes eight vLLM, EPP, and gateway pods and writes to AMP. The dashboard has 15 panels.',
        ),
        tr(
          '측정은 콜드 스타트 구간 분해, 구간별 TTFT, SLO 하 처리량, 우선순위 효과입니다.',
          'The measurements are the cold start breakdown, per-segment TTFT, throughput under the SLO, and the effect of priority.',
        ),
        tr(
          '부하 발생기는 측정 전용 NodePool에서 Job으로 실행합니다. 원시 데이터는 results/에 그대로 둡니다.',
          'The load generator runs as a Job on a dedicated bench NodePool. Raw data is kept as is under results/.',
        ),
      ],
      command:
        'kubectl apply -k k8s/observability\n' +
        'python3 bench/coldstart/measure.py --model gemma --scenario cold-optimized --out results/2026-11-14-coldstart\n' +
        'python3 bench/job.py --name slo-gemma --service-account gemma --out results/2026-11-14-slo/gemma \\\n' +
        '  --env MODEL_NAME=gemma-4-31b --env MODEL_DIR=gemma-4-31B-it-FP8-dynamic \\\n' +
        '  --env BASE_URL=http://vllm-gemma.inference.svc:8000 -- bash /bench/run-bench.sh',
      rows: [
        [tr('Gemma 콜드 스타트', 'Gemma cold start'), tr('394초에서 260초', '394s to 260s')],
        [tr('사용자가 본 첫 내용', 'First content seen by the user'), 'Gemma 81.9ms, Qwen 177.5ms'],
        [tr('배치 부하 중 상담 TTFT p50', 'Support TTFT p50 under batch load'), tr('30.9초에서 0.19초', '30.9s to 0.19s')],
      ],
      doc: 'docs/08-results.md',
    },
    {
      n: 9,
      status: 'todo',
      title: tr('정리', 'Cleanup'),
      tools: [tr('스크립트', 'Script'), 'Terraform', 'AWS CDK'],
      text: tr(
        '전체 리소스를 만든 순서의 반대로 지우는 단계입니다. 아직 실행하지 않았고, 아래는 계획입니다.',
        'This step deletes everything in reverse order of creation. It has not been run yet, and the items below are the plan.',
      ),
      points: [
        tr(
          'GPU 노드가 먼저 사라지도록 Deployment와 NodePool을 지운 뒤 terraform destroy를 실행합니다.',
          'Delete the Deployments and NodePools first so the GPU nodes go away, then run terraform destroy.',
        ),
        tr(
          'S3의 models와 vllm-cache는 기본으로 남기고, 별도 플래그를 줬을 때만 지웁니다.',
          'Keep models and vllm-cache in S3 by default, and delete them only with an explicit flag.',
        ),
        tr(
          '지운 뒤 남은 EC2, NLB, ALB, CloudFront 리소스를 조회해 확인합니다. VPC는 CDK 스택이라 따로 지웁니다.',
          'Afterward, list any remaining EC2, NLB, ALB, and CloudFront resources. The VPC is a CDK stack and is destroyed separately.',
        ),
      ],
      command: '',
      rows: [],
      doc: '',
    },
  ],
  // 측정에서 확인한 주요 내용. value는 한눈에 보이는 수치, text는 그 수치의 뜻이다.
  findings: [
    {
      title: tr('콜드 스타트는 구간마다 따로 줄였습니다', 'Cold start was cut segment by segment'),
      value: tr('394초에서 260초', '394s to 260s'),
      text: tr(
        'Gemma의 콜드 스타트가 34%, 웜 재시작이 214초에서 86초로 60% 줄었습니다. 이미지 사전 pull로 111.1초를 71.0초로, runai_streamer로 ' +
          '가중치 로드 59.6초를 19.2초로, compile 캐시 복원으로 엔진 초기화 95.5초를 23.7초로 줄였습니다.',
        'Gemma cold start dropped 34%, and warm restart dropped 60% from 214s to 86s. Image pre-pull cut 111.1s to 71.0s, runai_streamer cut ' +
          'weight load from 59.6s to 19.2s, and compile cache restore cut engine init from 95.5s to 23.7s.',
      ),
      doc: 'docs/08-results.md',
    },
    {
      title: tr('첫 내용까지의 시간은 대부분 vLLM입니다', 'Most of the time to first content is vLLM'),
      value: 'Gemma 81.9ms, Qwen 177.5ms',
      text: tr(
        '사용자가 본 첫 내용까지의 시간 중 vLLM의 TTFT가 63.2ms와 147.6ms로 77%와 83%입니다. vLLM 앞의 구간(엣지까지, CloudFront, 내부 ALB, ' +
          'BFF, 게이트웨이)의 중앙값을 더하면 Gemma 18.2ms, Qwen 29.7ms입니다.',
        'Of the time to first content seen by the user, vLLM TTFT is 63.2ms and 147.6ms, or 77% and 83%. The medians of the segments before vLLM ' +
          '(to the edge, CloudFront, the internal ALB, the BFF, and the gateway) add up to 18.2ms for Gemma and 29.7ms for Qwen.',
      ),
      doc: 'docs/08-results.md',
    },
    {
      title: tr('L40S의 Gemma는 ITL 기준을 넘습니다', 'Gemma on the L40S misses the ITL target'),
      value: tr('토큰 간격 54ms', '54ms between tokens'),
      text: tr(
        'SLO는 TTFT p99 500ms와 ITL p99 50ms를 함께 만족하는 것입니다. Gemma FP8-dynamic은 토큰 간격이 54ms여서 동시성 1에서도 ' +
          'ITL 기준을 넘고, 두 기준을 함께 만족하는 동시성이 없었습니다.',
        'The SLO is TTFT p99 of 500ms together with ITL p99 of 50ms. Gemma FP8-dynamic takes 54ms between tokens, so it misses the ITL ' +
          'target even at concurrency 1, and no concurrency level met both.',
      ),
      doc: 'docs/08-results.md',
    },
    {
      title: tr('Qwen의 동시 3건 한도는 MTP 때문입니다', 'The 3-request limit on Qwen comes from MTP'),
      value: tr('동시 3건, MTP를 끄면 20건', '3 concurrent, 20 without MTP'),
      text: tr(
        'MTP의 추측 토큰 3개가 요청마다 상태 블록을 4배로 잡습니다. MTP를 끄면 최대 처리량이 초당 91.2토큰에서 281.8토큰이 되지만 ' +
          '요청 하나의 속도는 초당 32.5토큰에서 19.2토큰으로 줄어듭니다.',
        'The three speculative tokens of MTP make each request hold four times the state blocks. Without MTP, peak throughput rises from 91.2 ' +
          'to 281.8 tokens/s, but a single request slows from 32.5 to 19.2 tokens/s.',
      ),
      doc: 'docs/08-results.md',
    },
    {
      title: tr('상담 요청은 엔진 우선순위가 지킵니다', 'Engine priority protects support requests'),
      value: tr('30.9초에서 0.19초', '30.9s to 0.19s'),
      text: tr(
        '배치 부하를 걸었을 때 상담 요청의 TTFT 중앙값입니다. vLLM의 priority 스케줄링을 켜면 0.19초가 됩니다. 게이트웨이의 ' +
          'InferenceObjective는 배치를 거절해 대기열을 줄이는 역할을 했습니다.',
        'This is the median TTFT of support requests under batch load. Turning on priority scheduling in vLLM brings it to 0.19s. ' +
          'The InferenceObjective at the gateway rejected batch requests and so kept the queue short.',
      ),
      doc: 'docs/08-results.md',
    },
    {
      title: tr('잠든 Qwen은 3.7초 만에 돌아옵니다', 'Sleeping Qwen is back in 3.7s'),
      value: tr('복귀 3.7초', '3.7s to wake'),
      text: tr(
        '같은 노드에서 파드를 다시 띄우면 123초, 노드부터 새로 띄우면 290초가 걸립니다. level 1 sleep은 가중치를 호스트 메모리에 두기 ' +
          '때문에 다시 읽지 않습니다.',
        'Restarting the pod on the same node takes 123s, and starting from a new node takes 290s. Level 1 sleep keeps the weights in host ' +
          'memory, so they are not read again.',
      ),
      doc: 'docs/06-sleep.md',
    },
    {
      title: tr('웹 검색은 검색만 밖에서 합니다', 'Web search runs only the search outside'),
      value: tr('검색 1회 485~662ms', '485~662ms per search'),
      text: tr(
        '추론은 Gemma와 Qwen이 하고, 검색만 Amazon Bedrock AgentCore Web Search(us-east-1)가 합니다. BFF가 잰 검색 시간은 요청 8건에서 ' +
          '중앙값 568ms였습니다. 민감 정보가 든 요청에는 검색 도구를 붙이지 않습니다.',
        'Gemma and Qwen do the inference, and only the search goes to Amazon Bedrock AgentCore Web Search (us-east-1). Search time measured ' +
          'by the BFF had a median of 568ms over 8 requests. Requests with sensitive data never get the search tool.',
      ),
      doc: 'docs/10-web-search.md',
    },
  ],
}));
