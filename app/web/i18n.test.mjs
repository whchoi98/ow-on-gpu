// 한영 전환 확인. 문구가 든 자료가 두 언어에서 같은 모양인지, 영어 쪽에 한글이 남지 않았는지 본다.
// 화면 없이 src의 자료와 순수 함수만 본다.
//   node i18n.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { getLang, locale, localized, setLang, tr } from './src/i18n.js';
import { SIDES, STAGES, budgetRows, duration, mapFor, measuredRows, searchRows } from './src/apicall.js';
import { DEPLOY } from './src/deploy-steps.js';
import { buildFlow } from './src/flow.js';
import { MAP_EDGES, MAP_NODES, STEPS, stepFlow } from './src/flow-steps.js';
import { DECISIONS, EXAMPLE_GROUPS, SEARCH_OFF, TASKS, analyze, explain, ms, seconds } from './src/format.js';

const HANGUL = /[가-힣]/;

// 대리 객체를 지금 언어의 보통 값으로 떠 낸다.
const plain = (value) => JSON.parse(JSON.stringify(value));
// 값의 모양. 글과 숫자는 종류만, 객체와 배열은 키와 길이까지 본다.
const shape = (value) => (Array.isArray(value) ? value.map(shape)
  : value && typeof value === 'object' ? Object.fromEntries(Object.entries(value).map(([key, item]) => [key, shape(item)]))
    : typeof value);
// 값 안의 모든 글을 [위치, 글]로 모은다.
function texts(value, path = '') {
  if (typeof value === 'string') return [[path, value]];
  if (!value || typeof value !== 'object') return [];
  return Object.entries(value).flatMap(([key, item]) => texts(item, path ? `${path}.${key}` : key));
}
const inLang = (lang, make) => {
  setLang(lang);
  try {
    return plain(make());
  } finally {
    setLang('ko');
  }
};

// 기본 언어는 한국어다(node에는 저장된 선택이 없다). 지원하지 않는 값은 무시한다.
assert.equal(getLang(), 'ko');
assert.equal(tr('가', 'A'), '가');
assert.equal(locale(), 'ko-KR');
setLang('fr');
assert.equal(getLang(), 'ko');

// localized(): 불러올 때가 아니라 읽을 때의 언어를 따른다. 배열과 객체의 흔한 연산이 그대로 된다.
const LIST = localized(() => [{ n: 0, title: tr('가', 'A') }, { n: 1, title: tr('나', 'B') }]);
const TABLE = localized(() => ({ gemma: tr('상담', 'Support'), qwen: tr('코딩', 'Coding') }));
assert.ok(Array.isArray(LIST));
assert.deepEqual(LIST.map((item) => item.title), ['가', '나']);
assert.deepEqual(Object.keys(TABLE), ['gemma', 'qwen']);
setLang('en');
assert.equal(locale(), 'en-US');
assert.deepEqual([...LIST].map((item) => item.title), ['A', 'B']);
assert.equal(LIST.find((item) => item.n === 1).title, 'B');
assert.deepEqual(Object.values(TABLE), ['Support', 'Coding']);
assert.equal(LIST.length, 2);
setLang('ko');
assert.equal(LIST[1].title, '나');

// 영어에서도 한국어로 두는 글. 측정에 쓴 질문은 바꾸면 측정값과 맞지 않는다(영어 화면은 풀이를 덧붙인다).
const KEEP = [/^SIDES\.(gemma|qwen)\.(prompt|searchPrompt)$/];

// 문구가 든 자료: 두 언어의 모양이 같고, 한국어에는 한글이 있고, 영어에는 한글이 없다.
const DATA = { TASKS, DECISIONS, SEARCH_OFF, EXAMPLE_GROUPS, STEPS, STAGES, SIDES, DEPLOY };
for (const [name, value] of Object.entries(DATA)) {
  const ko = inLang('ko', () => value);
  const en = inLang('en', () => value);
  assert.deepEqual(shape(en), shape(ko), `${name}: 두 언어의 모양이 다르다`);
  assert.ok(texts(ko).some(([, text]) => HANGUL.test(text)), `${name}: 한국어 글이 없다`);
  for (const [path, text] of texts(en)) {
    const where = `${name}.${path}`;
    if (KEEP.some((pattern) => pattern.test(where))) continue;
    assert.ok(!HANGUL.test(text), `${where}: 영어에 한글이 남았다: ${text}`);
  }
}
// 웹 검색을 쓰지 않은 이유는 BFF가 알리는 값마다 있다. 기본값으로 보낸 요청의 문구는 민감 정보가 있다고 말하지 않고,
// 모델을 정하지 못한 것을 이유로 들지도 않는다(모델 선택만 불확실한 요청에는 검색이 붙는다).
for (const lang of ['ko', 'en']) {
  const off = inLang(lang, () => SEARCH_OFF);
  assert.deepEqual(Object.keys(off).sort(), ['disabled', 'fallback', 'sensitive']);
  assert.ok(!/민감|sensitive|모델을 정하지|model decision/i.test(off.fallback), off.fallback);
}
// 영어 화면에서 측정용 질문에 덧붙이는 풀이가 있다. 한국어 화면에서는 비어 있다.
for (const side of ['gemma', 'qwen']) {
  assert.equal(inLang('ko', () => SIDES)[side].promptGloss, '');
  assert.ok(inLang('en', () => SIDES)[side].promptGloss.length > 10);
}

