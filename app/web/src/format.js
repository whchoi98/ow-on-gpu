import { locale, localized, tr } from './i18n.js';

export const MODELS = {
  'gemma-4-31b': { pen: 'gemma', name: 'Gemma 4 31B' },
  'qwen38-27b': { pen: 'qwen', name: 'Qwen3.8-27B' },
};

export const TASKS = localized(() => [
  { value: 'support', label: tr('상담', 'Support'), pen: 'gemma', hint: tr('Gemma, 주문 조회 도구 사용', 'Gemma, uses the order lookup tool') },
  { value: 'translate', label: tr('번역', 'Translation'), pen: 'gemma', hint: tr('Gemma, 배치 우선순위', 'Gemma, batch priority') },
  // 영어 이름은 용어표의 Summarization 대신 Summary로 줄였다. 업무 종류 카드에서 화면 폭 385px 이하일 때 낱말 중간에서 줄이 넘어갔다.
  { value: 'summarize', label: tr('요약', 'Summary'), pen: 'gemma', hint: tr('Gemma, 배치 우선순위', 'Gemma, batch priority') },
  { value: 'coding', label: tr('코딩', 'Coding'), pen: 'qwen', hint: tr('Qwen, 잠들어 있으면 먼저 깨움', 'Qwen, woken first if asleep') },
  { value: '', label: tr('자동', 'Auto'), pen: 'auto', hint: tr('Decider가 모델을 고름', 'Decider picks the model') },
]);

export const DECISIONS = localized(() => ({
  rule: tr('민감 정보 규칙으로 결정', 'Decided by sensitive data rule'),
  task: tr('업무 종류로 결정', 'Decided by task type'),
  attachment: tr('첨부 파일로 결정', 'Decided by attachment'),
  decider: tr('Decider가 결정', 'Decided by Decider'),
  fallback: tr('판단 실패, 기본값 사용', 'Decision failed, default used'),
}));

// 요청이 웹 검색을 켰는데 BFF가 도구를 붙이지 않은 이유(x-bff-search)
export const SEARCH_OFF = localized(() => ({
  sensitive: tr('민감 정보가 있는 요청이라 웹 검색을 쓰지 않았습니다.', 'Web search was not used because the request contains sensitive data.'),
  // 모델을 정하지 못해 기본값(Gemma, 민감 정보 요청으로 다룸)으로 보낸 요청. 민감 정보가 있어서가 아니다.
  fallback: tr('모델을 정하지 못해 웹 검색을 쓰지 않았습니다.', 'Web search was not used because the model decision failed.'),
  disabled: tr('이 환경에는 웹 검색이 설정되어 있지 않습니다.', 'Web search is not configured in this environment.'),
}));

