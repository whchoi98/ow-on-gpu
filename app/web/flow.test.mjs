// 요청 경로 그림의 상태 계산 확인. 그림(src/flow-map.svg)에 있는 id와 코드가 쓰는 이름이 어긋나지 않는지도 본다.
//   node flow.test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { buildFlow } from './src/flow.js';
import { MAP_EDGES, MAP_NODES, STEPS, stepFlow } from './src/flow-steps.js';

const svg = readFileSync(new URL('./src/flow-map.svg', import.meta.url), 'utf8');
const ids = (prefix) => [...svg.matchAll(new RegExp(`id="${prefix}-([a-z0-9-]+)"`, 'g'))].map((match) => match[1]).sort();

// 그림의 노드, 선과 코드의 목록이 같다. 틀(n-gpu)은 노드 목록에 넣지 않는다.
assert.deepEqual(ids('n'), [...MAP_NODES, 'gpu'].sort());
assert.deepEqual(ids('e'), [...MAP_EDGES].sort());
// 값 자리가 없는 것은 Karpenter 막대와 틀뿐이다.
assert.deepEqual(ids('v'), MAP_NODES.filter((name) => name !== 'karpenter').sort());

// 다른 화면과 약속한 id는 이름이 바뀌면 안 된다.
for (const name of ['user', 'cf', 'alb', 'bff', 'gw', 'decider', 'wake', 'gemma', 'qwen',
  'hf', 'sync', 's3', 'registry', 'karpenter', 'identity', 'amp', 'search']) {
  assert.ok(svg.includes(`id="n-${name}"`), `n-${name}`);
}
for (const name of ['user-cf', 'cf-alb', 'alb-bff', 'bff-gw', 'gw-decider', 'gw-gemma', 'gw-qwen', 'bff-wake',
  'wake-qwen', 'hf-sync', 'sync-s3', 'bff-search']) {
  assert.ok(svg.includes(`id="e-${name}"`), `e-${name}`);
}
// BFF는 게이트웨이의 Service를 직접 부른다(2026-11-15). 그림에 내부 NLB 노드와 그 앞뒤의 선이 없고,
// BFF와 게이트웨이를 잇는 선 하나에 라벨이 붙어 있다.
for (const id of ['n-nlb', 'v-nlb', 'e-bff-nlb', 'e-nlb-gw']) assert.ok(!svg.includes(`id="${id}"`), id);
assert.ok(!MAP_NODES.includes('nlb') && !MAP_EDGES.some((name) => name.includes('nlb')));
assert.match(svg.match(/<g id="e-bff-gw"[\s\S]*?<\/g>/)[0], /<text[^>]*>Service 직접 호출<\/text>/);

// 단계 여섯 개: 번호가 차례대로이고, 그림에 같은 번호의 배지가 있고, 켤 요소가 모두 그림에 있다.
assert.deepEqual(STEPS.map((step) => step.n), [0, 1, 2, 3, 4, 5]);
for (const step of STEPS) {
  assert.ok(svg.includes(`data-step="${step.n}"`), `배지 ${step.n}`);
  for (const name of step.nodes) assert.ok(name === 'gpu' || MAP_NODES.includes(name), `${step.n}: ${name}`);
  for (const name of step.edges) assert.ok(MAP_EDGES.includes(name), `${step.n}: ${name}`);
  for (const name of Object.keys(step.values)) assert.ok(svg.includes(`id="v-${name}"`), `${step.n}: v-${name}`);
  assert.ok(step.rows.length >= 2 && step.text && step.note);
}

// 단계의 그림 상태: 그 단계의 것만 켜고 나머지는 흐리게 한다.
let flow = stepFlow(0);
assert.equal(flow.nodes.hf, 'on');
assert.equal(flow.nodes.user, 'off');
assert.equal(flow.nodes.gpu, 'off');
assert.equal(flow.edges['hf-sync'], 'feed');
assert.equal(flow.edges['user-cf'], 'off');
flow = stepFlow(1);
assert.equal(flow.nodes.gpu, 'on');
assert.equal(flow.nodes.gemma, 'off');
flow = stepFlow(3);
assert.equal(flow.nodes.gemma, 'on');
assert.equal(flow.nodes.gpu, undefined);  // 안의 노드가 켜져 있으면 틀은 그대로 둔다
assert.equal(flow.values.gemma, '가중치 19.2초');
assert.equal(stepFlow(9), null);
// 5번: 웹 검색은 요청이 켰을 때만 쓰므로 약하게 켠다. 다른 단계에서는 꺼 둔다.
flow = stepFlow(5);
assert.equal(flow.nodes.search, 'opt');
assert.equal(flow.edges['bff-search'], 'opt');
assert.equal(flow.nodes.bff, 'on');
assert.equal(flow.values.search, '선택, 481~1,065ms');
assert.equal(stepFlow(4).nodes.search, 'off');
// 그림의 BFF와 Web Search 사이는 왕복이라 화살촉이 둘이다.
assert.equal((svg.match(/<g id="e-bff-search"[\s\S]*?<\/g>/)[0].match(/fedge__head/g) || []).length, 2);

