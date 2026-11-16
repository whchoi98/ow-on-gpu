// BFF의 JSON 경로를 부른다. 스트리밍 대화는 stream.js가 맡는다.
import { ChatError } from './stream.js';
import { getLang, tr } from './i18n.js';

export async function callJson(path, token, { method = 'GET', body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      // x-lang은 BFF가 만드는 오류 문구의 언어를 정한다.
      headers: { Authorization: `Bearer ${token}`, 'x-lang': getLang(), ...(body ? { 'Content-Type': 'application/json' } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ChatError(0, tr('응답을 받지 못했습니다. 네트워크 연결을 확인해 주세요.', 'No response received. Check your network connection.'));
  }
  const text = await response.text();
  let data = null;
  try {
    data = JSON.parse(text);
  } catch {
    // WAF나 CloudFront의 오류 본문은 JSON이 아니다.
  }
  if (!response.ok) throw new ChatError(response.status, data?.error?.message || '');
  return data;
}

export function explainFailure(error) {
  if (!(error instanceof ChatError)) return tr('응답을 처리하지 못했습니다.', 'Could not process the response.');
  if (error.status === 403) {
    return tr(
      '요청이 많아 이 네트워크가 잠시 차단되었습니다. 5분쯤 뒤에 다시 시도해 주세요.',
      'Too many requests, so this network is blocked for a while. Try again in about 5 minutes.',
    );
  }
  if (error.status === 0) return error.message;
  const responded = tr(`서버가 ${error.status}로 응답했습니다.`, `The server responded with ${error.status}.`);
  return error.message ? `${responded} ${error.message}` : responded;
}