// 예시는 이 환경이 보여 주려는 경로별로 묶었다. 이름, 연락처, 번호는 모두 지어낸 값이다.
// 영어 질문에서도 주문 번호, 주민등록번호, 카드번호, 전화번호는 그대로 둔다. BFF의 규칙과 주문 조회 목 API가 이 값에 맞춰져 있다.
export const EXAMPLE_GROUPS = localized(() => [
  {
    title: tr('상담', 'Support'),
    items: [
      {
        label: tr('배송 중인 주문', 'In transit'),
        task: 'support',
        prompt: tr('주문 번호 A-1024의 배송 상태를 알려 주세요.', 'What is the delivery status of order number A-1024?'),
      },
      {
        label: tr('도착한 주문', 'Delivered'),
        task: 'support',
        prompt: tr('A-1025 주문은 언제 도착했나요? 택배사도 알려 주세요.', 'When did order A-1025 arrive? Tell me the carrier as well.'),
      },
      {
        label: tr('없는 주문', 'No such order'),
        task: 'support',
        prompt: tr('주문 번호 B-7777이 어디쯤 왔는지 확인해 주세요.', 'Please check where order number B-7777 is now.'),
      },
      {
        label: tr('반품 문의', 'Returns'),
        task: 'support',
        prompt: tr(
          '단순 변심으로 반품하면 배송비는 누가 부담하나요? 일반적인 기준을 세 줄로 알려 주세요.',
          'If I return an item because I changed my mind, who pays for shipping? Give me the general rule in three lines.',
        ),
      },
    ],
  },
  {
    title: tr('번역과 요약', 'Translate, summarize'),
    items: [
      {
        label: tr('상품 설명 번역', 'Product description'),
        task: 'translate',
        prompt: tr(
          '다음 상품 설명을 영어와 일본어로 번역해 주세요.\n\n가볍고 따뜻한 구스다운 패딩입니다. 생활 방수 원단을 써서 눈과 비에 강하고, 안쪽 주머니에 접어 넣어 휴대할 수 있습니다.',
          'Translate the following product description into Korean and Japanese.\n\nA light, warm goose down puffer jacket. The water-resistant fabric holds up in snow and rain, and the jacket folds into its inner pocket so you can carry it.',
        ),
      },
      {
        label: tr('리뷰 요약', 'Review summary'),
        task: 'summarize',
        prompt: tr(
          '다음 리뷰를 읽고 장점과 단점을 표로 요약해 주세요.\n\n1. 배송이 하루 만에 왔고 포장이 꼼꼼했습니다.\n2. 색상이 사진보다 어둡습니다. 그래도 마감은 좋습니다.\n3. 한 치수 작게 나왔습니다. 교환 절차는 간단했습니다.\n4. 세탁 후에 보풀이 조금 생겼습니다.\n5. 가격에 비해 따뜻하고 가볍습니다.',
          'Read the following reviews and summarize the pros and cons in a table.\n\n1. It arrived in one day and was packed with care.\n2. The color is darker than in the photos. The finish is still good.\n3. It runs one size small. The exchange process was simple.\n4. Some pilling appeared after washing.\n5. It is warm and light for the price.',
        ),
      },
    ],
  },
  {
    title: tr('코딩', 'Coding'),
    items: [
      {
        label: tr('함수 작성', 'Write a function'),
        task: 'coding',
        prompt: tr(
          '파이썬으로 리스트의 중복을 순서를 유지하면서 제거하는 함수를 작성하고, 사용 예를 표로 정리해 주세요.',
          'Write a Python function that removes duplicates from a list while keeping the order, and show usage examples in a table.',
        ),
      },
      {
        label: tr('SQL 다듬기', 'Tidy up SQL'),
        task: 'coding',
        prompt: tr(
          '다음 SQL을 읽기 쉽게 고치고, 어떤 인덱스가 도움이 되는지 알려 주세요.\n\nselect o.id,o.created_at,c.name from orders o,customers c where o.customer_id=c.id and o.status=\'PAID\' and o.created_at>=\'2026-11-01\' order by o.created_at desc limit 50',
          'Rewrite the following SQL so it is easier to read, and tell me which indexes would help.\n\nselect o.id,o.created_at,c.name from orders o,customers c where o.customer_id=c.id and o.status=\'PAID\' and o.created_at>=\'2026-11-01\' order by o.created_at desc limit 50',
        ),
      },
      {
        label: tr('셸 한 줄', 'Shell one-liner'),
        task: 'coding',
        prompt: tr(
          'nginx 접근 로그에서 5xx 응답 수를 시간대별로 세는 bash 한 줄 명령을 작성하고 각 부분을 설명해 주세요.',
          'Write a bash one-liner that counts 5xx responses per hour in an nginx access log, and explain each part.',
        ),
      },
    ],
  },
  {
    title: tr('Decider 판단', 'Decider decision'),
    items: [
      {
        label: tr('코드 수정', 'Bug fix'),
        task: '',
        prompt: tr(
          '이 파이썬 코드의 버그를 고쳐 주세요.\n\ndef add(a, b):\n    return a - b',
          'Fix the bug in this Python code.\n\ndef add(a, b):\n    return a - b',
        ),
      },
      {
        label: tr('단계별 설계', 'Stepwise design'),
        task: '',
        prompt: tr(
          '구간 목록을 병합하는 파이썬 함수를 설계해 주세요. 겹치는 구간을 합치고, 합친 뒤 구간 수를 세고, 시간 복잡도를 단계별로 분석해 주세요.',
          'Design a Python function that merges a list of intervals. Merge the overlapping intervals, count the intervals after merging, and analyze the time complexity step by step.',
        ),
      },
      {
        label: tr('생활 문의', 'Daily life'),
        task: '',
        prompt: tr(
          '겨울철 니트를 줄어들지 않게 세탁하는 방법을 세 줄로 알려 주세요.',
          'Tell me in three lines how to wash a winter knit sweater so it does not shrink.',
        ),
      },
      {
        label: tr('요금 계산', 'Pricing'),
        task: '',
        prompt: tr(
          '요금제 A는 월 9,900원이고 요금제 B는 연 99,000원입니다. 2년 동안 쓰면 어느 쪽이 얼마나 쌉니까?',
          'Plan A costs 9,900 won per month and plan B costs 99,000 won per year. Over two years, which one is cheaper and by how much?',
        ),
      },
      {
        label: tr('배송지 변경', 'New address'),
        task: '',
        prompt: tr(
          '제 이름은 김민수이고 연락처는 010-1234-5678입니다. 배송지를 서울시 강남구 테헤란로 1로 바꿔 주세요.',
          'My name is Minsu Kim and my phone number is 010-1234-5678. Please change my delivery address to 1 Teheran-ro, Gangnam-gu, Seoul.',
        ),
      },
    ],
  },
  {
    // search: true인 예시는 웹 검색을 켠다. 모델이 web_search 도구를 불러 검색하고 출처 번호를 달아 답한다.
    title: tr('웹 검색', 'Web search'),
    items: [
      {
        label: tr('제공 리전 확인', 'Regions'),
        task: '',
        search: true,
        prompt: tr(
          'Amazon Bedrock AgentCore Web Search API를 쓸 수 있는 AWS 리전을 검색해서 알려 주세요.',
          'Search for the AWS Regions where the Amazon Bedrock AgentCore Web Search API is available and tell me.',
        ),
      },
      {
        label: tr('릴리스 변경점', 'Release notes'),
        task: 'coding',
        search: true,
        prompt: tr(
          'Kubernetes 최신 릴리스의 주요 변경점을 검색해서 세 가지로 정리해 주세요.',
          'Search for the main changes in the latest Kubernetes release and summarize them in three points.',
        ),
      },
      {
        label: tr('검색 결과 요약', 'Search summary'),
        task: 'summarize',
        search: true,
        prompt: tr(
          '이번 주 서울 날씨 예보를 검색해서 세 줄로 요약해 주세요.',
          "Search for this week's weather forecast for Seoul and summarize it in three lines.",
        ),
      },
      {
        label: tr('민감 정보와 검색', 'Sensitive data'),
        task: '',
        search: true,
        prompt: tr(
          '제 주민등록번호 900101-1234567로 가입된 서비스가 있는지 검색해 주세요.',
          'Search for any services signed up with my resident registration number 900101-1234567.',
        ),
      },
    ],
  },
  {
    title: tr('데이터 정책', 'Data policy'),
    items: [
      {
        label: tr('주민등록번호', 'Resident reg. number'),
        task: 'coding',
        prompt: tr(
          '제 주민등록번호는 900101-1234567입니다. 이 번호의 형식을 검사하는 코드를 작성해 주세요.',
          'My resident registration number is 900101-1234567. Write code that validates the format of this number.',
        ),
      },
      {
        label: tr('카드번호', 'Card number'),
        task: 'support',
        prompt: tr(
          '카드 4111 1111 1111 1111로 결제했는데 두 번 결제된 것 같습니다. 확인하는 방법을 알려 주세요.',
          'I paid with card 4111 1111 1111 1111 and I think I was charged twice. Tell me how to check.',
        ),
      },
    ],
  },
]);

