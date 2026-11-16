// "API 호출" 보기의 단계, 지도 표시, 값 계산. 화면과 무관한 순수 함수만 둔다.
//
// 단계는 docs/infographic/apicall.py의 인포그래픽과 같은 여덟 개다. 측정값은 그 파일이 내보낸
// apicall-data.js에서 읽는다(8단계 측정, docs/08-results.md). 숫자를 이 파일에 따로 적지 않는다.
import data from './apicall-data.js';
import { addSearch } from './citations.js';
import { locale, localized, tr } from './i18n.js';

export const REGIONS = data.regions;
const M = data.measured;
const D = data.derived;
const SEARCH = M.search;

// 재생과 실제 요청은 8단계의 구간별 TTFT 측정과 같은 요청을 쓴다(bench/ttft/segments.py).
// 웹 검색을 켠 요청은 요청 보기의 웹 검색 예시와 같은 질문이다(docs/10-web-search.md에서 손으로 돌려 본 질문).
// 질문(prompt, searchPrompt)은 번역하지 않는다. 측정값이 이 한국어 질문으로 잰 값이기 때문이다.
// 영어 화면에서는 뜻을 알 수 있게 영어 풀이(promptGloss, searchPromptGloss)를 함께 보여 준다. 한국어 화면에서는 빈 문자열이다.
export const SIDES = localized(() => ({
  gemma: {
    name: M.gemma.name, model: 'gemma-4-31b', task: 'support', taskLabel: tr('상담', 'Support'),
    prompt: '반품은 며칠 안에 신청해야 하나요?',
    promptGloss: tr('', 'How many days do I have to request a return?'),
    searchPrompt: 'Amazon Bedrock AgentCore Web Search API를 쓸 수 있는 AWS 리전을 검색해서 알려 주세요.',
    searchPromptGloss: tr('', 'Search for the AWS Regions where the Amazon Bedrock AgentCore Web Search API is available and tell me.'),
  },
  qwen: {
    name: M.qwen.name, model: 'qwen38-27b', task: 'coding', taskLabel: tr('코딩', 'Coding'),
    prompt: '파이썬에서 리스트를 뒤집는 방법을 한 줄로 알려 주세요.',
    promptGloss: tr('', 'Tell me in one line how to reverse a list in Python.'),
    searchPrompt: 'Kubernetes 최신 릴리스의 주요 변경점을 검색해서 세 가지로 정리해 주세요.',
    searchPromptGloss: tr('', 'Search for the main changes in the latest Kubernetes release and summarize them in three points.'),
  },
}));

export const sideOf = (model) => Object.keys(SIDES).find((side) => SIDES[side].model === model) ?? null;

export function duration(value) {
  if (value == null || Number.isNaN(value)) return '';
  if (value >= 10000) return `${(value / 1000).toFixed(1)}${tr('초', 's')}`;
  if (value >= 1000) return `${(value / 1000).toFixed(2)}${tr('초', 's')}`;
  if (value === 0) return '0ms';
  // 0.03ms처럼 0.1ms보다 작은 값은 한 자리 더 적는다.
  return `${value.toFixed(value < 0.095 ? 2 : 1)}ms`;
}

const count = (value) => value.toLocaleString(locale());
// 영어 문구의 단수와 복수. 한국어 문구에는 쓰지 않는다.
const plural = (value, one, many = `${one}s`) => `${count(value)} ${value === 1 ? one : many}`;
// BFF가 응답 헤더 x-bff-search로 알려 주는 값
const SEARCH_STATES = localized(() => ({
  on: tr('모델 요청에 붙임', 'Attached to model request'),
  off: tr('요청이 켜지 않음', 'Not turned on by request'),
  sensitive: tr('민감 정보 요청이라 붙이지 않음', 'Not attached (sensitive data)'),
  fallback: tr('모델을 정하지 못해 붙이지 않음', 'Not attached (decision failed)'),
  disabled: tr('이 환경에 설정되지 않음', 'Not configured here'),
}));
const DECISIONS = localized(() => ({
  rule: tr('민감 정보 규칙', 'Sensitive data rule'),
  task: tr('업무 종류', 'Task type'),
  attachment: tr('첨부 파일', 'Attachment'),
  decider: tr('Decider의 판단', 'Decider'),
  fallback: tr('기본값', 'Default'),
}));

