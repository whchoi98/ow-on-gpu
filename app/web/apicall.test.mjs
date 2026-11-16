// "API 호출" 보기의 계산 확인. 화면 없이 src/apicall.js의 순수 함수만 본다.
//   node apicall.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import data from './src/apicall-data.js';
import {
  REGIONS, SIDES, STAGES, budgetRows, liveRows, mapFor, mapForLive, measuredRows, railStates, searchRows, sideOf,
  summarizeLive,
} from './src/apicall.js';

// 이 보기가 쓰는 지도(flow-map.svg)의 id. 여기에 없는 이름을 쓰면 오타다.
const NODES = ['user', 'cf', 'alb', 'bff', 'gw', 'decider', 'wake', 'gemma', 'qwen', 'cognito', 'amp', 'search'];
const EDGES = ['user-cf', 'cf-alb', 'alb-bff', 'bff-gw', 'gw-decider', 'gw-gemma', 'gw-qwen', 'bff-wake', 'wake-qwen', 'bff-search'];
// 이 이름들이 실제로 그림에 있다. 그림에서 노드나 선이 빠지면(예: BFF와 게이트웨이 사이의 내부 NLB) 여기서 드러난다.
const svg = readFileSync(new URL('./src/flow-map.svg', import.meta.url), 'utf8');
for (const name of NODES) assert.ok(svg.includes(`id="n-${name}"`), `n-${name}`);
for (const name of EDGES) assert.ok(svg.includes(`id="e-${name}"`), `e-${name}`);
const NODE_STATES = ['on', 'now', 'off', 'fail'];
const EDGE_STATES = ['on', 'off', 'stream'];

// 단계는 여덟 개이고 그림의 카드 위치와 하나씩 짝을 이룬다. 그림에는 웹 검색 경로가 하나 더 있다.
assert.deepEqual(STAGES.map((stage) => stage.n), [1, 2, 3, 4, 5, 6, 7, 8]);
assert.deepEqual(Object.keys(REGIONS), ['1', '2', '3', '4', '5', '6', '7', '8', 'search']);
for (const region of Object.values(REGIONS)) {
  assert.ok(region.left >= 0 && region.left + region.width <= 100);
  assert.ok(region.top >= 0 && region.top + region.height <= 100);
}

// 모든 단계와 모델에서 지도는 아는 id와 상태만 쓰고, 설명과 측정값이 비지 않는다.
for (const [side, webSearch] of Object.keys(SIDES).flatMap((name) => [[name, false], [name, true]])) {
  for (const stage of STAGES) {
    const flow = mapFor(stage.n, side, null, webSearch);
    for (const [name, state] of Object.entries(flow.nodes)) {
      assert.ok(NODES.includes(name), `${stage.n}: ${name}`);
      assert.ok(NODE_STATES.includes(state), `${stage.n}: ${name}=${state}`);
    }
    for (const [name, state] of Object.entries(flow.edges)) {
      assert.ok(EDGES.includes(name), `${stage.n}: ${name}`);
      assert.ok(EDGE_STATES.includes(state), `${stage.n}: ${name}=${state}`);
    }
    for (const name of Object.keys(flow.values)) assert.ok(NODES.includes(name), `${stage.n}: ${name}`);
    assert.ok(Object.values(flow.nodes).includes('now'), `${stage.n}단계에 켜지는 구성 요소가 있어야 한다`);
    assert.ok(stage.here.length >= 2 && stage.lead && stage.note);
    assert.ok(measuredRows(stage.n, side).length >= 1);
  }
}

