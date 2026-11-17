// Markdown 렌더링 확인. 화면(src/Record.jsx)과 같은 플러그인 구성으로 한국어 문장의 강조가 처리되는지 본다.
//   npm test
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import Markdown from 'react-markdown';
import remarkCjkFriendly from 'remark-cjk-friendly';
import remarkCjkFriendlyGfmStrikethrough from 'remark-cjk-friendly-gfm-strikethrough';
import remarkGfm from 'remark-gfm';

const plugins = [remarkGfm, remarkCjkFriendly, remarkCjkFriendlyGfmStrikethrough];
const render = (text) => renderToStaticMarkup(createElement(Markdown, { remarkPlugins: plugins }, text));
const count = (html, pattern) => (html.match(pattern) || []).length;

// 굵게 표시할 구간이 괄호로 끝나고 바로 조사가 붙는 문장(2026-11-14에 화면에서 `**`가 그대로 보였던 문장)
let html = render('주민등록번호의 **형식(길이, 숫자 여부, 성별 구분자)**과 **유효성 검증 알고리즘(체크섬)**을 모두 확인합니다.');
assert.equal(count(html, /<strong>/g), 2);
assert.equal(count(html, /\*\*/g), 0);

// 따옴표로 끝나는 구간, 기울임, 취소선
html = render('값은 **"A-1024"**입니다. *기울임(참고)*도 확인합니다. ~~취소선(예)~~도 봅니다.');
assert.equal(count(html, /<strong>/g), 1);
assert.equal(count(html, /<em>/g), 1);
assert.equal(count(html, /<del>/g), 1);

// 코드와 수식의 별표는 그대로 둔다
html = render('`**코드 안(그대로)**과` 는 바뀌지 않습니다. 곱셈은 2 * 3 * 4 이고 a**b 는 거듭제곱입니다.');
assert.equal(count(html, /<strong>|<em>/g), 0);
assert.equal(count(html, /\*\*/g), 3);

// remark-gfm: 표와 할 일 목록
html = render('- [x] 완료한 일\n- [ ] 남은 일\n\n| 항목 | 값 |\n|---|---|\n| **합계(원)**은 | 1,000 |');
assert.equal(count(html, /<table>/g), 1);
assert.equal(count(html, /type="checkbox"/g), 2);
assert.equal(count(html, /<strong>/g), 1);

// 원시 HTML은 렌더링하지 않는다
html = render('<img src=x onerror=alert(1)> 텍스트');
assert.equal(count(html, /<img/g), 0);

console.log('markdown: ok');

// 결정 이유 문장(src/format.js). BFF의 x-bff-reason 값마다 문장이 나오는지 본다.
const { explain } = await import('./src/format.js');
const text = (decision, reason) => explain(decision, reason).join(' ');
assert.match(text('decider', { route: 'qwen', route_confidence: 0.85, policy: 0.08, thinking: 0.59, min_confidence: 0.6 }),
  /Decider가 Qwen을 골랐습니다\. 신뢰도는 0\.85로 기준 0\.60 이상입니다\..*확률은 0\.08.*0\.59여서 thinking을 켰습니다/);
assert.match(text('decider', { route: 'qwen', route_confidence: 0.9, policy: 0.95, thinking: 0.2, min_confidence: 0.6 }),
  /확률을 0\.95로 보아 Gemma로 보냈습니다.*thinking을 껐습니다/);
assert.match(text('fallback', { why: 'low_confidence', low: ['route'], route: 'gemma', route_confidence: 0.3, policy: 0.05,
  policy_confidence: 0.9, thinking: 0.54, min_confidence: 0.6 }), /모델 선택의 신뢰도\(0\.30\)가 기준 0\.60보다 낮아.*기본값인 Gemma/);
assert.match(text('fallback', { why: 'decider_unavailable', detail: 'timeout', timeout_s: 2 }), /2초 안에 답하지 않았습니다/);
assert.match(text('rule', { pattern: 'rrn' }), /주민등록번호 형식이 있어 Decider에 묻지 않고 Gemma로/);
assert.match(text('task', { task: 'coding' }), /업무 종류\(코딩\)의 배정표/);
assert.match(text('decider', { route: 'gemma', route_confidence: 0.9, policy: 0.1, thinking: 0.1, min_confidence: 0.6, cached: true }),
  /앞서 내린 결정을 다시 썼습니다/);
assert.deepEqual(explain('task', null), []);
console.log('explain: ok');

// 성능 평가 계산(src/format.js)
const { aggregate, koreanShare, measure, percentile } = await import('./src/format.js');
const ticks = [100, 150, 200, 260].map((ms) => ({ ms, kind: 'content' })).concat([{ ms: 50, kind: 'reasoning' }]);
const one = measure(ticks, 300, { completion_tokens: 9 });
assert.deepEqual([one.firstMs, one.gaps, one.tokens], [100, [50, 50, 60], 9]);
assert.equal(one.tokensPerSecond, 8 / 0.16);  // 첫 토큰 뒤 0.16초 동안 8토큰
assert.equal(measure([], 300, null).tokensPerSecond, null);
assert.equal(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.95), 10);
const total = aggregate(
  [{ ...one, round: 0 }, { ...measure(ticks.map((t) => ({ ...t, ms: t.ms * 2 })), 600, { completion_tokens: 9 }), round: 0 },
   { round: 0, error: '실패', gaps: [] }],
  [{ index: 0, wallMs: 600 }]);
