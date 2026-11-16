// 모델을 올려 서빙하기까지의 여섯 단계. 흐름 그림 아래의 띠가 이 목록을 보여 주고,
// 띠에서 단계를 고르면 그 단계에서 움직이는 구성 요소를 그림(flow-map.svg)에서 켠다. 화면과 무관한 자료와 순수 함수만 둔다.
//
// 수치는 2026-11-14에 이 환경에서 시나리오마다 한 번 잰 값이다.
//   1~4번: docs/08-results.md 1절 "콜드 스타트 구간 분해"의 Gemma, Qwen 구간 표
//   5번:   docs/08-results.md 2절 "구간별 TTFT"의 표(요청 1건씩 20건의 중앙값)
//   0번:   results/2026-11-14-model-sync/summary.jsonl
//   웹 검색: docs/10-web-search.md (작업 장비에서 us-east-1의 InvokeWebSearch를 6회 부른 시간. 배포 뒤 BFF가 잰 값은 요청 8건에서 485~662ms)
import { localized, tr } from './i18n.js';

// 그림의 노드와 선. docs/infographic/flow.py의 NODES, layout()과 같은 이름이다.
export const MAP_NODES = [
  'user', 'cf', 'alb', 'bff', 'gw', 'gemma', 'cache', 'qwen', 'cognito', 'search', 'decider', 'pages', 'wake',
  'registry', 's3', 'identity', 'hf', 'sync', 'amp', 'karpenter',
];
export const MAP_EDGES = [
  'user-cf', 'cf-alb', 'alb-bff', 'bff-gw', 'gw-gemma', 'gw-qwen', 'gw-decider', 'bff-wake', 'wake-qwen',
  'user-cognito', 'bff-cognito', 'bff-search', 'cf-pages',
  'hf-sync', 'sync-s3', 'karpenter-gpu', 'registry-gpu', 's3-gemma', 's3-cache', 's3-qwen', 'cache-gemma', 'cache-qwen',
  'identity-s3', 'gw-amp', 'gpu-amp',
];
// GPU 노드 틀(n-gpu) 안에 그린 노드
const IN_GPU = ['gemma', 'cache', 'qwen'];