export const STAGES = localized(() => [
  {
    n: 1,
    en: 'API Gateway',
    ko: tr('요청 진입', 'Request entry'),
    lead: tr(
      '요청이 처음 닿는 곳입니다. 암호화된 연결을 받고, 호출 횟수를 제한하고, 누가 보냈는지 확인하고, 본문 형식을 검사합니다.',
      'Where the request first lands. It accepts the encrypted connection, limits the call rate, checks who sent the request, and validates the body format.',
    ),
    here: [
      ['CloudFront', tr('HTTPS로 받아 /v1/* 요청을 내부 ALB로 넘깁니다.', 'Accepts HTTPS and forwards /v1/* requests to the internal ALB.')],
      ['AWS WAF', tr('IP 하나가 5분에 300회를 넘기면 403으로 막습니다.', 'Blocks an IP with 403 when it sends more than 300 requests in 5 minutes.')],
      ['Cognito', tr('로그인할 때 액세스 토큰을 발급합니다. 가입은 막아 두었습니다.', 'Issues an access token at sign-in. Sign-up is disabled.')],
      ['BFF', tr('토큰을 검증해 틀리면 401을, messages가 없는 본문이면 400을 돌려줍니다.', 'Verifies the token and returns 401 if it is invalid, or 400 if the body has no messages.')],
    ],
    note: tr(
      '429는 이 단계가 아닌 게이트웨이에서 납니다. 풀이 포화되면 배치 요청만 거절합니다.',
      '429 comes from the gateway, not from this step. When the pool is saturated, only batch requests are rejected.',
    ),
  },
  {
    n: 2,
    en: 'Load Balancer',
    ko: tr('부하 분산', 'Spreading requests'),
    lead: tr(
      '요청을 받을 수 있는 대상에게 나눠 보냅니다. 이 환경에서는 내부 ALB와 게이트웨이(agentgateway)가 이 일을 합니다.',
      'Spreads requests across the targets that can take them. In this environment the internal ALB and the gateway (agentgateway) do that.',
    ),
    here: [
      [tr('내부 ALB', 'Internal ALB'), tr(
        'CloudFront에서 온 요청만 받아 BFF 파드 2개로 나눕니다. 쿠키로 같은 세션을 30분 동안 같은 파드에 보냅니다. AWS Load Balancer Controller가 Ingress에서 만든 ALB입니다.',
        'Accepts only requests from CloudFront and spreads them across 2 BFF pods. A cookie keeps a session on the same pod for 30 minutes. The AWS Load Balancer Controller creates this ALB from an Ingress.',
      )],
      ['Service', tr(
        'BFF는 클러스터 안의 Service(inference-gateway.inference.svc)로 게이트웨이를 직접 부릅니다. 게이트웨이의 내부 NLB는 배치 클라이언트만 씁니다.',
        'The BFF calls the gateway directly through its in-cluster Service (inference-gateway.inference.svc). The internal NLB of the gateway serves only the batch client.',
      )],
      ['agentgateway', tr(
        '파드 2개가 본문의 model 값을 보고 모델별 InferencePool을 고릅니다.',
        'Two pods read the model value in the body and pick the InferencePool for that model.',
      )],
      [tr('헬스체크', 'Health check'), tr(
        'ALB는 /healthz로 BFF를 확인합니다. 잠든 Qwen 파드는 readinessProbe가 대상에서 뺍니다.',
        'The ALB checks the BFF at /healthz. The readinessProbe takes a sleeping Qwen pod out of the targets.',
      )],
    ],
    note: tr('GPU 부하를 보고 파드를 고르는 일은 4단계의 EPP가 합니다.', 'Picking a pod by GPU load is the job of the EPP in step 4.'),
  },
  {
    n: 3,
    en: 'Tokenization',
    ko: tr('토큰화', 'Text to token IDs'),
    lead: tr(
      '문장을 모델이 읽는 토큰 ID로 바꾸고 길이를 확인합니다.',
      'Turns the text into the token IDs the model reads and checks the length.',
    ),
    here: [
      [tr('vLLM API 서버', 'vLLM API server'), tr(
        '모델 파드 안에서 chat template을 적용하고 그 모델의 tokenizer로 토큰화합니다.',
        'Inside the model pod, applies the chat template and tokenizes with the tokenizer of that model.',
      )],
      [tr('컨텍스트 한도', 'Context limit'), tr(
        `--max-model-len 값입니다. Gemma는 ${count(M.gemma.max_model_len)}토큰, Qwen은 ${count(M.qwen.max_model_len)}토큰입니다.`,
        `The --max-model-len value. Gemma takes ${count(M.gemma.max_model_len)} tokens and Qwen ${count(M.qwen.max_model_len)} tokens.`,
      )],
    ],
    note: tr(
      '이 환경에서는 4단계가 먼저입니다. BFF와 게이트웨이는 토큰화하지 않고 헤더와 원문 텍스트로 모델을 정합니다.',
      'In this environment step 4 comes first. The BFF and the gateway do not tokenize. They choose the model from the headers and the raw text.',
    ),
  },
  {
    n: 4,
    en: 'Model Router',
    ko: tr('모델 결정, 대기열', 'Model choice, queue'),
    lead: tr(
      '어느 모델의 어느 파드가 처리할지 정하고, 자리가 없으면 줄을 세웁니다.',
      'Decides which pod of which model handles the request, and queues the request when there is no free slot.',
    ),
    here: [
      ['BFF', tr(
        '민감 정보 규칙, 업무 종류, 첨부, Decider, 기본값 순서로 먼저 맞는 규칙을 적용해 Gemma와 Qwen 중 하나를 고릅니다.',
        'Picks Gemma or Qwen by the first rule that matches, in this order: sensitive data rule, task type, attachment, Decider, default.',
      )],
      ['Decider 2B', tr(
        '업무 종류가 없는 요청만 판단합니다. 신뢰도가 0.6 이상일 때 그 판단을 씁니다.',
        'Classifies only requests that have no task type. Its answer is used when the confidence is 0.6 or higher.',
      )],
      [tr('InferencePool과 EPP', 'InferencePool and EPP'), tr('풀 안에서 요청을 보낼 vLLM 파드를 고릅니다.', 'Picks the vLLM pod in the pool that gets the request.')],
      [tr('깨우기 API', 'Wake API'), tr(
        'Qwen으로 가는 요청마다 Qwen이 깨어 있는지 확인하고, 잠들어 있으면 깨웁니다. BFF가 클러스터 안의 Service로 직접 부르고 NetworkPolicy가 BFF 파드와 ow-on-gpu/wake-client 라벨이 붙은 파드만 허용합니다.',
        'For every request that goes to Qwen, checks whether Qwen is awake and wakes it if it is asleep. The BFF calls it directly through its in-cluster Service, and a NetworkPolicy allows only BFF pods and pods labeled ow-on-gpu/wake-client.',
      )],
      [tr('웹 검색 도구', 'Web search tool'), tr(
        '요청이 x-web-search: on을 보냈을 때만 BFF가 모델 요청에 web_search 도구와 지시문(오늘 날짜, 출처 번호 규칙)을 붙입니다. 민감 정보 요청과 성능 평가 요청에는 붙이지 않습니다.',
        'Only when the request sends x-web-search: on does the BFF attach the web_search tool and its instructions (today\'s date, source numbering rules) to the model request. It is not attached to sensitive data requests or benchmark requests.',
      )],
      [tr('vLLM priority 스케줄러', 'vLLM priority scheduler'), tr(
        '엔진 안의 대기열입니다. 상담(0)을 배치(10)보다 먼저 처리합니다.',
        'The queue inside the engine. Support (0) is served before batch (10).',
      )],
    ],
    note: tr(
      `배치 부하 중 상담 요청의 TTFT 중앙값은 우선순위가 없을 때 ${(M.priority_ttft_ms.none / 1000).toFixed(1)}초, 엔진 우선순위를 켰을 때 ${(M.priority_ttft_ms.engine / 1000).toFixed(2)}초였습니다.`,
      `Under batch load, the median TTFT of support requests was ${(M.priority_ttft_ms.none / 1000).toFixed(1)}s without priority and ${(M.priority_ttft_ms.engine / 1000).toFixed(2)}s with engine priority on.`,
    ),
  },
  {
    n: 5,
    en: 'Inference Engine',
    ko: tr('토큰 생성', 'Token generation'),
    lead: tr(
      '토큰을 실제로 만드는 구간입니다. 모델마다 g6e.4xlarge의 L40S 한 장에서 vLLM v0.33.0이 처리합니다.',
      'Where the tokens are actually generated. Each model runs on vLLM v0.33.0 with one L40S on a g6e.4xlarge.',
    ),
    here: [
      ['A Prefill', tr(
        '입력 토큰 전체를 한 번에 계산하고 KV 캐시에 기록합니다. 첫 토큰까지의 시간을 좌우합니다.',
        'Computes all input tokens in one pass and writes them to the KV cache. This sets the time to first token.',
      )],
      ['B Decode', tr(
        'KV 캐시를 다시 쓰면서 토큰을 하나씩 만듭니다. 조각 사이 간격을 좌우합니다. Qwen은 MTP로 조각 하나에 여러 토큰을 담습니다.',
        'Generates tokens one at a time while reusing the KV cache. This sets the interval between chunks. Qwen uses MTP to put several tokens in one chunk.',
      )],
      ['C Hardware', tr(
        `L40S의 GDDR6 48GB 중 ${M.device_gib}GiB를 쓸 수 있습니다. 가중치가 차지하고 남은 KV 캐시 크기가 동시에 실행하는 요청 수를 제한합니다.`,
        `${M.device_gib}GiB of the 48GB GDDR6 on the L40S is usable. The KV cache left after the weights limits how many requests run at once.`,
      )],
      [tr('다시 추론', 'Infer again'), tr(
        `모델이 도구를 부르면 BFF가 도구 결과를 붙인 요청을 다시 보내고, 엔진은 그 요청을 처음부터 처리합니다. 한 요청에서 도구를 부르는 차례는 ${SEARCH.max_rounds}번까지입니다.`,
        `When the model calls a tool, the BFF sends the request again with the tool result attached, and the engine processes that request from the start. One request gets at most ${SEARCH.max_rounds} tool-call rounds.`,
      )],
    ],
    note: tr(
      `사용자가 본 첫 내용까지의 시간 중 vLLM이 Gemma ${D.gemma.share}%, Qwen ${D.qwen.share}%였습니다.`,
      `Of the time to the first content seen by the user, vLLM took ${D.gemma.share}% for Gemma and ${D.qwen.share}% for Qwen.`,
    ),
  },
  {
    n: 6,
    en: 'Post-processing',
    ko: tr('후처리', 'Detokenize, parse'),
    lead: tr(
      '생성한 토큰을 텍스트로 되돌리고 추론 과정과 도구 호출을 답변에서 떼어 냅니다. 스트리밍 중에는 조각마다 함께 진행됩니다.',
      'Turns the generated tokens back into text and separates the reasoning and tool calls from the answer. While streaming, this runs for every chunk.',
    ),
    here: [
      ['Detokenize', tr('vLLM이 토큰 ID를 텍스트로 되돌립니다.', 'vLLM turns the token IDs back into text.')],
      ['Reasoning parser', tr(
        '추론 과정을 reasoning_content로 분리합니다. Gemma는 gemma4, Qwen은 qwen3 parser를 씁니다.',
        'Splits the reasoning out into reasoning_content. Gemma uses the gemma4 parser and Qwen the qwen3 parser.',
      )],
      ['Tool-call parser', tr(
        '도구 호출을 tool_calls로 뽑습니다. Gemma는 gemma4, Qwen은 qwen3_coder parser를 씁니다.',
        'Extracts tool calls into tool_calls. Gemma uses the gemma4 parser and Qwen the qwen3_coder parser.',
      )],
      [tr('BFF의 도구 실행', 'BFF tool execution'), tr(
        `모델이 주문 조회나 웹 검색 도구를 부르면 BFF가 실행하고 결과를 붙여 5단계로 다시 보냅니다. 차례는 ${SEARCH.max_rounds}번까지이고 마지막에는 tool_choice: none으로 지금까지의 결과로 답하게 합니다.`,
        `When the model calls the order lookup or web search tool, the BFF runs it, attaches the result, and sends the request back to step 5. There are at most ${SEARCH.max_rounds} rounds, and the last one sets tool_choice: none so the model answers from the results so far.`,
      )],
      ['AgentCore Web Search', tr(
        `BFF가 InvokeWebSearch(${SEARCH.region})를 EKS Pod Identity로 연결한 역할의 권한으로 불러 검색합니다. 결과 ${SEARCH.results}건에 번호를 붙이고 본문을 ${count(SEARCH.text_chars)}자까지 잘라 모델에 돌려줍니다. 추론은 Gemma와 Qwen이 하고 검색만 AgentCore가 합니다.`,
        `The BFF searches by calling InvokeWebSearch (${SEARCH.region}) with the permissions of the role attached through EKS Pod Identity. It numbers the ${SEARCH.results} results, cuts each body to ${count(SEARCH.text_chars)} characters, and returns them to the model. Gemma and Qwen do the inference. AgentCore does only the search.`,
      )],
    ],
    note: tr(
      '출력 안전 필터는 두지 않았습니다. 주민등록번호와 카드번호 형식은 4단계의 규칙이 입력에서 찾아 Gemma로만 보내고, 모델이 만든 검색어에 그 형식이 있으면 검색을 보내지 않습니다.',
      'There is no output safety filter. The step 4 rule finds resident registration number and card number formats in the input and sends those requests only to Gemma. If a search query written by the model contains those formats, the search is not sent.',
    ),
  },
  {
    n: 7,
    en: 'Response & Billing',
    ko: tr('응답, 비용', 'Response, cost'),
    lead: tr(
      '조각을 브라우저까지 돌려보내고 요청이 쓴 양을 셉니다.',
      'Sends the chunks back to the browser and counts what the request used.',
    ),
    here: [
      ['BFF', tr(
        '게이트웨이에서 받은 SSE 조각을 모으지 않고 그대로 흘려보냅니다.',
        'Passes the SSE chunks from the gateway straight through without buffering them.',
      )],
      ['usage', tr('마지막 조각에 입력과 출력 토큰 수가 담겨 옵니다.', 'The last chunk carries the input and output token counts.')],
      [tr('출처', 'Sources'), tr(
        '웹 검색을 쓴 답변에는 모델이 [1], [2] 번호를 붙입니다. 화면은 SSE 주석 줄로 받은 출처 목록을 답변 아래에 링크로 보여 줍니다.',
        'In an answer that used web search, the model adds numbers such as [1] and [2]. The page shows the source list, received as SSE comment lines, as links below the answer.',
      )],
      [tr('응답 헤더', 'Response headers'), tr(
        'x-bff-model, x-bff-decision, x-bff-timing으로 어느 모델을 왜 골랐고 BFF에서 얼마나 걸렸는지 알려 줍니다.',
        'x-bff-model, x-bff-decision, and x-bff-timing tell which model was chosen, why, and how long the BFF took.',
      )],
      [tr('비용', 'Cost'), tr(
        `토큰 단가가 없습니다. GPU 노드가 떠 있는 시간에 비용이 붙고, 이 환경의 고정 비용은 시간당 약 ${M.fixed_cost_usd_per_hour}달러입니다.`,
        `There is no price per token. Cost accrues for the time the GPU nodes are up, and the fixed cost of this environment is about ${M.fixed_cost_usd_per_hour} USD per hour.`,
      )],
    ],
    note: tr(
      `전체 시간은 TTFT + (출력 토큰 수 - 1) × TPOT와 같습니다. Gemma의 S1에서는 ${M.gemma.s1.ttft}ms + ${M.s1_output_tokens - 1} × ${M.gemma.s1.tpot}ms로 ${count(Math.round(M.gemma.s1.e2e))}ms였습니다.`,
      `Total time equals TTFT + (output tokens - 1) × TPOT. In S1 for Gemma that was ${M.gemma.s1.ttft}ms + ${M.s1_output_tokens - 1} × ${M.gemma.s1.tpot}ms, or ${count(Math.round(M.gemma.s1.e2e))}ms.`,
    ),
  },
  {
    n: 8,
    en: 'Logging & Observability',
    ko: tr('기록, 관측', 'Logs, metrics'),
    lead: tr(
      '요청이 지나간 구간마다 기록을 남기고 지표를 모읍니다.',
      'Every segment the request passes through leaves a record, and metrics are collected.',
    ),
    here: [
      [tr('Prometheus agent와 AMP', 'Prometheus agent and AMP'), tr(
        'vLLM 파드 2개, EPP 파드 4개, 게이트웨이 파드 2개의 지표를 모아 Amazon Managed Service for Prometheus로 보냅니다.',
        'Collects metrics from 2 vLLM pods, 4 EPP pods, and 2 gateway pods and sends them to Amazon Managed Service for Prometheus.',
      )],
      [tr('BFF 로그', 'BFF logs'), tr(
        '파드의 표준 출력에 요청마다 chat과 chat_end를 남깁니다. 결정 근거, 구간 시간, 첫 조각 시각이 들어 있습니다.',
        'Writes chat and chat_end to the pod standard output for every request. They hold the reason for the decision, the segment times, and the time of the first chunk.',
      )],
      [tr('ALB 접근 로그', 'ALB access logs'), tr('S3 버킷에 쌓입니다.', 'Stored in an S3 bucket.')],
      ['Server-Timing', tr(
        'CloudFront가 응답 헤더에 엣지와 오리진의 시간을 붙입니다.',
        'CloudFront adds the edge and origin times to the response headers.',
      )],
    ],
    note: tr(
      '8단계 측정에서는 요청 ID와 X-Amzn-Trace-Id로 여섯 구간의 기록을 요청마다 이었습니다.',
      'In the build step 8 measurement, the records of six segments were joined for each request by request ID and X-Amzn-Trace-Id.',
    ),
  },
]);