// 깨우기 API는 Qwen 요청에서만 켜지고, 쓰지 않는 모델은 흐리게 한다.
assert.equal(mapFor(4, 'qwen').nodes.wake, 'now');
assert.equal(mapFor(4, 'gemma').nodes.wake, 'off');
assert.equal(mapFor(5, 'gemma').nodes.qwen, 'off');
assert.equal(mapFor(5, 'qwen').nodes.gemma, 'off');
// 2단계는 요청을 나누는 내부 ALB와 게이트웨이를 표시한다. BFF는 게이트웨이의 Service를 직접 부르므로 그 사이에 NLB가 없다.
assert.deepEqual(['alb', 'bff', 'gw'].map((name) => mapFor(2, 'gemma').nodes[name]), ['now', 'on', 'now']);
assert.equal(mapFor(2, 'gemma').edges['bff-gw'], 'on');
assert.equal(mapFor(1, 'gemma').edges['bff-gw'], undefined);  // 1단계는 BFF까지만 간다
assert.ok(STAGES[1].here.some(([name, text]) => name === 'Service' && text.includes('직접')));
assert.ok(!STAGES[1].here.some(([name]) => name.includes('NLB')));
assert.equal(measuredRows(2, 'gemma')[1][0], '게이트웨이 구간 (agentgateway, EPP)');
// 7단계는 돌아오는 조각을, 8단계는 AMP를 표시한다.
assert.equal(mapFor(7, 'gemma').edges['bff-gw'], 'stream');
assert.equal(mapFor(7, 'gemma').edges['gw-gemma'], 'stream');
assert.equal(mapFor(8, 'qwen').nodes.amp, 'now');

// 웹 검색: 켜면 6단계에서 Web Search가 일하고 그 뒤로는 지나온 곳이 된다. 끄면 4단계부터 쓰지 않는 곳으로 흐리게 한다.
assert.equal(mapFor(6, 'gemma', null, true).nodes.search, 'now');
assert.equal(mapFor(6, 'gemma', null, true).edges['bff-search'], 'on');
assert.equal(mapFor(6, 'gemma', null, true).nodes.bff, 'now');
assert.equal(mapFor(6, 'gemma', null, true).values.search, '481~1,065ms');
assert.equal(mapFor(7, 'qwen', null, true).nodes.search, 'on');
assert.equal(mapFor(5, 'qwen', null, true).nodes.search, undefined);
assert.equal(mapFor(6, 'gemma', null, false).nodes.search, 'off');
assert.equal(mapFor(6, 'gemma').edges['bff-search'], 'off');
assert.equal(mapFor(2, 'gemma', null, false).nodes.search, undefined);
// 웹 검색을 설명하는 단계: 도구를 붙이는 4, 다시 추론하는 5, 실행하는 6, 출처를 보이는 7
for (const n of [4, 5, 6, 7]) {
  assert.ok(STAGES[n - 1].here.some(([name, text]) => /웹 검색|도구|출처/.test(name + text)), `${n}단계에 웹 검색 설명`);
}
assert.ok(STAGES[5].here.some(([name]) => name === 'AgentCore Web Search'));
// 웹 검색에서 잰 값은 6, 7단계에만 있고 내보낸 값 그대로다.
assert.deepEqual([1, 2, 3, 4, 5, 8].map((n) => searchRows(n, 'gemma').length), [0, 0, 0, 0, 0, 0]);
assert.equal(searchRows(6, 'gemma')[2][1], `${data.measured.search.input_tokens.gemma.toLocaleString('ko-KR')}개`);
assert.equal(searchRows(6, 'qwen')[2][0], '입력 토큰 (검색 2회)');
assert.equal(searchRows(7, 'qwen')[0][1], '1,000건에 7달러');

// 측정값은 내보낸 값 그대로 나온다.
assert.equal(measuredRows(5, 'gemma')[0][1], `${data.measured.gemma.prefill.toFixed(1)}ms`);
assert.equal(measuredRows(7, 'qwen')[1][1], `${data.measured.qwen.first_content.toFixed(1)}ms`);
assert.equal(measuredRows(1, 'gemma')[1][1], `${data.measured.gemma.cloudfront.toFixed(1)}ms`);
assert.equal(measuredRows(4, 'gemma')[1][1], '0.03ms');
assert.equal(mapFor(4, 'qwen').values.bff, '판단 0.1ms');

// 단계 띠: 고른 단계는 진행 중, 앞 단계는 지나옴. 요청이 진행 중이면 요청의 단계를 따른다.
assert.deepEqual(Object.values(railStates(3, null)), ['on', 'on', 'now', '', '', '', '', '']);
assert.deepEqual(Object.values(railStates(1, { phase: 'streaming' })), ['on', 'on', 'on', 'on', 'now', 'now', 'now', '']);
assert.deepEqual(Object.values(railStates(2, { phase: 'done' })), ['on', 'now', 'on', 'on', 'on', 'on', 'on', 'on']);