// 영어 예시 질문에도 BFF의 규칙과 주문 조회 목 API가 쓰는 식별 값이 그대로 있다.
const prompts = (lang) => inLang(lang, () => EXAMPLE_GROUPS).flatMap((group) => group.items.map((item) => item.prompt)).join('\n');
for (const value of ['A-1024', 'A-1025', 'B-7777', '900101-1234567', '4111 1111 1111 1111', '010-1234-5678']) {
  assert.ok(prompts('ko').includes(value) && prompts('en').includes(value), value);
}

// 글을 만들어 돌려주는 함수: 영어에서 한글이 나오지 않는다.
const record = {
  state: 'done', model: 'qwen38-27b', decision: 'decider', toolCalls: 1,
  reason: { route: 'qwen', route_confidence: 0.93, min_confidence: 0.6, policy: 0.1, thinking: 0.7 },
  timing: { decide_ms: 152.3, wake_ms: 3661, woke: true, upstream_ms: 41 },
  searches: [{ query: 'q', searchMs: 568, count: 5 }, { query: 'q2', searchMs: 497, count: 5 }],
  cdn: { 'cdn-upstream-fbl': 35 },
  ticks: [{ kind: 'reasoning', ms: 120 }, { kind: 'content', ms: 400 }, { kind: 'content', ms: 470 }],
};
// BFF가 x-bff-reason으로 주는 값의 모양(markdown.test.mjs의 결정 이유 시험과 같은 값)
const reasons = [
  ['rule', { pattern: 'rrn', during_session: true, cached: true }],
  ['rule', { pattern: 'card' }],
  ['task', { task: 'translate' }],
  ['task', { task: 'coding' }],
  ['attachment', {}],
  ['decider', record.reason],
  ['decider', { route: 'qwen', route_confidence: 0.9, policy: 0.95, thinking: 0.2, min_confidence: 0.6 }],
  ['decider', { route: 'gemma', route_confidence: 0.9, policy: 0.1, thinking: 0.1, min_confidence: 0.6, cached: true }],
  ['fallback', { why: 'low_confidence', low: ['route'], route: 'gemma', route_confidence: 0.3, policy: 0.05,
    policy_confidence: 0.9, thinking: 0.54, min_confidence: 0.6 }],
  // 셋째 값은 BFF가 알린 민감 정보 여부. 모델 선택만 불확실했던 요청은 false로 온다.
  ['fallback', { why: 'low_confidence', low: ['route'], route: 'gemma', route_confidence: 0.3, policy: 0.05,
    policy_confidence: 0.9, thinking: 0.54, min_confidence: 0.6 }, false],
  ['fallback', { why: 'decider_unavailable', detail: 'timeout', timeout_s: 2 }],
];
const made = () => ({
  explain: reasons.map(([decision, reason, sensitive]) => explain(decision, reason, sensitive)),
  flows: [
    buildFlow(record),
    buildFlow({ ...record, state: 'streaming' }),
    buildFlow({ state: 'streaming', ticks: [] }),
    buildFlow({ ...record, decision: 'fallback', reason: { detail: 'timeout' } }),
    ...[403, 401, 0, 502].map((status) => buildFlow({ state: 'failed', status, ticks: [] })),
    ...STEPS.map((step) => stepFlow(step.n)),
  ],
  apicall: STAGES.flatMap((stage) => Object.keys(SIDES).map((side) => ({
    measured: measuredRows(stage.n, side),
    search: searchRows(stage.n, side),
    map: mapFor(stage.n, side, null, true),
    budget: budgetRows(side, null),
  }))),
  units: [ms(1234.5), seconds(4567), duration(1234), duration(12345)],
});
const koMade = inLang('ko', made);
const enMade = inLang('en', made);
assert.deepEqual(shape(enMade), shape(koMade), '함수가 돌려준 값의 모양이 언어마다 다르다');
assert.ok(texts(koMade).some(([, text]) => HANGUL.test(text)));
for (const [path, text] of texts(enMade)) assert.ok(!HANGUL.test(text), `${path}: 영어에 한글이 남았다: ${text}`);
// 성능 평가의 결과 분석(markdown.test.mjs의 분석 시험과 같은 값). 두 언어의 문장 수가 같고 영어에 한글이 없다.
const side = (first, gap, tokensPerSecond, tokensPerChunk, tokens, extra = {}) => ({ sent: 3, failed: 0, firstMedian: first,
  firstMin: first - 5, firstMax: first + 10, gapMedian: gap, tokensPerSecond, tokensPerChunk, throughput: tokensPerSecond, tokens, ...extra });