// 단계 n에서 8단계 측정이 잰 값. [이름, 값] 목록이다.
export function measuredRows(n, side) {
  const m = M[side];
  switch (n) {
    case 1:
      return [[tr('사용자와 엣지 사이', 'User to edge'), duration(m.edge)], ['CloudFront', duration(m.cloudfront)]];
    case 2:
      return [
        ['ALB', duration(m.alb)],
        [tr('게이트웨이 구간 (agentgateway, EPP)', 'Gateway segment (agentgateway, EPP)'), duration(m.gateway)],
      ];
    case 3:
      return [
        [tr('토큰화 시간', 'Tokenization time'), tr('따로 재지 않음', 'Not measured separately')],
        [tr('컨텍스트 한도', 'Context limit'), tr(`${count(m.max_model_len)}토큰`, `${count(m.max_model_len)} tokens`)],
      ];
    case 4:
      return [
        [side === 'qwen' ? tr('BFF (판단과 깨우기 확인)', 'BFF (decision and wake check)') : tr('BFF (판단)', 'BFF (decision)'), duration(m.bff)],
        [tr('EPP의 파드 선택', 'EPP pod selection'), duration(M.epp_ms)],
        [tr('Decider (업무 종류가 없을 때)', 'Decider (no task type)'), `${M.decider_ms[0]}~${M.decider_ms[1]}ms`],
        [tr('엔진 대기열 (요청 1건씩)', 'Engine queue (one request at a time)'), duration(m.queue)],
      ];
    case 5:
      return [
        ['Prefill', duration(m.prefill)],
        [tr('조각 간격 (ITL)', 'Chunk interval (ITL)'), duration(m.s1.itl)],
        [tr('토큰당 시간 (TPOT)', 'Time per token (TPOT)'), duration(m.s1.tpot)],
        [tr('가중치, KV 캐시', 'Weights, KV cache'), `${m.weights_gib}GiB, ${m.kv_gib}GiB`],
        [tr('S1에서 동시에 실행한 요청', 'Requests running at once in S1'), tr(`최대 ${m.s1.running_max}건`, `Up to ${m.s1.running_max}`)],
      ];
    case 6:
      return [[tr('후처리 시간', 'Post-processing time'), tr('따로 재지 않음', 'Not measured separately')]];
    case 7:
      return [
        [tr('응답 헤더 도착', 'Response headers received'), duration(m.headers)],
        [tr('사용자가 본 첫 내용', 'First content seen by the user'), duration(m.first_content)],
        [tr(`S1의 전체 시간 (출력 ${M.s1_output_tokens}토큰)`, `Total time in S1 (${M.s1_output_tokens} output tokens)`), duration(m.s1.e2e)],
      ];
    case 8:
      return [
        [tr('지표 수집 대상', 'Metrics collected from'), tr('파드 8개', '8 pods')],
        [tr('대시보드', 'Dashboard'), tr('패널 15개, 쿼리 27개', '15 panels, 27 queries')],
      ];
    default:
      return [];
  }
}