const TASK_NAMES = localized(() => ({
  support: tr('상담', 'Support'),
  translate: tr('번역', 'Translation'),
  summarize: tr('요약', 'Summary'),
  vision: tr('이미지 이해', 'Image understanding'),
  ocr: 'OCR',
  coding: tr('코딩', 'Coding'),
}));
const PATTERNS = localized(() => ({ rrn: tr('주민등록번호', 'resident registration number'), card: tr('카드번호', 'card number') }));
// 조사가 모델 이름의 받침에 따라 달라진다. 한국어 문장에만 쓰고, 영어 문장은 NAMES의 이름을 쓴다.
const TO = { gemma: 'Gemma로', qwen: 'Qwen으로' };
const OBJECT = { gemma: 'Gemma를', qwen: 'Qwen을' };
const NAMES = { gemma: 'Gemma', qwen: 'Qwen' };
const score = (value) => Number(value).toFixed(2);
// 기준보다 낮은 값이 반올림 때문에 기준과 같아 보이지 않게 한 자리 더 보여 준다(예: 0.598과 기준 0.60).
const below = (value, limit) => (score(value) === score(limit) ? Number(value).toFixed(3) : score(value));

// BFF가 응답 헤더(x-bff-reason)로 준 근거를 문장으로 푼다. Decider는 이유를 글로 돌려주지 않고
// 모델 선택과 신뢰도, 개인정보일 확률, 추론이 필요할 확률을 돌려준다.
export function explain(decision, reason) {
  if (!reason) return [];
  const lines = [];
  const route = NAMES[reason.route] ?? reason.route;
  if (decision === 'rule') {
    lines.push(tr(
      `요청에 ${PATTERNS[reason.pattern] ?? '민감 정보'} 형식이 있어 Decider에 묻지 않고 Gemma로 보냈습니다. 민감 정보가 든 요청은 Gemma로만 보냅니다.`,
      `The request contains a ${PATTERNS[reason.pattern] ?? 'sensitive data'} pattern, so it was sent to Gemma without asking Decider. Requests with sensitive data go only to Gemma.`,
    ));
    if (reason.during_session) {
      lines.push(tr('이 세션에서 앞서 내린 결정보다 이 규칙을 먼저 적용했습니다.', 'This rule was applied ahead of the decision made earlier in this session.'));
    }
  } else if (decision === 'task') {
    lines.push(tr(
      `업무 종류(${TASK_NAMES[reason.task] ?? reason.task})의 배정표에 따라 보냈습니다. Decider에는 묻지 않았습니다.`,
      `Sent according to the assignment table for the task type (${TASK_NAMES[reason.task] ?? reason.task}). Decider was not asked.`,
    ));
  } else if (decision === 'attachment') {
    lines.push(tr('이미지가 첨부되어 Qwen으로 보냈습니다. Decider에는 묻지 않았습니다.', 'An image is attached, so it was sent to Qwen. Decider was not asked.'));
  } else if (decision === 'decider') {
    lines.push(tr(
      `Decider가 ${OBJECT[reason.route] ?? reason.route} 골랐습니다. 신뢰도는 ${score(reason.route_confidence)}로 기준 ${score(reason.min_confidence)} 이상입니다.`,
      `Decider picked ${route}. The confidence is ${score(reason.route_confidence)}, at or above the threshold of ${score(reason.min_confidence)}.`,
    ));
    lines.push(reason.policy >= 0.5
      ? tr(`개인정보가 들어 있을 확률을 ${score(reason.policy)}로 보아 Gemma로 보냈습니다.`,
        `It put the probability of personal data at ${score(reason.policy)}, so the request was sent to Gemma.`)
      : tr(`개인정보가 들어 있을 확률은 ${score(reason.policy)}로 낮게 보았습니다.`,
        `It put the probability of personal data at ${score(reason.policy)}, which is low.`));
    lines.push(tr(
      `여러 단계의 추론이 필요할 확률은 ${score(reason.thinking)}여서 thinking을 ${reason.thinking >= 0.5 ? '켰습니다' : '껐습니다'}.`,
      `The probability that multi-step reasoning is needed is ${score(reason.thinking)}, so thinking was turned ${reason.thinking >= 0.5 ? 'on' : 'off'}.`,
    ));
  } else if (decision === 'fallback') {
    if (reason.why === 'low_confidence') {
      const short = [];
      if (reason.low?.includes('route')) {
        short.push(tr(`모델 선택의 신뢰도(${below(reason.route_confidence, reason.min_confidence)})`,
          `the model choice confidence (${below(reason.route_confidence, reason.min_confidence)})`));
      }
      if (reason.low?.includes('policy')) {
        short.push(tr(`개인정보 판단의 신뢰도(${below(reason.policy_confidence, reason.min_confidence)})`,
          `the personal data confidence (${below(reason.policy_confidence, reason.min_confidence)})`));
      }
      lines.push(tr(
        `Decider에 물었지만 ${short.join('와 ')}가 기준 ${score(reason.min_confidence)}보다 낮아 그 판단을 쓰지 않았습니다.`,
        `Decider was asked, but ${short.join(' and ')} ${short.length > 1 ? 'were' : 'was'} below the threshold of ${score(reason.min_confidence)}, so its decision was not used.`,
      ));
      lines.push(tr(
        `Decider의 답은 ${TO[reason.route] ?? reason.route} 보내기, 개인정보일 확률 ${score(reason.policy)}, 추론이 필요할 확률 ${score(reason.thinking)}였습니다.`,
        `Decider answered: send to ${route}, personal data probability ${score(reason.policy)}, reasoning probability ${score(reason.thinking)}.`,
      ));
    } else if (reason.detail === 'timeout') {
      lines.push(tr(`Decider가 ${reason.timeout_s}초 안에 답하지 않았습니다.`, `Decider did not answer within ${reason.timeout_s} s.`));
    } else if (String(reason.detail || '').startsWith('status')) {
      lines.push(tr(`Decider가 오류로 응답했습니다(${reason.detail}).`, `Decider responded with an error (${reason.detail}).`));
    } else {
      lines.push(tr('Decider의 답을 받지 못했습니다.', 'No answer was received from Decider.'));
    }
    lines.push(tr('그래서 기본값인 Gemma, thinking 끔, 민감 정보 있음으로 처리했습니다.',
      'So the defaults were used: Gemma, thinking off, treated as containing sensitive data.'));
  }
  if (reason.cached && !reason.during_session) {
    lines.push(tr('이 세션에서 앞서 내린 결정을 다시 썼습니다.', 'The decision made earlier in this session was reused.'));
  }
  return lines;
}

