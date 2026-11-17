// /v1/chat/completions를 스트리밍으로 부르고, Chunk가 도착할 때마다 도착 시각과 함께 알려 준다.
import { getLang, tr } from './i18n.js';

// 게이트웨이 경로의 요청 제한 시간이 300초다(k8s/gemma/routes.yaml). 2026-11-14에 잰 생성 속도로
// Gemma는 4,096 토큰에 약 3분, Qwen은 그보다 짧게 걸려 이 안에 끝난다. 더 올리려면 그 제한 시간도 함께 올린다.
export const MAX_TOKENS = 4096;

export class ChatError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// BFF가 모델을 정한 근거. JSON이 아니면 근거 없이 표시한다.
function parseReason(value) {
  try {
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

// 응답을 받지 못했을 때의 문구. 기록에는 오류를 두고 그릴 때 이 함수로 문구를 골라야 언어를 바꿔도 따라온다.
export const noResponse = () =>
  tr('응답을 받지 못했습니다. 네트워크 연결을 확인하고 다시 보내 주세요.', 'No response received. Check your network connection and send again.');

// evalModel(gemma 또는 qwen)을 주면 성능 평가 요청이 된다. BFF가 그 모델로 보내고 thinking과 도구를 끈다.
function parseServerTiming(value) {
  if (!value) return null;
  const result = {};
  for (const part of value.split(',')) {
    const [name, detail] = part.trim().split(';');
    if (detail?.startsWith('dur=')) result[name] = Number(detail.slice(4));
  }
  return result;
}

export async function streamChat({ token, task, prompt, messages, sessionId, evalModel, webSearch = false, maxTokens = MAX_TOKENS, onHeaders = () => {}, onChunk = () => {}, onNote = () => {} }) {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    // 기록 하나가 대화 하나다. BFF는 세션마다 모델 결정을 한 번 내리므로 기록마다 새 세션을 쓴다.
    // 대화 보기는 같은 세션 ID를 계속 써서 세션의 결정이 다시 쓰이는 것을 보여 준다.
    'x-session-id': sessionId ?? crypto.randomUUID(),
  };
  // thinking이 켜진 요청에서 추론 과정을 한국어로 쓰게 한다(Qwen은 따르고 Gemma는 따르지 않는다).
  // 한국어 화면에서만 보낸다. BFF는 이 값이 ko일 때만 지시를 붙이므로 영어 화면의 추론은 모델이 쓰는 대로 온다.
  if (getLang() === 'ko') headers['x-thinking-language'] = 'ko';
  // BFF가 만드는 문구(오류 본문, 주문 조회 데이터, 도구 설명, 웹 검색 지시문)의 언어. en이면 영어, 그 밖에는 한국어다.
  headers['x-lang'] = getLang();
  if (task) headers['x-task'] = task;
  if (evalModel) headers['x-eval-model'] = evalModel;
  // 웹 검색을 켜면 BFF가 모델에 web_search 도구를 붙인다. 검색은 모델이 필요하다고 판단할 때만 일어난다.
  if (webSearch) headers['x-web-search'] = 'on';

  const started = performance.now();
  let response;
  try {
    response = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        messages: messages ?? [{ role: 'user', content: prompt }],
        stream: true,
        max_tokens: maxTokens,
        // 마지막 Chunk에 토큰 수(usage)가 온다.
        stream_options: { include_usage: true },
      }),
    });
  } catch {
    throw new ChatError(0, noResponse());
  }

  onHeaders({
    status: response.status,
    headersMs: performance.now() - started,
    model: response.headers.get('x-bff-model'),
    decision: response.headers.get('x-bff-decision'),
    sensitive: response.headers.get('x-bff-sensitive') === 'true',
    // on, off, sensitive(민감 정보라 붙이지 않음), disabled(설정되지 않음)
    search: response.headers.get('x-bff-search'),
    reason: parseReason(response.headers.get('x-bff-reason')),
    // BFF 안에서 구간마다 걸린 시간과, CloudFront가 붙인 Server-Timing(설정되어 있을 때만 온다)
    timing: parseReason(response.headers.get('x-bff-timing')),
    cdn: parseServerTiming(response.headers.get('server-timing')),
    requestId: response.headers.get('x-request-id'),
  });

  if (!response.ok) {
    const body = await response.text();
    let message = '';
    try {
      message = JSON.parse(body)?.error?.message || '';
    } catch {
      // JSON이 아닌 오류 본문(WAF, CloudFront)은 아래에서 상태 코드로 설명한다.
    }
    throw new ChatError(response.status, message);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finishReason = null;
  let usage = null;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    const ms = performance.now() - started;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop();
    for (const line of lines) {
      // BFF가 SSE 주석 줄로 보내는 알림(주문 조회와 웹 검색 도구 호출. 웹 검색은 검색어와 출처 목록이 함께 온다)
      if (line.startsWith(': bff ')) {
        try {
          onNote(JSON.parse(line.slice(6)));
        } catch {
          // 알림은 없어도 되는 정보다.
        }
        continue;
      }
      if (!line.startsWith('data: ') || line === 'data: [DONE]') continue;
      let choice;
      try {
        const event = JSON.parse(line.slice(6));
        usage = event.usage ?? usage;
        choice = event.choices?.[0];
      } catch {
        continue;
      }
      if (choice?.finish_reason) finishReason = choice.finish_reason;
      const delta = choice?.delta;
      if (!delta) continue;
      const reasoning = delta.reasoning_content ?? delta.reasoning;
      if (reasoning) onChunk({ ms, kind: 'reasoning', text: reasoning });
      if (delta.content) onChunk({ ms, kind: 'content', text: delta.content });
    }
  }
  return { totalMs: performance.now() - started, finishReason, usage };
}