// 웹 검색 경로에서 잰 값. 8단계 측정이 아닌, 작업 장비에서 손으로 돌려 본 값과 배포 뒤 BFF가 잰 값이다(docs/10-web-search.md).
export function searchRows(n, side) {
  if (n === 6) {
    const rows = [
      [
        tr(`검색 1회 (작업 장비에서 ${SEARCH.region})`, `One search (work machine to ${SEARCH.region})`),
        `${SEARCH.ms[0]}~${count(SEARCH.ms[1])}ms`,
      ],
      [
        tr('모델에 넘기는 결과', 'Results passed to the model'),
        tr(`${SEARCH.results}건, 본문 ${count(SEARCH.text_chars)}자까지`, `${SEARCH.results}, up to ${count(SEARCH.text_chars)} chars each`),
      ],
      [
        tr(`입력 토큰 (검색 ${SEARCH.searches[side]}회)`, `Input tokens (${plural(SEARCH.searches[side], 'search', 'searches')})`),
        tr(`${count(SEARCH.input_tokens[side])}개`, count(SEARCH.input_tokens[side])),
      ],
    ];
    if (side === 'qwen') {
      rows.push([
        tr('첫 차례, 두 번째 차례', 'First round, second round'),
        SEARCH.qwen_round_s.map((value) => `${value}${tr('초', 's')}`).join(', '),
      ]);
    }
    rows.push([
      tr(`BFF에서 잰 검색 시간 (요청 ${SEARCH.bff_n}건)`, `Search time at the BFF (${plural(SEARCH.bff_n, 'request')})`),
      tr(
        `${SEARCH.bff_ms[0]}~${SEARCH.bff_ms[1]}ms, 중앙값 ${SEARCH.bff_median_ms}ms`,
        `${SEARCH.bff_ms[0]}~${SEARCH.bff_ms[1]}ms, median ${SEARCH.bff_median_ms}ms`,
      ),
    ]);
    return rows;
  }
  if (n === 7) {
    return [
      [tr('요금', 'Price'), tr(`1,000건에 ${SEARCH.usd_per_1000}달러`, `${SEARCH.usd_per_1000} USD per 1,000 searches`)],
      [tr('기본 할당량', 'Default quota'), tr(`초당 ${SEARCH.quota_per_s}건`, `${SEARCH.quota_per_s} per second`)],
    ];
  }
  return [];
}

