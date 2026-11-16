// 기록 하나의 상태를 흐름 그림(flow-map.svg)의 노드, 선, 값으로 바꾼다. 화면과 무관한 순수 함수다.
//
// 노드 상태: on(지나옴), now(지금 처리 중), off(이 요청이 쓰지 않음), fail(여기서 막힘)
// 선 상태:   on(지나옴), stream(응답 조각이 돌아오는 중), off(쓰지 않음)
//
// 그림에는 요청 경로 말고도 모델과 이미지를 대는 쪽(Hugging Face, 모델 적재 Job, 모델 버킷, Image registry,
// Karpenter, Pod Identity, compile 캐시)이 있다. 요청 하나를 표시할 때는 그쪽을 흐리게 둔다. 그쪽의 단계별 표시는
// flow-steps.js가 맡는다.
//
// 응답 헤더가 오기 전에는 브라우저가 알 수 있는 것이 없어서 BFF까지만 표시한다. 헤더가 오면 BFF가 알려 준
// 값(x-bff-decision, x-bff-reason, x-bff-timing)으로 실제로 거친 경로와 구간 시간을 표시한다.
import { MODELS, median } from './format.js';
import { tr } from './i18n.js';

// 요청 경로의 노드와, 그 사이의 선. MAIN_EDGES[i]는 MAIN[i]에서 MAIN[i + 1]로 가는 선이다.
const MAIN = ['user', 'cf', 'alb', 'bff', 'gw'];
const MAIN_EDGES = ['user-cf', 'cf-alb', 'alb-bff', 'bff-gw'];
// 요청이 지나가지 않는 쪽. 지표 수집(amp)은 요청과 나란히 일어나므로 흐리게 하지 않는다.
const SUPPLY = ['hf', 'sync', 's3', 'registry', 'karpenter', 'identity', 'cache'];
const SUPPLY_EDGES = ['hf-sync', 'sync-s3', 'karpenter-gpu', 'registry-gpu', 's3-gemma', 's3-cache', 's3-qwen',
  'cache-gemma', 'cache-qwen', 'identity-s3'];
// 값은 그림의 노드 칸에 써넣으므로 영어도 칸의 폭을 넘지 않게 짧게 쓴다.
const duration = (value) => (value >= 1000 ? `${(value / 1000).toFixed(2)}${tr('초', 's')}` : `${Math.round(value * 10) / 10}ms`);

// 웹 검색: BFF가 모델의 web_search 호출을 받아 AgentCore Web Search를 부른 기록(record.searches)이 있으면 켠다.
// 항목은 {query, searchMs, count, error}다.
function markSearch(record, nodes, edges, values) {
  const searches = record.searches ?? [];
  if (!searches.length) {
    nodes.search = 'off';
    edges['bff-search'] = 'off';
    return;
  }
  const last = searches[searches.length - 1];
  nodes.search = last.error ? 'fail' : 'on';
  edges['bff-search'] = 'on';
  // 횟수와 마지막 검색의 결과는 검색 노드에 적는다. BFF 칸에 함께 적으면 칸을 넘친다.
  const times = searches.length > 1 ? tr(`${searches.length}회, `, `${searches.length}x, `) : '';
  const took = last.searchMs != null ? `, ${duration(last.searchMs)}` : '';
  values.search = last.error ? `${times}${tr('검색 실패', 'Search failed')}`
    : `${times}${tr(`결과 ${last.count ?? 0}건`, `${last.count ?? 0} results`)}${took}`;
}