// 요청 하나의 경로: 공급 쪽은 흐리게, 웹 검색은 기록이 있을 때만 켠다.
const record = {
  state: 'done', model: 'gemma-4-31b', decision: 'task', reason: {}, timing: { decide_ms: 0.2, upstream_ms: 80 },
  ticks: [{ ms: 100, kind: 'content' }, { ms: 150, kind: 'content' }], toolCalls: 0,
};
flow = buildFlow(record);
assert.equal(flow.phase, 'done');
assert.equal(flow.nodes.gemma, 'on');
assert.equal(flow.nodes.qwen, 'off');
assert.equal(flow.nodes.s3, 'off');
assert.equal(flow.edges['s3-gemma'], 'off');
assert.equal(flow.nodes.search, 'off');
assert.equal(flow.edges['bff-search'], 'off');
assert.equal(flow.nodes.amp, undefined);

flow = buildFlow({ ...record, searches: [{ query: '가', searchMs: 412.3, count: 5 }, { query: '나', searchMs: 388, count: 4 }] });
assert.equal(flow.nodes.search, 'on');
assert.equal(flow.edges['bff-search'], 'on');
// 횟수는 검색 노드에 적고 BFF 칸은 그대로 둔다(BFF 칸에 더하면 칸을 넘친다).
assert.equal(flow.values.search, '2회, 결과 4건, 388ms');
assert.equal(flow.values.bff, '판단 0.2ms');

flow = buildFlow({ ...record, searches: [{ query: '가', error: 'timeout' }] });
assert.equal(flow.nodes.search, 'fail');
assert.equal(flow.values.search, '검색 실패');

// 응답 헤더를 기다리는 중과 실패한 요청에서도 공급 쪽은 흐리다.
flow = buildFlow({ state: 'streaming', model: null, ticks: [] });
assert.equal(flow.phase, 'waiting');
assert.equal(flow.nodes.registry, 'off');
flow = buildFlow({ state: 'failed', model: null, status: 401, ticks: [] });
assert.equal(flow.nodes.bff, 'fail');
assert.equal(flow.nodes.hf, 'off');

// 요청 경로의 선은 그림에 있는 선만 쓴다. 끝난 요청은 BFF에서 게이트웨이로 가는 선까지 켠다.
flow = buildFlow(record);
for (const name of Object.keys(flow.edges)) assert.ok(MAP_EDGES.includes(name), name);
for (const name of Object.keys(flow.nodes)) assert.ok(MAP_NODES.includes(name), name);
assert.deepEqual(['user-cf', 'cf-alb', 'alb-bff', 'bff-gw'].map((name) => flow.edges[name]), ['on', 'on', 'on', 'on']);
// 실패한 요청은 막힌 곳 앞의 선까지만 켠다. BFF가 막으면 BFF와 게이트웨이 사이는 켜지 않고, 게이트웨이가 막으면 켠다.
flow = buildFlow({ state: 'failed', model: null, status: 401, ticks: [] });
assert.deepEqual([flow.edges['alb-bff'], flow.edges['bff-gw'], flow.nodes.gw], ['on', undefined, undefined]);
flow = buildFlow({ state: 'failed', model: null, status: 503, ticks: [] });
assert.deepEqual([flow.nodes.bff, flow.edges['bff-gw'], flow.nodes.gw, flow.values.gw], ['on', 'on', 'fail', '응답 503']);
flow = buildFlow({ state: 'failed', model: null, status: 403, ticks: [] });
assert.deepEqual([flow.nodes.cf, flow.edges['user-cf'], flow.edges['cf-alb'], flow.edges['bff-gw']], ['fail', 'on', undefined, undefined]);
// 5번(추론 요청)은 BFF에서 게이트웨이로 바로 가는 선을 켠다.
assert.equal(stepFlow(5).edges['bff-gw'], 'feed');
assert.equal(stepFlow(5).nodes.gw, 'on');
assert.equal(buildFlow(null), null);

console.log('flow: ok');