const median = (values) => {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
};

// 실제 요청 한 건의 기록을 값으로 정리한다. 브라우저가 알 수 있는 것만 담는다.
//   live.info   streamChat의 onHeaders가 준 값
//   live.ticks  조각이 도착한 시각 [{ms, kind}]
//   live.result streamChat이 돌려준 값 {totalMs, finishReason, usage}
//   live.notes  웹 검색 도구 호출 알림(streamChat의 onNote). live.asked는 요청이 웹 검색을 켰는지
export function summarizeLive(live) {
  if (!live?.info) return null;
  const { info, ticks = [], result } = live;
  const { searches, sources } = (live.notes ?? []).reduce((state, note) => addSearch(state, note), { searches: [], sources: [] });
  const timing = info.timing ?? {};
  const bffMs = timing.decide_ms != null ? (timing.decide_ms ?? 0) + (timing.wake_ms ?? 0) : null;
  const insideBff = bffMs != null && timing.upstream_ms != null ? bffMs + timing.upstream_ms : null;
  const times = ticks.map((tick) => tick.ms);
  const ttft = times.length ? times[0] : null;
  const outputTokens = result?.usage?.completion_tokens ?? null;
  const totalMs = result?.totalMs ?? null;
  return {
    model: info.model,
    decision: info.decision,
    requestId: info.requestId,
    headersMs: info.headersMs,
    // 응답 헤더가 오기까지의 시간에서 BFF 안에서 쓴 시간을 뺀 값. 브라우저와 BFF 사이를 오간 시간이다.
    entryMs: insideBff != null ? Math.max(0, info.headersMs - insideBff) : null,
    decideMs: timing.decide_ms ?? null,
    wakeMs: timing.wake_ms ?? null,
    woke: Boolean(timing.woke),
    upstreamMs: timing.upstream_ms ?? null,
    bffMs,
    cdnUpstream: info.cdn?.['cdn-upstream-fbl'] ?? null,
    cdnDownstream: info.cdn?.['cdn-downstream-fbl'] ?? null,
    ttft,
    firstKind: ticks[0]?.kind ?? null,
    gap: median(times.slice(1).map((value, index) => value - times[index])),
    chunks: ticks.length,
    reasoningChunks: ticks.filter((tick) => tick.kind === 'reasoning').length,
    contentChunks: ticks.filter((tick) => tick.kind === 'content').length,
    totalMs,
    finishReason: result?.finishReason ?? null,
    inputTokens: result?.usage?.prompt_tokens ?? null,
    outputTokens,
    tpot: totalMs != null && ttft != null && outputTokens > 1 ? (totalMs - ttft) / (outputTokens - 1) : null,
    asked: Boolean(live.asked),
    search: info.search ?? null,
    searches,
    sources,
  };
}