export function buildFlow(record) {
  if (!record) return null;
  const nodes = {};
  const edges = {};
  const values = {};
  const mark = (names, state, target = nodes) => names.forEach((name) => { target[name] = state; });
  mark(SUPPLY, 'off');
  mark(SUPPLY_EDGES, 'off', edges);

  // 요청이 실패한 경우: 막은 곳까지만 지나온 것으로 표시한다.
  if (record.state === 'failed' && !record.model) {
    const status = record.status ?? 0;
    const at = status === 403 ? 'cf' : status === 401 || status === 400 || status === 422 ? 'bff' : status === 0 ? 'cf' : 'gw';
    const reached = MAIN.slice(0, MAIN.indexOf(at));
    mark(reached, 'on');
    mark(MAIN_EDGES.slice(0, reached.length), 'on', edges);
    nodes[at] = 'fail';
    values[at] = status === 403 ? tr('WAF가 차단', 'Blocked by WAF')
      : status === 401 ? tr('토큰 거절', 'Token rejected')
        : status === 0 ? tr('연결 실패', 'Connection failed') : tr(`응답 ${status}`, `Status ${status}`);
    return { nodes, edges, values, phase: 'failed' };
  }

  // 응답 헤더를 기다리는 중: BFF 뒤에서 무슨 일이 있는지는 아직 모른다.
  if (!record.model) {
    mark(['user', 'cf', 'alb'], 'on');
    mark(['user-cf', 'cf-alb', 'alb-bff'], 'on', edges);
    nodes.bff = 'now';
    values.bff = tr('처리 중', 'Processing');
    return { nodes, edges, values, phase: 'waiting' };
  }

  const live = record.state === 'streaming';
  const side = MODELS[record.model]?.pen ?? 'gemma';
  const other = side === 'gemma' ? 'qwen' : 'gemma';
  const reason = record.reason ?? {};
  const timing = record.timing ?? {};
  const asked = record.decision === 'decider' || (record.decision === 'fallback' && !reason.cached);
  const answered = record.decision === 'decider' || reason.why === 'low_confidence';

  mark(MAIN, 'on');
  mark(MAIN_EDGES, live ? 'stream' : 'on', edges);
  nodes[side] = record.state === 'failed' ? 'fail' : live ? 'now' : 'on';
  nodes[other] = 'off';
  edges[`gw-${side}`] = live ? 'stream' : 'on';
  edges[`gw-${other}`] = 'off';

  // Decider: 물었으면 표시하고, 답을 받지 못했으면 막힌 것으로 표시한다.
  if (asked && !reason.cached) {
    nodes.decider = answered ? 'on' : 'fail';
    edges['gw-decider'] = 'on';
    values.decider = answered ? tr(`판단 ${duration(timing.decide_ms ?? 0)}`, `Decision ${duration(timing.decide_ms ?? 0)}`)
      : reason.detail === 'timeout' ? tr('시간 초과', 'Timed out') : tr('응답 없음', 'No response');
    values.bff = record.decision === 'fallback' ? tr('기본값 적용', 'Default applied') : tr('Decider 판단 채택', 'Decider used');
  } else {
    nodes.decider = 'off';
    edges['gw-decider'] = 'off';
    if (timing.decide_ms != null) values.bff = tr(`판단 ${duration(timing.decide_ms)}`, `Decision ${duration(timing.decide_ms)}`);
  }
  if (record.toolCalls) {
    values.bff = `${values.bff ?? ''}${values.bff ? ', ' : ''}${tr(`주문 조회 ${record.toolCalls}회`, `lookup x${record.toolCalls}`)}`;
  }
  markSearch(record, nodes, edges, values);

  // 깨우기 API는 Qwen으로 가는 요청마다 부른다.
  if (side === 'qwen') {
    nodes.wake = 'on';
    edges['bff-wake'] = 'on';
    edges['wake-qwen'] = 'on';
    if (timing.wake_ms != null) {
      values.wake = `${timing.woke ? tr('깨움', 'Woke') : tr('확인', 'Checked')} ${duration(timing.wake_ms)}`;
    }
  } else {
    nodes.wake = 'off';
    edges['bff-wake'] = 'off';
    edges['wake-qwen'] = 'off';
  }

  if (timing.upstream_ms != null) values.gw = `${tr('첫 응답', 'First byte')} ${duration(timing.upstream_ms)}`;
  if (record.cdn?.['cdn-upstream-fbl'] != null) values.cf = `${tr('오리진', 'Origin')} ${duration(record.cdn['cdn-upstream-fbl'])}`;

  const content = record.ticks.filter((tick) => tick.kind === 'content').map((tick) => tick.ms);
  const gap = median(content.slice(1).map((value, index) => value - content[index]));
  const thinking = record.ticks.filter((tick) => tick.kind === 'reasoning');
  if (thinking.length && !content.length) values.user = `${tr('추론 시작', 'Reasoning at')} ${duration(thinking[0].ms)}`;
  if (thinking.length && !content.length && live) {
    values[side] = tr(`추론 조각 ${thinking.length}개`, `${thinking.length} reasoning chunks`);
  }
  if (content.length) {
    values.user = `${thinking.length ? tr('답변 시작', 'Answer at') : tr('첫 토큰', 'First token')} ${duration(content[0])}`;
    const chunks = tr(`조각 ${content.length}개`, `${content.length} chunks`);
    values[side] = gap == null ? chunks : `${chunks}, ${Math.round(gap)}ms`;
  } else if (!thinking.length) {
    values[side] = live ? tr('첫 토큰 대기', 'Awaiting first token') : '';
  }
  if (record.state === 'failed') values[side] = tr('응답 중단', 'Response cut off');
  return { nodes, edges, values, phase: live ? 'streaming' : record.state === 'failed' ? 'failed' : 'done' };
}