// 숫자 표기는 로캘마다 한 번만 만든다.
const integers = {};
const integer = () => (integers[locale()] ??= new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 }));

export function ms(value) {
  if (value == null || Number.isNaN(value)) return '-';
  return `${integer().format(Math.round(value))}ms`;
}

export function seconds(value) {
  if (value == null) return '-';
  return tr(`${(value / 1000).toFixed(2)}초`, `${(value / 1000).toFixed(2)}s`);
}

export function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

// 내용 Chunk의 도착 시각으로 요약값을 만든다.
export function summarize(ticks) {
  const content = ticks.filter((tick) => tick.kind === 'content').map((tick) => tick.ms);
  const gaps = content.slice(1).map((value, index) => value - content[index]);
  const reasoning = ticks.filter((tick) => tick.kind === 'reasoning').map((tick) => tick.ms);
  return { firstMs: content[0] ?? null, gapMs: median(gaps), count: content.length, reasoningMs: reasoning[0] ?? null,
           reasoningCount: reasoning.length };
}

export function percentile(values, q) {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * q))];
}

// 글의 한글 비율. 추론 과정이 한국어인지 가릴 때 쓴다.
export function koreanShare(text) {
  const hangul = (text.match(/[가-힣]/g) || []).length;
  const latin = (text.match(/[A-Za-z]/g) || []).length;
  return hangul + latin === 0 ? 1 : hangul / (hangul + latin);
}