const analyses = () => [
  analyze({ gemma: side(186, 54, 19.6, 1.0, 21), qwen: side(382, 70, 39.3, 2.8, 31) }, { concurrency: 1, rounds: 3 }),
  analyze({ gemma: side(300, 60, 15, 1, 100, { throughput: 52 }), qwen: side(350, 80, 30, 3, 100, { throughput: 95 }) }, { concurrency: 4, rounds: 3 }),
  analyze({ gemma: side(186, 54, 19.6, 1, 21), qwen: { sent: 3, failed: 3 } }, { concurrency: 1, rounds: 3 }),
];
const [koLines, enLines] = [inLang('ko', analyses), inLang('en', analyses)];
assert.ok(koLines[0].length >= 5, '결과 분석의 문장이 나와야 한다');
assert.deepEqual(enLines.map((lines) => lines.length), koLines.map((lines) => lines.length));
for (const [path, text] of texts(enLines)) assert.ok(!HANGUL.test(text), `analyze ${path}: 영어에 한글이 남았다: ${text}`);
// 영어 문장에 값이 빠져 undefined나 NaN이 들어가지 않는다.
for (const [path, text] of [...texts(enMade), ...texts(enLines)]) {
  assert.ok(!/undefined|NaN/.test(text), `${path}: 값이 빠진 문장: ${text}`);
}

// 흐름 그림의 값은 노드 칸에 써넣는다. 영어 단계 값이 칸을 넘지 않게 길이를 묶어 둔다.
for (const step of inLang('en', () => STEPS)) {
  for (const [name, text] of Object.entries(step.values)) assert.ok(text.length <= 20, `${step.n}.${name}: ${text}`);
}

// 구축 과정: 0단계에서 9단계까지 차례대로이고, 남은 단계에는 명령과 측정값을 적지 않는다.
assert.deepEqual(DEPLOY.steps.map((step) => step.n), [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
for (const step of DEPLOY.steps) {
  assert.ok(step.title && step.text && step.tools.length >= 1 && step.points.length >= 3, `${step.n}단계`);
  assert.ok(['done', 'todo'].includes(step.status));
  if (step.status === 'todo') assert.ok(step.command === '' && step.rows.length === 0 && step.doc === '', `${step.n}단계는 아직 하지 않았다`);
  else assert.ok(step.rows.length >= 2 && step.doc, `${step.n}단계의 확인한 값과 기록`);
}
assert.deepEqual(DEPLOY.steps.filter((step) => step.status === 'todo').map((step) => step.n), [9]);
assert.ok(DEPLOY.findings.length >= 5 && DEPLOY.findings.every((item) => item.title && item.value && item.text && item.doc));

// 영어판 지도는 한국어판과 같은 id를 쓰고(화면 코드가 두 그림을 같은 이름으로 다룬다) 글에 한글이 없다.
const read = (name) => readFileSync(new URL(`./src/${name}`, import.meta.url), 'utf8');
const ids = (svg) => [...svg.matchAll(/ id="([a-z0-9-]+)"/g)].map((match) => match[1]).sort();
const [mapKo, mapEn] = [read('flow-map.svg'), read('flow-map.en.svg')];
assert.deepEqual(ids(mapEn), ids(mapKo));
assert.ok(ids(mapEn).length >= MAP_NODES.length + MAP_EDGES.length);
const labels = (svg) => [...svg.matchAll(/<text[^>]*>(.*?)<\/text>/gs)].map((match) => match[1].replace(/<[^>]+>/g, ''));
assert.ok(labels(mapKo).some((text) => HANGUL.test(text)));
for (const text of labels(mapEn)) assert.ok(!HANGUL.test(text), `flow-map.en.svg: ${text}`);
// BFF와 게이트웨이를 잇는 선의 라벨은 두 그림에 각자의 언어로 있다.
assert.ok(labels(mapKo).includes('Service 직접 호출') && labels(mapEn).includes('Direct Service call'));

console.log('i18n: ok');