// 단계 n에서 이 요청이 보여 준 값. 브라우저가 알 수 없는 단계는 빈 목록이다.
export function liveRows(n, summary) {
  if (!summary) return [];
  const rows = [];
  const add = (name, value) => {
    if (value != null && value !== '') rows.push([name, value]);
  };
  switch (n) {
    case 1:
      add(tr('응답 헤더 도착', 'Response headers received'), duration(summary.headersMs));
      add(tr('브라우저와 BFF 사이 (왕복)', 'Browser to BFF (round trip)'), duration(summary.entryMs));
      add(tr('CloudFront가 요청을 받고 응답을 내보내기까지', 'CloudFront, request in to response out'), duration(summary.cdnDownstream));
      break;
    case 2:
      add(tr('CloudFront가 본 오리진의 응답 시간', 'Origin response time seen by CloudFront'), duration(summary.cdnUpstream));
      add(tr('BFF가 게이트웨이로 보낸 뒤 응답 헤더까지', 'BFF send to gateway until response headers'), duration(summary.upstreamMs));
      break;
    case 4:
      add(tr('결정 방식', 'Decided by'), DECISIONS[summary.decision] ?? summary.decision);
      add(tr('BFF의 판단', 'BFF decision'), duration(summary.decideMs));
      if (summary.wakeMs != null && sideOf(summary.model) === 'qwen') {
        add(summary.woke ? tr('잠든 Qwen을 깨움', 'Woke sleeping Qwen') : tr('깨우기 확인', 'Wake check'), duration(summary.wakeMs));
      }
      if (summary.asked) {
        add(tr('웹 검색 도구', 'Web search tool'), SEARCH_STATES[summary.search] ?? tr('BFF가 알려 주지 않음', 'Not reported by the BFF'));
      }
      break;
    case 5:
      add(summary.firstKind === 'reasoning' ? tr('첫 조각 (추론)', 'First chunk (reasoning)') : tr('첫 조각 (TTFT)', 'First chunk (TTFT)'), duration(summary.ttft));
      add(tr('조각 간격 중앙값', 'Median chunk interval'), duration(summary.gap));
      add(tr('토큰당 시간 (TPOT)', 'Time per token (TPOT)'), duration(summary.tpot));
      break;
    case 6:
      if (summary.chunks) {
        add(tr('추론 조각', 'Reasoning chunks'), tr(`${count(summary.reasoningChunks)}개`, count(summary.reasoningChunks)));
        add(tr('답변 조각', 'Answer chunks'), tr(`${count(summary.contentChunks)}개`, count(summary.contentChunks)));
      }
      add('finish_reason', summary.finishReason);
      if (summary.searches.length) {
        const done = summary.searches.filter((search) => !search.error);
        const results = done.reduce((sum, search) => sum + search.count, 0);
        const failed = summary.searches.length - done.length;
        add(tr('웹 검색', 'Web search'), tr(`${count(summary.searches.length)}회`, plural(summary.searches.length, 'call')));
        add(tr('검색 결과', 'Search results'), tr(`${count(results)}건`, count(results)));
        add(tr('검색 시간', 'Search time'), summary.searches.filter((search) => search.searchMs != null).map((search) => duration(search.searchMs)).join(', '));
        if (failed) add(tr('실패한 검색', 'Failed searches'), tr(`${count(failed)}회`, count(failed)));
      } else if (summary.search === 'on') {
        add(tr('웹 검색', 'Web search'), tr('모델이 부르지 않음', 'Not called by the model'));
      }
      break;
    case 7:
      add(tr('전체 시간 (E2E)', 'Total time (E2E)'), duration(summary.totalMs));
      if (summary.inputTokens != null) add(tr('입력 토큰 (usage)', 'Input tokens (usage)'), tr(`${count(summary.inputTokens)}개`, count(summary.inputTokens)));
      if (summary.outputTokens != null) add(tr('출력 토큰 (usage)', 'Output tokens (usage)'), tr(`${count(summary.outputTokens)}개`, count(summary.outputTokens)));
      if (summary.sources.length) add(tr('출처', 'Sources'), tr(`${count(summary.sources.length)}개`, count(summary.sources.length)));
      break;
    case 8:
      add(tr('요청 ID', 'Request ID'), summary.requestId);
      break;
    default:
      break;
  }
  return rows;
}