// tone: load(한 번 하는 준비), boot(파드가 뜰 때마다 거치는 구간), serve(요청)
// values는 그림의 노드 칸에 써넣는 값이라 칸의 폭(영어 약 18자)을 넘지 않게 쓴다.
export const STEPS = localized(() => [
  {
    n: 0,
    title: tr('모델 적재', 'Model sync'),
    value: tr('4종 69.8GiB, 491초', '4 models 69.8GiB, 491s'),
    tone: 'load',
    nodes: ['hf', 'sync', 's3', 'identity'],
    edges: ['hf-sync', 'sync-s3', 'identity-s3'],
    values: { sync: tr('491초, 1회', '491s, once'), s3: tr('4종 69.8GiB', '4 models 69.8GiB') },
    text: tr(
      '모델 적재 Job(model-sync)이 Hugging Face의 체크포인트를 받는 대로 s5cmd로 모델 버킷에 올리고 파일마다 해시를 확인합니다. ' +
        '처음 한 번만 실행합니다. 그 뒤로 서빙 파드는 Hugging Face가 아닌 S3에서만 읽습니다.',
      'The model sync Job (model-sync) streams the Hugging Face checkpoints to the model bucket with s5cmd as it downloads them and ' +
        'checks the hash of every file. It runs only once. After that, serving pods read from S3 and never from Hugging Face.',
    ),
    rows: [
      [tr('모델 4종, 객체 73개', '4 models, 73 objects'), '69.8GiB'],
      [tr('적재에 걸린 시간', 'Sync duration'), tr('491초', '491s')],
    ],
    note: tr('2026년 11월 14일에 한 번 실행한 결과입니다.', 'From a single run on November 14, 2026.'),
  },
  {
    n: 1,
    title: tr('노드 프로비저닝', 'Node provisioning'),
    value: tr('55.0~71.0초', '55.0~71.0s'),
    tone: 'boot',
    nodes: ['karpenter', 'gpu'],
    edges: ['karpenter-gpu'],
    values: {},
    text: tr(
      '서빙 파드가 자리를 기다리면 Karpenter가 NodePool(gemma-od, qwen-od)의 조건에 맞는 g6e.4xlarge On-Demand 노드를 만듭니다. ' +
        'NodePool마다 GPU 1장까지만 허용합니다. NodeClaim 생성부터 노드 Ready까지를 쟀습니다.',
      'When a serving pod is pending, Karpenter creates a g6e.4xlarge On-Demand node that matches the NodePool (gemma-od, qwen-od). ' +
        'Each NodePool allows one GPU at most. The time is from NodeClaim creation to node Ready.',
    ),
    rows: [
      [tr('Gemma, 콜드 기준 구성', 'Gemma, cold baseline'), tr('55.0초', '55.0s')],
      [tr('Gemma, 콜드 최적화 구성', 'Gemma, cold optimized'), tr('71.0초', '71.0s')],
      [tr('Qwen, 콜드 최적화 구성', 'Qwen, cold optimized'), tr('63.0초', '63.0s')],
    ],
    note: tr('콜드 스타트를 시나리오마다 한 번 잰 값입니다.', 'Each cold start scenario was measured once.'),
  },
  {
    n: 2,
    title: tr('이미지 pull', 'Image pull'),
    value: tr('111.1초에서 71.0초', '111.1s to 71.0s'),
    tone: 'boot',
    nodes: ['registry', 'gpu'],
    edges: ['registry-gpu'],
    values: { registry: tr('이미지 9.1GiB', 'Image 9.1GiB') },
    text: tr(
      '노드가 뜨면 userData의 일회성 유닛이 containerd를 기다렸다가 vLLM 이미지(9.1GiB)를 Docker Hub에서 미리 받습니다. ' +
        'kubelet의 pull은 진행 중인 다운로드를 이어받습니다. 사전 pull은 노드가 뜨는 동안 먼저 시작하므로 kubelet이 본 시간이 줄어듭니다.',
      'When the node boots, a one-shot unit in userData waits for containerd and pre-pulls the vLLM image (9.1GiB) from Docker Hub. ' +
        'The kubelet pull then joins the download in progress. Because the pre-pull starts while the node is still coming up, the kubelet sees a shorter pull.',
    ),
    rows: [
      [tr('Gemma, 사전 pull 없음', 'Gemma, no pre-pull'), tr('111.1초', '111.1s')],
      [tr('Gemma, 사전 pull', 'Gemma, pre-pull'), tr('71.0초', '71.0s')],
      [tr('Qwen, 사전 pull', 'Qwen, pre-pull'), tr('77.5초', '77.5s')],
    ],
    note: tr('kubelet의 Pulled 이벤트로 잰 값입니다.', 'Measured from the kubelet Pulled event.'),
  },
  {
    n: 3,
    title: tr('가중치 로드', 'Weight load'),
    value: tr('59.6초에서 19.2초', '59.6s to 19.2s'),
    tone: 'boot',
    nodes: ['s3', 'identity', 'gemma', 'qwen'],
    edges: ['s3-gemma', 's3-qwen', 'identity-s3'],
    values: { gemma: tr('가중치 19.2초', 'Weights 19.2s'), qwen: tr('가중치 34.9초', 'Weights 34.9s') },
    text: tr(
      'vLLM이 runai_streamer로 모델 버킷의 가중치를 S3에서 직접 읽습니다. 파드는 Pod Identity로 받은 읽기 전용 역할로 S3에 접근합니다. ' +
        '기준 구성은 버킷을 Mountpoint로 마운트해 vLLM 기본 로더로 읽습니다.',
      'vLLM reads the weights straight from the S3 model bucket with runai_streamer. The pod reaches S3 with a read-only role from Pod Identity. ' +
        'The baseline mounts the bucket with Mountpoint and reads with the default vLLM loader.',
    ),
    rows: [
      [tr('Gemma, Mountpoint로 읽기', 'Gemma, read through Mountpoint'), tr('59.6초', '59.6s')],
      ['Gemma, runai_streamer', tr('19.2초', '19.2s')],
      ['Qwen, runai_streamer', tr('34.9초', '34.9s')],
    ],
    note: tr('vLLM 로그의 Model loading took으로 잰 값입니다.', 'Measured from "Model loading took" in the vLLM log.'),
  },
  {
    n: 4,
    title: tr('엔진 초기화', 'Engine init'),
    value: tr('95.5초에서 23.7초', '95.5s to 23.7s'),
    tone: 'boot',
    nodes: ['s3', 'cache', 'gemma', 'qwen'],
    edges: ['s3-cache', 'cache-gemma', 'cache-qwen'],
    values: {
      cache: tr('S3 복원 3.3초', 'S3 restore 3.3s'),
      gemma: tr('초기화 23.7초', 'Init 23.7s'),
      qwen: tr('초기화 42.5초', 'Init 42.5s'),
    },
    text: tr(
      'initContainer cache-restore가 S3의 compile 캐시를 노드의 hostPath(/var/cache/vllm)로 내려받고 vLLM이 그 캐시를 다시 씁니다. ' +
        '이어서 KV 캐시를 만들고 워밍업을 합니다. Gemma는 새 노드에서 캐시 522개(90.8MB)를 3.3초에 복원했습니다.',
      'The initContainer cache-restore downloads the compile cache from S3 to a hostPath on the node (/var/cache/vllm), and vLLM reuses it. ' +
        'vLLM then allocates the KV cache and warms up. On a new node, Gemma restored 522 cache files (90.8MB) in 3.3s.',
    ),
    rows: [
      [tr('Gemma, 캐시 없음', 'Gemma, no cache'), tr('95.5초 (compile 61.0초)', '95.5s (compile 61.0s)')],
      [tr('Gemma, S3 캐시 복원', 'Gemma, cache restored from S3'), tr('23.7초 (compile 0.9초)', '23.7s (compile 0.9s)')],
      [tr('Qwen, S3 캐시 복원', 'Qwen, cache restored from S3'), tr('42.5초 (compile 0.8초)', '42.5s (compile 0.8s)')],
    ],
    note: tr('vLLM 로그의 init engine 줄로 잰 값입니다.', 'Measured from the "init engine" line in the vLLM log.'),
  },
  {
    n: 5,
    title: tr('추론 요청', 'Inference request'),
    value: tr('첫 내용 81.9ms, 177.5ms', 'First content 81.9ms, 177.5ms'),
    tone: 'serve',
    nodes: ['user', 'cf', 'alb', 'bff', 'gw', 'wake', 'gemma', 'qwen'],
    edges: ['user-cf', 'cf-alb', 'alb-bff', 'bff-gw', 'gw-gemma', 'gw-qwen', 'bff-wake', 'wake-qwen'],
    // 요청이 켰을 때만 쓰는 경로. 점선 테두리로 약하게 켠다.
    optional: { nodes: ['search'], edges: ['bff-search'] },
    values: {
      user: tr('첫 내용 81.9ms', 'First content 81.9ms'),
      cf: '5.0ms',
      alb: '1.6ms',
      bff: tr('판단 0.1ms', 'Decision 0.1ms'),
      gw: '9.7ms',
      gemma: 'TTFT 63.2ms',
      qwen: 'TTFT 147.6ms',
      search: tr('선택, 481~1,065ms', 'Opt. 481~1,065ms'),
    },
    text: tr(
      '브라우저의 요청이 CloudFront, 내부 ALB, BFF, 게이트웨이를 거쳐 모델로 갑니다. BFF는 EKS 파드이고 게이트웨이의 Service를 직접 부릅니다. ' +
        'BFF가 모델을 정하고, Qwen으로 가는 요청은 깨우기 API를 먼저 부릅니다. 요청을 보내면 이 그림에 그 요청이 실제로 거친 경로와 시간이 표시됩니다.',
      'A request from the browser goes through CloudFront, the internal ALB, the BFF, and the gateway to a model. The BFF runs as EKS pods and calls ' +
        'the gateway Service directly. The BFF picks the model, and requests bound for Qwen call the wake API first. Send a request and this map ' +
        'shows the path and timing it actually took.',
    ),
    more: tr(
      '웹 검색을 켠 요청에는 BFF가 모델에 web_search 도구를 붙입니다. 모델이 도구를 부르면 BFF가 AgentCore Web Search(us-east-1)로 검색하고, ' +
        '결과에 번호를 붙여 돌려준 뒤 다시 추론을 요청합니다. 추론은 Gemma와 Qwen이 하고 검색만 AgentCore가 합니다. ' +
        '한 요청에서 도구를 부를 수 있는 차례는 3번이고, 민감 정보가 있는 요청과 성능 평가 요청에는 도구를 붙이지 않습니다.',
      'For requests with web search on, the BFF attaches the web_search tool to the model request. When the model calls the tool, the BFF searches ' +
        'with AgentCore Web Search (us-east-1), returns numbered results, and requests inference again. Gemma and Qwen do the inference, and only ' +
        'the search runs on AgentCore. A request gets at most 3 tool rounds, and requests with sensitive data and benchmark requests get no tool.',
    ),
    rows: [
      [tr('Gemma, 사용자가 본 첫 내용', 'Gemma, first content seen by the user'), '81.9ms (vLLM 63.2ms)'],
      [tr('Qwen, 사용자가 본 첫 내용', 'Qwen, first content seen by the user'), '177.5ms (vLLM 147.6ms)'],
      [tr('웹 검색 1회 (켠 요청만)', 'One web search (only when on)'), '481~1,065ms'],
    ],
    note: tr(
      '첫 내용은 요청을 하나씩 보낸 20건의 중앙값입니다. 웹 검색은 작업 장비(서울)에서 us-east-1을 6회 부른 범위이고 결과는 5건입니다. ' +
        '배포 뒤 BFF가 잰 값은 요청 8건에서 485~662ms(중앙값 568ms)였습니다.',
      'First content is the median of 20 requests sent one at a time. Web search is the range of 6 calls to us-east-1 from the work machine (Seoul), ' +
        'with 5 results each. After deployment, the BFF measured 485~662ms (median 568ms) over 8 requests.',
    ),
  },
]);

// 단계 하나를 흐름 그림의 상태로 바꾼다. 그 단계의 노드는 on, 선은 feed(공급 방향으로 움직이는 선), 나머지는 off다.
// 그 단계에서 쓸 수도 있고 안 쓸 수도 있는 것(optional)은 opt로 약하게 켠다.
export function stepFlow(n) {
  const step = STEPS[n];
  if (!step) return null;
  const optional = step.optional ?? { nodes: [], edges: [] };
  const state = (name, chosen, maybe, on) => (chosen.includes(name) ? on : maybe.includes(name) ? 'opt' : 'off');
  const nodes = Object.fromEntries(MAP_NODES.map((name) => [name, state(name, step.nodes, optional.nodes, 'on')]));
  const edges = Object.fromEntries(MAP_EDGES.map((name) => [name, state(name, step.edges, optional.edges, 'feed')]));
  // 틀은 그 단계가 노드 자체를 다룰 때만 켠다. 틀 안의 노드가 켜져 있으면 틀은 그대로 둔다.
  if (step.nodes.includes('gpu')) nodes.gpu = 'on';
  else if (!IN_GPU.some((name) => step.nodes.includes(name))) nodes.gpu = 'off';
  return { nodes, edges, values: step.values, phase: 'step', step: n };
}