assert.deepEqual([total.sent, total.failed, total.firstMedian, total.firstMax, total.gapMedian], [3, 1, 150, 200, 80]);
assert.equal(total.throughput, 18 / 0.6);  // 0.6초 동안 두 요청이 18토큰
assert.ok(koreanShare('사용자의 질문을 정리하면 요금제 A는 월 9,900원이다') > 0.9);
assert.ok(koreanShare('Plan A: 9,900 KRW per month. 요금제') < 0.2);
console.log('measure: ok');

// 흐름 그림 계산(src/flow.js)
const { buildFlow } = await import('./src/flow.js');
const base = { state: 'streaming', ticks: [], model: null, decision: null, reason: null, timing: null, toolCalls: 0 };
let flow = buildFlow(base);
assert.deepEqual([flow.phase, flow.nodes.bff, flow.nodes.gw, flow.edges['alb-bff']], ['waiting', 'now', undefined, 'on']);
// Decider가 고른 Qwen 요청이 응답 Chunk를 받고 있는 중
flow = buildFlow({ ...base, model: 'qwen38-27b', decision: 'decider', reason: { route: 'qwen' },
  timing: { decide_ms: 152.3, wake_ms: 3660.9, upstream_ms: 219.6, woke: true },
  ticks: [{ ms: 4050, kind: 'content' }, { ms: 4120, kind: 'content' }, { ms: 4190, kind: 'content' }] });
assert.deepEqual([flow.phase, flow.nodes.qwen, flow.nodes.gemma, flow.nodes.decider, flow.nodes.wake], ['streaming', 'now', 'off', 'on', 'on']);
assert.deepEqual([flow.edges['gw-qwen'], flow.edges['gw-gemma'], flow.edges['bff-wake'], flow.edges['user-cf']], ['stream', 'off', 'on', 'stream']);
assert.deepEqual([flow.values.decider, flow.values.wake, flow.values.gw, flow.values.user, flow.values.qwen],
  ['판단 152.3ms', '깨움 3.66초', '첫 응답 219.6ms', '첫 토큰 4.05초', 'Chunk 3개, 70ms']);
// 업무 종류로 정한 Gemma 상담 요청이 끝난 뒤: Decider와 깨우기 API는 쓰지 않았다
flow = buildFlow({ ...base, state: 'done', model: 'gemma-4-31b', decision: 'task', reason: { task: 'support' }, toolCalls: 1,
  timing: { decide_ms: 0.4, wake_ms: 0, upstream_ms: 15.2, woke: false }, ticks: [{ ms: 1600, kind: 'content' }] });
assert.deepEqual([flow.phase, flow.nodes.gemma, flow.nodes.decider, flow.nodes.wake, flow.edges['bff-gw']], ['done', 'on', 'off', 'off', 'on']);
assert.equal(flow.values.bff, '판단 0.4ms, 주문 조회 1회');
// Decider가 답하지 않아 기본값을 쓴 경우
flow = buildFlow({ ...base, state: 'done', model: 'gemma-4-31b', decision: 'fallback',
  reason: { why: 'decider_unavailable', detail: 'timeout' }, timing: { decide_ms: 2001, wake_ms: 0, upstream_ms: 20 } });
assert.deepEqual([flow.nodes.decider, flow.values.decider, flow.values.bff], ['fail', '시간 초과', '기본값 적용']);
// WAF 차단과 토큰 거절
flow = buildFlow({ ...base, state: 'failed', status: 403 });
assert.deepEqual([flow.nodes.user, flow.nodes.cf, flow.nodes.alb, flow.values.cf], ['on', 'fail', undefined, 'WAF가 차단']);
flow = buildFlow({ ...base, state: 'failed', status: 401 });
assert.deepEqual([flow.nodes.alb, flow.nodes.bff, flow.edges['alb-bff']], ['on', 'fail', 'on']);
assert.equal(buildFlow(null), null);
console.log('flow: ok');

// 성능 평가의 결과 분석(src/format.js)
const { analyze } = await import('./src/format.js');
const side = (first, gap, tokensPerSecond, tokensPerChunk, tokens, extra = {}) => ({ sent: 3, failed: 0, firstMedian: first, firstMin: first - 5,
  firstMax: first + 10, gapMedian: gap, tokensPerSecond, tokensPerChunk, throughput: tokensPerSecond, tokens, ...extra });