// 실제 요청의 기록을 값으로 정리한다.
const live = {
  phase: 'done',
  side: 'qwen',
  info: {
    status: 200, headersMs: 40, model: 'qwen38-27b', decision: 'task', requestId: 'r-1',
    timing: { decide_ms: 0.2, wake_ms: 14, upstream_ms: 12, woke: false, tools: false },
    cdn: { 'cdn-upstream-fbl': 30, 'cdn-downstream-fbl': 33 },
  },
  ticks: [{ ms: 180, kind: 'reasoning' }, { ms: 250, kind: 'content' }, { ms: 320, kind: 'content' }, { ms: 400, kind: 'content' }],
  result: { totalMs: 1180, finishReason: 'stop', usage: { prompt_tokens: 20, completion_tokens: 41 } },
};
const summary = summarizeLive(live);
assert.equal(sideOf(summary.model), 'qwen');
assert.equal(summary.ttft, 180);
assert.equal(summary.firstKind, 'reasoning');
assert.equal(summary.gap, 70);
assert.equal(summary.bffMs, 14.2);
assert.ok(Math.abs(summary.entryMs - 13.8) < 1e-9);       // 40 - (0.2 + 14 + 12)
assert.equal(summary.tpot, (1180 - 180) / 40);
assert.deepEqual([summary.asked, summary.search, summary.searches, summary.sources], [false, null, [], []]);
assert.equal(summarizeLive(null), null);
assert.equal(summarizeLive({ phase: 'sending', info: null }), null);

// 브라우저가 알 수 없는 단계(토큰화)는 값이 없고, 나머지는 그 요청의 값이 나온다.
assert.deepEqual(liveRows(3, summary), []);
assert.deepEqual(liveRows(4, summary).map((row) => row[0]), ['결정 방식', 'BFF의 판단', '깨우기 확인']);
assert.equal(liveRows(7, summary)[0][1], '1.18초');
assert.deepEqual(liveRows(5, null), []);

// 시간 띠: 측정값 한 줄, 요청을 보냈으면 두 줄. 가장 긴 줄이 100%다.
assert.equal(budgetRows('gemma', null).length, 1);
const rows = budgetRows('qwen', summary);
assert.deepEqual(rows.map((row) => row.key), ['measured', 'live']);
const widths = rows.map((row) => row.parts.reduce((sum, part) => sum + part.percent, 0));
assert.ok(Math.abs(Math.max(...widths) - 100) < 1e-9);
assert.ok(Math.abs(rows[1].parts.reduce((sum, part) => sum + part.value, 0) - summary.ttft) < 1e-9);