// 첫 내용까지의 시간을 구간으로 나눈 띠. 측정값은 네 구간, 실제 요청은 브라우저가 가를 수 있는 세 구간이다.
export function budgetRows(side, summary) {
  const m = M[side];
  const rows = [{
    key: 'measured',
    // 이름 칸(11.5em)에 값과 한 줄로 들어가도록 영어는 짧게 쓴다. 8단계 측정이라는 설명은 위의 값 목록 제목에 있다.
    label: tr('8단계 중앙값', 'Measured'),
    total: m.first_content,
    parts: [
      { key: 'entry', name: tr('진입', 'Entry'), value: D[side].entry },
      { key: 'bff', name: 'BFF', value: m.bff },
      { key: 'gateway', name: tr('게이트웨이', 'Gateway'), value: m.gateway },
      { key: 'engine', name: 'vLLM', value: m.vllm_ttft },
    ],
  }];
  if (summary?.ttft != null && summary.entryMs != null) {
    rows.push({
      key: 'live',
      label: tr('이 요청', 'This request'),
      total: summary.ttft,
      parts: [
        { key: 'entry', name: tr('진입 (왕복)', 'Entry (round trip)'), value: summary.entryMs },
        { key: 'bff', name: 'BFF', value: summary.bffMs },
        // 웹 검색을 부른 요청은 첫 조각 전에 검색과 다시 추론이 끼어들 수 있다. 브라우저는 그 시간을 가르지 못한다.
        { key: 'engine',
          name: summary.searches.length ? tr('게이트웨이, vLLM, 웹 검색', 'Gateway, vLLM, web search') : tr('게이트웨이와 vLLM', 'Gateway and vLLM'),
          value: Math.max(0, summary.ttft - summary.entryMs - summary.bffMs) },
      ],
    });
  }
  const scale = Math.max(...rows.map((row) => row.parts.reduce((sum, part) => sum + part.value, 0)));
  return rows.map((row) => ({
    ...row,
    parts: row.parts.map((part) => ({ ...part, percent: (part.value / scale) * 100 })),
  }));
}

// 요청 경로의 노드와, 그 사이의 선. PATH_EDGES[i]는 PATH[i]에서 PATH[i + 1]로 가는 선이다.
const PATH = ['user', 'cf', 'alb', 'bff', 'gw'];
const PATH_EDGES = ['user-cf', 'cf-alb', 'alb-bff', 'bff-gw'];

// 단계 n을 지도(flow-map.svg)의 노드, 선, 값으로 바꾼다.
//   now  이 단계의 일을 하는 구성 요소      on  요청이 이 단계까지 지나온 구성 요소
//   off  이 요청이 쓰지 않는 구성 요소      stream  응답 조각이 돌아오는 선
// summary(실제 요청의 값)가 있으면 그 요청의 값을 적고, 없으면 8단계 측정 중앙값을 적는다.
// webSearch가 켜져 있으면 6단계에서 Web Search가 일하고, 꺼져 있으면 4단계부터 쓰지 않는 것으로 흐리게 한다.
// 값은 지도의 노드 아래 좁은 자리에 들어가므로 영어도 짧게 쓴다.
export function mapFor(n, side, summary = null, webSearch = false) {
  const m = M[side];
  const other = side === 'gemma' ? 'qwen' : 'gemma';
  const nodes = {};
  const edges = {};
  const values = {};
  const set = (names, state, target = nodes) => names.forEach((name) => { target[name] = state; });
  const live = (value, fallback) => (value != null ? duration(value) : duration(fallback));
  const useOther = (state) => {
    nodes[other] = state;
    edges[`gw-${other}`] = state;
  };
  const wake = (state) => {
    if (side === 'qwen') {
      nodes.wake = state;
      set(['bff-wake', 'wake-qwen'], 'on', edges);
    } else {
      nodes.wake = 'off';
      set(['bff-wake', 'wake-qwen'], 'off', edges);
    }
  };

  switch (n) {
    case 1:
      set(['user', 'alb'], 'on');
      set(['cf', 'bff', 'cognito'], 'now');
      set(PATH_EDGES.slice(0, 3), 'on', edges);
      values.user = tr(`엣지까지 ${duration(m.edge)}`, `To edge ${duration(m.edge)}`);
      values.cf = `CloudFront ${duration(m.cloudfront)}`;
      values.bff = tr('토큰 검증', 'Token check');
      break;
    case 2:
      set(['user', 'cf', 'bff'], 'on');
      set(['alb', 'gw'], 'now');
      set(PATH_EDGES, 'on', edges);
      values.alb = `ALB ${duration(m.alb)}`;
      values.gw = tr(`구간 ${duration(m.gateway)}`, `Segment ${duration(m.gateway)}`);
      break;
    case 3:
      set(PATH, 'on');
      set(PATH_EDGES, 'on', edges);
      nodes[side] = 'now';
      edges[`gw-${side}`] = 'on';
      useOther('off');
      wake('on');
      values[side] = tr(`한도 ${count(m.max_model_len)}토큰`, `Limit ${count(m.max_model_len)} tokens`);
      break;
    case 4: {
      set(['user', 'cf', 'alb'], 'on');
      set(['bff', 'gw', 'decider'], 'now');
      set(PATH_EDGES, 'on', edges);
      edges['gw-decider'] = 'on';
      useOther('off');
      wake('now');
      const decide = live(summary?.decideMs, m.decide);
      values.bff = tr(`판단 ${decide}`, `Decision ${decide}`);
      values.gw = `EPP ${duration(M.epp_ms)}`;
      values.decider = `${M.decider_ms[0]}~${M.decider_ms[1]}ms`;
      if (side === 'qwen') {
        values.wake = `${summary?.woke ? tr('깨움', 'Woke') : tr('확인', 'Check')} ${live(summary?.wakeMs, m.wake_check)}`;
      }
      break;
    }
    case 5:
      set(PATH, 'on');
      set(PATH_EDGES, 'on', edges);
      nodes[side] = 'now';
      edges[`gw-${side}`] = 'on';
      useOther('off');
      wake('on');
      values[side] = summary?.gap != null
        ? tr(`조각 간격 ${duration(summary.gap)}`, `Interval ${duration(summary.gap)}`)
        : `Prefill ${duration(m.prefill)}`;
      break;
    case 6:
      set(PATH, 'on');
      set(PATH_EDGES, 'on', edges);
      set([side, 'bff'], 'now');
      edges[`gw-${side}`] = 'on';
      useOther('off');
      wake('on');
      values[side] = 'detokenize, parser';
      values.bff = tr('도구 실행', 'Runs tools');
      break;
    case 7: {
      set(PATH, 'on');
      nodes.user = 'now';
      nodes[side] = 'on';
      set(PATH_EDGES, 'stream', edges);
      edges[`gw-${side}`] = 'stream';
      useOther('off');
      wake('on');
      const first = live(summary?.ttft, m.first_content);
      values.user = tr(`첫 내용 ${first}`, `1st content ${first}`);
      values.bff = tr('그대로 전달', 'Relays as is');
      values[side] = tr('usage 전송', 'Sends usage');
      break;
    }
    case 8:
      set(['user'], 'on');
      set(['cf', 'alb', 'bff', 'gw', side, 'amp'], 'now');
      set(PATH_EDGES, 'on', edges);
      edges[`gw-${side}`] = 'on';
      useOther('off');
      wake('on');
      values.cf = 'Server-Timing';
      values.alb = tr('접근 로그', 'Access logs');
      values.bff = 'chat, chat_end';
      values.gw = tr('지표', 'Metrics');
      values[side] = tr('지표', 'Metrics');
      values.amp = tr('파드 8개 수집', 'Scrapes 8 pods');
      break;
    default:
      break;
  }
  if (!webSearch && n >= 4) {
    nodes.search = 'off';
    edges['bff-search'] = 'off';
  } else if (webSearch && n >= 6) {
    nodes.search = n === 6 ? 'now' : 'on';
    edges['bff-search'] = 'on';
    const first = summary?.searches.find((search) => search.searchMs != null);
    values.search = first
      ? tr(`검색 ${duration(first.searchMs)}`, `Search ${duration(first.searchMs)}`)
      : `${SEARCH.ms[0]}~${count(SEARCH.ms[1])}ms`;
  }
  return { nodes, edges, values };
}