let lines = analyze({ gemma: side(186, 54, 19.6, 1.0, 21), qwen: side(382, 70, 39.3, 2.8, 31) }, { concurrency: 1, rounds: 3 });
let text2 = lines.join(' ');
assert.match(text2, /첫 토큰은 Gemma가 186ms로 Qwen\(382ms\)보다 196ms 빨랐습니다/);
assert.match(text2, /생성 속도는 Qwen이 초당 39\.3토큰으로 Gemma\(초당 19\.6토큰\)의 2\.0배/);
assert.match(text2, /토큰 하나당 간격으로 바꾸면 Gemma 54ms, Qwen 25ms/);
assert.match(text2, /Qwen은 Chunk 사이의 간격이 더 길지만/);
assert.match(text2, /Gemma는 첫 토큰 충족\(가장 느린 요청 196ms\), 토큰 간격 미충족\(54ms\), Qwen은 첫 토큰 충족\(가장 느린 요청 392ms\), 토큰 간격 충족\(25ms\)/);
assert.match(text2, /답의 길이가 다릅니다\(Gemma 21토큰, Qwen 31토큰\)/);
assert.match(text2, /모델마다 요청 3건으로 잰 값/);
lines = analyze({ gemma: side(300, 60, 15, 1, 100, { throughput: 52 }), qwen: side(350, 80, 30, 3, 100, { throughput: 95 }) }, { concurrency: 4, rounds: 3 });
assert.match(lines.join(' '), /4개씩 동시에 보냈을 때 모델 전체 처리량은 Gemma 초당 52\.0토큰, Qwen 초당 95\.0토큰입니다\. 요청 하나의 생성 속도와 견주면 Gemma 3\.5배, Qwen 3\.2배/);
lines = analyze({ gemma: side(186, 54, 19.6, 1, 21), qwen: { sent: 3, failed: 3 } }, { concurrency: 1, rounds: 3 });
assert.deepEqual(lines, ['Qwen 요청이 모두 실패해 두 모델을 견줄 수 없습니다.']);
console.log('analyze: ok');

// 고친 문구: 기준과 같아 보이는 신뢰도, 세션 문구의 겹침, 추론 중인 요청의 흐름
assert.match(explain('fallback', { why: 'low_confidence', low: ['route'], route: 'gemma', route_confidence: 0.598, policy: 0.05,
  policy_confidence: 0.9, thinking: 0.2, min_confidence: 0.6 }).join(' '), /신뢰도\(0\.598\)가 기준 0\.60보다 낮아/);
const during = explain('rule', { pattern: 'rrn', during_session: true, cached: true }).join(' ');
assert.ok(during.includes('이 규칙을 먼저 적용했습니다') && !during.includes('다시 썼습니다'));
flow = buildFlow({ ...base, model: 'qwen38-27b', decision: 'decider', reason: {}, timing: { decide_ms: 150, wake_ms: 16, upstream_ms: 9 },
  ticks: [{ ms: 300, kind: 'reasoning' }, { ms: 370, kind: 'reasoning' }] });
assert.deepEqual([flow.values.user, flow.values.qwen], ['추론 시작 300ms', '추론 Chunk 2개']);
console.log('fixes: ok');

// 웹 검색 출처: 답변의 [n]을 출처 링크로 바꾼다(src/citations.js).
const { addSearch, host, linkCitations } = await import('./src/citations.js');
const sources = [
  { n: 1, title: '서울 주간 예보', url: 'https://weather.example/seoul', published_at: '2026-11-14' },
  { n: 2, title: '괄호가 있는 주소', url: 'https://ko.example/wiki/서울_(도시)', published_at: null },
];
html = render(linkCitations('이번 주는 맑습니다 [1]. 면적은 605km²입니다[1, 2]. 근거 없는 번호 [7]과 배열 `a[1]`은 그대로 둡니다.\n\n```js\nconst x = list[2];\n```', sources));
assert.equal(count(html, /<a href="https:\/\/weather\.example\/seoul">\[1\]<\/a>/g), 2);
assert.equal(count(html, /<a href="https:\/\/ko\.example\/wiki\/[^"]+">\[2\]<\/a>/g), 1);
assert.ok(html.includes('[7]') && html.includes('<code>a[1]</code>') && html.includes('list[2]'));
// 이미 링크인 [1](주소)와 출처가 없는 답변은 건드리지 않는다
assert.equal(linkCitations('[1](https://x.example) 참고', sources), '[1](https://x.example) 참고');
assert.equal(linkCitations('출처 없음 [1]', []), '출처 없음 [1]');
// 검색을 두 번 해도 같은 번호는 한 번만 담는다
let found = addSearch({}, { query: '서울 날씨', search_ms: 480.5, sources });
found = addSearch(found, { query: '서울 면적', search_ms: 510, sources: [sources[1], { n: 3, title: 'c', url: 'https://c.example/' }] });
assert.deepEqual(found.sources.map((item) => item.n), [1, 2, 3]);
assert.deepEqual(found.searches.map((item) => [item.query, item.count]), [['서울 날씨', 2], ['서울 면적', 2]]);
assert.equal(host('https://www.docs.example/a/b'), 'docs.example');
console.log('citations: ok');