// 웹 검색을 켠 요청: 도구 호출 알림에서 검색 횟수, 결과 수, 검색 시간, 출처를 모은다. 같은 번호의 출처는 한 번만 센다.
const searched = summarizeLive({
  ...live,
  asked: true,
  info: { ...live.info, search: 'on' },
  notes: [
    { event: 'tool_call', name: 'web_search', query: 'kubernetes release', search_ms: 536.2,
      sources: [{ n: 1, title: 'A', url: 'https://example.com/a' }, { n: 2, title: 'B', url: 'https://example.com/b' }] },
    { event: 'tool_call', name: 'web_search', query: '쿠버네티스 릴리스', search_ms: 612,
      sources: [{ n: 2, title: 'B', url: 'https://example.com/b' }, { n: 3, title: 'C', url: 'https://example.com/c' }] },
    { event: 'tool_call', name: 'web_search', query: '', error: 'sensitive_query', sources: [] },
  ],
});
assert.equal(searched.searches.length, 3);
assert.deepEqual(searched.sources.map((source) => source.n), [1, 2, 3]);
assert.deepEqual(liveRows(6, searched).slice(-4), [
  ['웹 검색', '3회'], ['검색 결과', '4건'], ['검색 시간', '536.2ms, 612.0ms'], ['실패한 검색', '1회'],
]);
assert.deepEqual(liveRows(4, searched).at(-1), ['웹 검색 도구', '모델 요청에 붙임']);
assert.deepEqual(liveRows(7, searched).at(-1), ['출처', '3개']);
assert.equal(mapFor(6, 'qwen', searched, true).values.search, '검색 536.2ms');
assert.equal(budgetRows('qwen', searched)[1].parts[2].name, '게이트웨이, vLLM, 웹 검색');
// 민감 정보 요청에는 도구를 붙이지 않는다. 모델이 검색을 부르지 않은 요청도 구분한다.
const refused = summarizeLive({ ...live, asked: true, info: { ...live.info, search: 'sensitive' }, notes: [] });
assert.deepEqual(liveRows(4, refused).at(-1), ['웹 검색 도구', '민감 정보 요청이라 붙이지 않음']);
// 모델을 정하지 못해 기본값으로 보낸 요청은 민감 정보 요청과 다른 말로 알린다.
const undecided = summarizeLive({ ...live, asked: true, info: { ...live.info, search: 'fallback' }, notes: [] });
assert.deepEqual(liveRows(4, undecided).at(-1), ['웹 검색 도구', '모델을 정하지 못해 붙이지 않음']);
assert.deepEqual(liveRows(6, summarizeLive({ ...live, asked: true, info: { ...live.info, search: 'on' } })).at(-1), ['웹 검색', '모델이 부르지 않음']);
// 진행 중의 지도: 알림이 오면 Web Search를 지나온 곳으로, 도구가 붙지 않았으면 흐리게 한다.
const running = { ...live, phase: 'engine', asked: true, info: { ...live.info, search: 'on' }, ticks: [] };
assert.equal(mapForLive(running).nodes.search, undefined);
assert.equal(mapForLive({ ...running, notes: [{ event: 'tool_call', name: 'web_search', query: 'q', search_ms: 500, sources: [] }] }).nodes.search, 'on');
assert.equal(mapForLive({ ...running, info: { ...live.info, search: 'sensitive' } }).nodes.search, 'off');
assert.equal(mapForLive({ ...live, phase: 'streaming' }).nodes.search, 'off');

// 진행 중과 실패한 요청의 지도
assert.equal(mapForLive({ phase: 'sending', side: 'gemma', info: null, ticks: [] }).nodes.bff, 'now');
assert.equal(mapForLive({ ...live, phase: 'streaming' }).edges['gw-qwen'], 'stream');
assert.equal(mapForLive({ phase: 'failed', side: 'gemma', info: null, ticks: [], status: 403 }).nodes.cf, 'fail');
assert.equal(mapForLive({ phase: 'failed', side: 'gemma', info: null, ticks: [], status: 503 }).nodes.gw, 'fail');
// 실패한 요청은 막힌 곳 앞의 선까지만 켠다. 게이트웨이가 막았으면 BFF에서 게이트웨이로 가는 선까지 지나온 것이다.
{
  const at = (status) => mapForLive({ phase: 'failed', side: 'gemma', info: null, ticks: [], status });
  assert.deepEqual([at(503).nodes.bff, at(503).edges['alb-bff'], at(503).edges['bff-gw']], ['on', 'on', 'on']);
  assert.deepEqual([at(401).nodes.bff, at(401).edges['alb-bff'], at(401).edges['bff-gw']], ['fail', 'on', undefined]);
  assert.deepEqual([at(403).nodes.user, at(403).edges['user-cf'], at(403).edges['cf-alb']], ['on', 'on', undefined]);
  assert.equal(mapForLive({ phase: 'sending', side: 'gemma', info: null, ticks: [] }).edges['bff-gw'], undefined);
  assert.equal(mapForLive({ ...live, phase: 'streaming' }).edges['bff-gw'], 'stream');
}

console.log('apicall: ok');

// 배포 뒤 BFF가 잰 검색 시간이 6단계의 값에 들어 있다.
{
  const { searchRows } = await import('./src/apicall.js');
  const row = searchRows(6, 'gemma').find(([label]) => label.startsWith('BFF에서 잰 검색 시간'));
  assert.ok(row && /485~662ms/.test(row[1]), 'BFF 측정값');
}