// 성능 평가: 요청 하나의 결과에서 견줄 값을 뽑는다.
export function measure(ticks, totalMs, usage) {
  const content = ticks.filter((tick) => tick.kind === 'content').map((tick) => tick.ms);
  const gaps = content.slice(1).map((value, index) => value - content[index]);
  const tokens = usage?.completion_tokens ?? null;
  const span = content.length > 1 ? (content[content.length - 1] - content[0]) / 1000 : null;
  return {
    firstMs: content[0] ?? null,
    gaps,
    chunks: content.length,
    tokens,
    totalMs,
    // 첫 토큰이 나온 뒤의 생성 속도. 첫 토큰까지의 시간은 넣지 않는다.
    tokensPerSecond: tokens && tokens > 1 && span ? (tokens - 1) / span : null,
  };
}

// 성능 평가: 한 모델의 요청 결과들을 한 줄로 줄인다.
export function aggregate(results, rounds) {
  const ok = results.filter((result) => !result.error);
  const numbers = (key) => ok.map((result) => result[key]).filter((value) => value != null);
  const gaps = ok.flatMap((result) => result.gaps);
  const throughput = rounds
    .map((round) => {
      const tokens = ok.filter((result) => result.round === round.index).reduce((sum, result) => sum + (result.tokens ?? 0), 0);
      return round.wallMs ? tokens / (round.wallMs / 1000) : null;
    })
    .filter((value) => value != null);
  return {
    sent: results.length,
    failed: results.length - ok.length,
    firstMedian: median(numbers('firstMs')),
    firstMin: numbers('firstMs').length ? Math.min(...numbers('firstMs')) : null,
    firstMax: numbers('firstMs').length ? Math.max(...numbers('firstMs')) : null,
    // Chunk 하나에 담겨 온 토큰 수. speculative decoding을 쓰는 모델은 1보다 크다.
    tokensPerChunk: median(ok.filter((result) => result.tokens && result.chunks).map((result) => result.tokens / result.chunks)),
    gapMedian: median(gaps),
    gapP95: percentile(gaps, 0.95),
    tokensPerSecond: median(numbers('tokensPerSecond')),
    throughput: throughput.length ? throughput.reduce((sum, value) => sum + value, 0) / throughput.length : null,
    tokens: median(numbers('tokens')),
    totalMedian: median(numbers('totalMs')),
  };
}