// 실제 요청이 진행되는 동안의 지도. 브라우저가 아는 만큼만 표시한다.
export function mapForLive(live) {
  const nodes = {};
  const edges = {};
  const values = {};
  const set = (names, state, target = nodes) => names.forEach((name) => { target[name] = state; });
  const summary = summarizeLive(live);
  const side = sideOf(live.info?.model) ?? live.side;
  const other = side === 'gemma' ? 'qwen' : 'gemma';

  if (live.phase === 'failed') {
    const status = live.status ?? 0;
    const at = status === 403 || status === 0 ? 'cf' : status === 401 || status === 400 || status === 422 ? 'bff' : 'gw';
    const reached = PATH.slice(0, PATH.indexOf(at));
    set(reached, 'on');
    set(PATH_EDGES.slice(0, reached.length), 'on', edges);
    nodes[at] = 'fail';
    values[at] = status === 403 ? tr('WAF가 차단', 'Blocked by WAF')
      : status === 401 ? tr('토큰 거절', 'Token rejected')
        : status === 0 ? tr('연결 실패', 'Connection failed')
          : tr(`응답 ${status}`, `Response ${status}`);
    return { nodes, edges, values };
  }
  if (live.phase === 'sending') {
    set(['user', 'cf', 'alb'], 'on');
    set(PATH_EDGES.slice(0, 3), 'on', edges);
    nodes.bff = 'now';
    values.bff = tr('처리 중', 'Processing');
    return { nodes, edges, values };
  }

  const streaming = live.phase === 'streaming';
  set(PATH, 'on');
  set(PATH_EDGES, streaming ? 'stream' : 'on', edges);
  nodes[side] = live.phase === 'done' ? 'on' : 'now';
  edges[`gw-${side}`] = streaming ? 'stream' : 'on';
  nodes[other] = 'off';
  edges[`gw-${other}`] = 'off';
  nodes.wake = side === 'qwen' ? 'on' : 'off';
  set(['bff-wake', 'wake-qwen'], side === 'qwen' ? 'on' : 'off', edges);
  if (summary.decideMs != null) values.bff = tr(`판단 ${duration(summary.decideMs)}`, `Decision ${duration(summary.decideMs)}`);
  if (side === 'qwen' && summary.wakeMs != null) {
    values.wake = `${summary.woke ? tr('깨움', 'Woke') : tr('확인', 'Check')} ${duration(summary.wakeMs)}`;
  }
  if (summary.upstreamMs != null) values.gw = tr(`응답 헤더 ${duration(summary.upstreamMs)}`, `Headers ${duration(summary.upstreamMs)}`);
  // 검색 알림은 BFF가 검색을 끝낸 뒤에 온다. 알림이 오면 Web Search를 지나온 것으로 표시한다.
  if (summary.searches.length) {
    nodes.search = 'on';
    edges['bff-search'] = 'on';
    values.search = tr(`검색 ${summary.searches.length}회`, plural(summary.searches.length, 'search', 'searches'));
  } else if (!live.asked || (summary.search && summary.search !== 'on')) {
    nodes.search = 'off';
    edges['bff-search'] = 'off';
  }
  if (summary.ttft != null) {
    const chunks = tr(`조각 ${summary.chunks}개`, plural(summary.chunks, 'chunk'));
    values.user = tr(`첫 조각 ${duration(summary.ttft)}`, `1st chunk ${duration(summary.ttft)}`);
    values[side] = summary.gap != null ? `${chunks}, ${duration(summary.gap)}` : chunks;
  } else {
    values[side] = tr('첫 토큰 대기', 'Awaiting 1st token');
  }
  return { nodes, edges, values };
}

// 단계 띠의 상태. now는 진행 중이거나 지금 보는 단계, on은 지나온 단계다. 끝난 요청은 모든 단계를 지나온 것으로 둔다.
export function railStates(selected, live) {
  const states = {};
  const phase = live?.phase;
  for (const { n } of STAGES) {
    if (phase === 'sending') states[n] = n === 1 ? 'now' : '';
    else if (phase === 'engine') states[n] = n <= 4 ? 'on' : n === 5 ? 'now' : '';
    else if (phase === 'streaming') states[n] = n <= 4 ? 'on' : n <= 7 ? 'now' : '';
    else if (phase === 'done') states[n] = n === selected ? 'now' : 'on';
    else states[n] = n < selected ? 'on' : n === selected ? 'now' : '';
  }
  return states;
}

// 진행 중인 요청이 지금 보여 줄 단계
export function stageOfPhase(phase) {
  return phase === 'sending' ? 1 : phase === 'engine' || phase === 'streaming' ? 5 : null;
}