const SLO = { firstMs: 500, gapMs: 50 };  // 이 환경의 기준: 첫 토큰 500ms, 토큰 간격 50ms
const ratio = (a, b) => (a / b).toFixed(1);
const rate = (value) => tr(`초당 ${value.toFixed(1)}토큰`, `${value.toFixed(1)} tokens/s`);

// 성능 평가의 결과를 문장으로 정리한다. 문장의 수치는 모두 표의 값에서 계산한다.
// 한국어 문장은 조사를 모델 이름에 맞춰 고치고(Qwen가를 Qwen이로), 영어 문장은 따로 쓴다.
export function analyze(summary, { concurrency, rounds }) {
  const { gemma, qwen } = summary;
  const lines = [];
  const done = (side) => side.sent - side.failed;
  if (!done(gemma) || !done(qwen)) {
    for (const [key, side] of Object.entries(summary)) {
      if (side.sent && !done(side)) {
        lines.push(tr(`${NAMES[key]} 요청이 모두 실패해 두 모델을 견줄 수 없습니다.`,
          `All ${NAMES[key]} requests failed, so the two models cannot be compared.`));
      }
    }
    return lines;
  }
  const sides = Object.entries(summary);
  const faster = (key, low = true) => {
    const [a, b] = sides;
    return (low ? a[1][key] <= b[1][key] : a[1][key] >= b[1][key]) ? [a, b] : [b, a];
  };

  if (gemma.firstMedian != null && qwen.firstMedian != null) {
    const [[winner, w], [loser, l]] = faster('firstMedian');
    lines.push(tr(
      `첫 토큰은 ${NAMES[winner]}가 ${ms(w.firstMedian)}로 ${NAMES[loser]}(${ms(l.firstMedian)})보다 ${ms(l.firstMedian - w.firstMedian)} 빨랐습니다.`
        .replace('Qwen가', 'Qwen이'),
      `${NAMES[winner]} sent its first token in ${ms(w.firstMedian)}, ${ms(l.firstMedian - w.firstMedian)} faster than ${NAMES[loser]} (${ms(l.firstMedian)}).`,
    ));
    if (rounds * concurrency > 1) {
      lines.push(tr(
        `요청마다의 첫 토큰은 Gemma ${ms(gemma.firstMin)}에서 ${ms(gemma.firstMax)}, Qwen ${ms(qwen.firstMin)}에서 ${ms(qwen.firstMax)} 사이였습니다.`,
        `Across requests, the first token ranged from ${ms(gemma.firstMin)} to ${ms(gemma.firstMax)} for Gemma and from ${ms(qwen.firstMin)} to ${ms(qwen.firstMax)} for Qwen.`,
      ));
    }
  }

  if (gemma.tokensPerSecond != null && qwen.tokensPerSecond != null) {
    const [[winner, w], [loser, l]] = faster('tokensPerSecond', false);
    lines.push(tr(
      `요청 하나의 생성 속도는 ${NAMES[winner]}가 ${rate(w.tokensPerSecond)}으로 ${NAMES[loser]}(${rate(l.tokensPerSecond)})의 ${ratio(w.tokensPerSecond, l.tokensPerSecond)}배입니다.`
        .replace('Qwen가', 'Qwen이'),
      `For a single request, ${NAMES[winner]} generated ${rate(w.tokensPerSecond)}, ${ratio(w.tokensPerSecond, l.tokensPerSecond)} times the speed of ${NAMES[loser]} (${rate(l.tokensPerSecond)}).`,
    ));
  }

  if (gemma.tokensPerChunk != null && qwen.tokensPerChunk != null && gemma.gapMedian != null && qwen.gapMedian != null) {
    const perToken = (side) => side.gapMedian / side.tokensPerChunk;
    lines.push(tr(
      `Chunk 하나에 담겨 온 토큰은 Gemma ${gemma.tokensPerChunk.toFixed(1)}개, Qwen ${qwen.tokensPerChunk.toFixed(1)}개입니다. ` +
        `Chunk 간격을 토큰 하나당 간격으로 바꾸면 Gemma ${ms(perToken(gemma))}, Qwen ${ms(perToken(qwen))}입니다.`,
      `Each chunk carried ${gemma.tokensPerChunk.toFixed(1)} tokens for Gemma and ${qwen.tokensPerChunk.toFixed(1)} for Qwen. ` +
        `Converted to an interval per token, the chunk interval is ${ms(perToken(gemma))} for Gemma and ${ms(perToken(qwen))} for Qwen.`,
    ));
    if (qwen.tokensPerChunk >= 1.5 && qwen.gapMedian > gemma.gapMedian && qwen.tokensPerSecond > gemma.tokensPerSecond) {
      lines.push(tr(
        'Qwen은 Chunk 사이의 간격이 더 길지만 한 번에 여러 토큰을 내보내서(speculative decoding) 생성 속도는 더 빠릅니다.',
        'Qwen has a longer interval between chunks, but it emits several tokens at a time (speculative decoding), so its generation speed is higher.',
      ));
    }
    const check = (side) => [side.firstMax <= SLO.firstMs, perToken(side) <= SLO.gapMs];
    const verdict = (key, side) => {
      const [first, gap] = check(side);
      return tr(
        `${NAMES[key]}는 첫 토큰 ${first ? '충족' : '미충족'}(가장 느린 요청 ${ms(side.firstMax)}), 토큰 간격 ${gap ? '충족' : '미충족'}(${ms(perToken(side))})`
          .replace('Qwen는', 'Qwen은'),
        `${NAMES[key]} first token ${first ? 'met' : 'not met'} (slowest request ${ms(side.firstMax)}), token interval ${gap ? 'met' : 'not met'} (${ms(perToken(side))})`,
      );
    };
    lines.push(tr(
      `이 환경의 기준(첫 토큰 500ms, 토큰 간격 50ms)과 견주면 ${verdict('gemma', gemma)}, ${verdict('qwen', qwen)}입니다.`,
      `Against the thresholds for this environment (first token 500ms, token interval 50ms): ${verdict('gemma', gemma)}; ${verdict('qwen', qwen)}.`,
    ));
  }

  if (gemma.throughput != null && qwen.throughput != null) {
    if (concurrency > 1) {
      const scale = (side) => ratio(side.throughput, side.tokensPerSecond ?? side.throughput);
      lines.push(tr(
        `모델마다 ${concurrency}개씩 동시에 보냈을 때 모델 전체 처리량은 Gemma ${rate(gemma.throughput)}, Qwen ${rate(qwen.throughput)}입니다. ` +
          `요청 하나의 생성 속도와 견주면 Gemma ${scale(gemma)}배, Qwen ${scale(qwen)}배입니다.`,
        `With ${concurrency} concurrent requests per model, the total throughput per model was ${rate(gemma.throughput)} for Gemma and ${rate(qwen.throughput)} for Qwen. ` +
          `That is ${scale(gemma)} times the single-request speed for Gemma and ${scale(qwen)} times for Qwen.`,
      ));
    } else {
      lines.push(tr(
        '동시 요청 수가 1이라 모델 전체 처리량은 요청 하나의 값과 같은 뜻입니다. 동시 요청 수를 올리면 처리량이 얼마나 늘고 첫 토큰이 얼마나 늦어지는지 볼 수 있습니다.',
        'With a concurrency of 1, the total throughput per model means the same as the single-request value. Raise the concurrency to see how much the throughput grows and how much later the first token arrives.',
      ));
    }
  }

  if (gemma.tokens && qwen.tokens && Math.max(gemma.tokens, qwen.tokens) / Math.min(gemma.tokens, qwen.tokens) > 1.2) {
    lines.push(tr(
      `답의 길이가 다릅니다(Gemma ${Math.round(gemma.tokens)}토큰, Qwen ${Math.round(qwen.tokens)}토큰). 전체 시간은 답의 길이에 좌우되므로 생성 속도로 견주는 편이 맞습니다.`,
      `The answers differ in length (Gemma ${Math.round(gemma.tokens)} tokens, Qwen ${Math.round(qwen.tokens)} tokens). Total time depends on the answer length, so generation speed is the better comparison.`,
    ));
  }
  for (const [key, side] of sides) {
    if (side.failed) {
      lines.push(tr(`${NAMES[key]} 요청 ${side.sent}건 중 ${side.failed}건이 실패해 계산에서 뺐습니다.`,
        `${side.failed} of ${side.sent} ${NAMES[key]} requests failed and ${side.failed === 1 ? 'was' : 'were'} left out of the calculation.`));
    }
  }
  if (done(gemma) < 5 || done(qwen) < 5) {
    const few = Math.min(done(gemma), done(qwen));
    lines.push(tr(`모델마다 요청 ${few}건으로 잰 값입니다. 반복 횟수를 늘리면 값이 덜 흔들립니다.`,
      `These values were measured with ${few} ${few === 1 ? 'request' : 'requests'} per model. More rounds make the values steadier.`));
  }
  return lines;
}
