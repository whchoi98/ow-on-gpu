import { useEffect, useState } from 'react';
import { ChatError } from './stream.js';
import { callJson, explainFailure } from './api.js';
import { ms } from './format.js';
import { locale, localized, tr, useLang } from './i18n.js';

const PARTS = localized(() => [
  {
    key: 'gemma',
    name: 'Gemma 4 31B',
    pen: 'gemma',
    role: tr('상담, 번역, 요약. 민감 정보가 든 요청', 'Support, translation, summarization. Requests with sensitive data'),
  },
  {
    key: 'qwen',
    name: 'Qwen3.8-27B',
    pen: 'qwen',
    role: tr('코딩, 이미지 이해. 평일 19시에 잠들고 8시 30분에 깨어남', 'Coding, image understanding. Sleeps at 19:00 on weekdays, wakes at 08:30'),
  },
  {
    key: 'decider',
    name: 'Decider 12B',
    pen: 'auto',
    role: tr('업무 종류가 없는 요청의 모델 판단', 'Picks the model for requests with no task type'),
  },
]);

// 로그인 토큰의 만료 시각. 서명은 BFF가 확인하고, 여기서는 표시만 한다.
function expiry(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return payload.exp * 1000;
  } catch {
    return null;
  }
}

// 게이트웨이 뒤의 두 모델과 Decider가 지금 응답하는지 본다. 열 때 한 번, 그 뒤로는 버튼을 누를 때 확인한다.
export default function Status({ session, active, onExpired }) {
  useLang();
  // error에는 문구 대신 오류 객체를 두고, 그릴 때 지금 언어의 문구로 바꾼다.
  const [state, setState] = useState({ status: 'idle', data: null, error: null });

  async function check() {
    setState((current) => ({ ...current, status: 'loading', error: null }));
    try {
      const data = await callJson('/v1/status', session.token);
      setState({ status: 'done', data, error: null });
    } catch (error) {
      if (error instanceof ChatError && error.status === 401) {
        onExpired();
        return;
      }
      setState((current) => ({ ...current, status: 'failed', error }));
    }
  }

  useEffect(() => {
    if (active && state.status === 'idle') check();
  }, [active]);

  const expires = expiry(session.token);
  const minutes = expires ? Math.max(0, Math.round((expires - Date.now()) / 60000)) : null;

  return (
    <div className="console__body">
      <section className="panel">
        <header className="panel__head">
          <h2>{tr('상태', 'Status')}</h2>
          <p className="form-note">
            {tr(
              'BFF가 게이트웨이를 거쳐 두 모델과 Decider에 확인 요청을 보낸 결과입니다. 이 확인은 Qwen을 깨우지 않습니다.',
              'Results of the check requests the BFF sent through the gateway to the two models and Decider. This check does not wake Qwen.',
            )}
          </p>
          <button id="status-check" type="button" className="link" onClick={check} disabled={state.status === 'loading'}>
            {state.status === 'loading' ? tr('확인하는 중', 'Checking') : tr('다시 확인', 'Check again')}
          </button>
        </header>

        {state.error && <p className="record__error" role="alert">{explainFailure(state.error)}</p>}

        <ul className="parts">
          {PARTS.map((part) => {
            const item = state.data?.components?.[part.key];
            return (
              <li key={part.key} className={`part ${item ? (item.ok ? 'is-up' : 'is-down') : ''}`}>
                <div className="part__name">
                  <span className={`pen pen--${part.pen}`} aria-hidden="true" />
                  <strong>{part.name}</strong>
                </div>
                <p className="part__state">
                  {!item ? tr('확인 전', 'Not checked') : item.ok ? tr('응답함', 'Responding') : tr('응답 없음', 'No response')}
                </p>
                <dl className="part__facts">
                  <div><dt>{tr('응답 시간', 'Response time')}</dt><dd>{item ? ms(item.ms) : '-'}</dd></div>
                  {part.key !== 'decider' && (
                    <div>
                      <dt>{tr('최대 입력 길이', 'Max input')}</dt>
                      <dd>{item?.max_model_len ? `${item.max_model_len.toLocaleString(locale())} ${tr('토큰', 'tokens')}` : '-'}</dd>
                    </div>
                  )}
                  <div><dt>{tr('상태 코드', 'Status code')}</dt><dd>{item ? item.status ?? item.error ?? '-' : '-'}</dd></div>
                </dl>
                <p className="form-note">{part.role}</p>
                {item && !item.ok && part.key === 'qwen' && (
                  <p className="form-note">
                    {tr(
                      '잠들어 있으면 응답하지 않습니다. 코딩 요청을 보내면 BFF가 먼저 깨웁니다(약 4초).',
                      'It does not respond while asleep. When you send a coding request, the BFF wakes it first (about 4 s).',
                    )}
                  </p>
                )}
              </li>
            );
          })}
        </ul>

        <dl className="readouts">
          <div className="readout"><dt>{tr('로그인한 계정', 'Signed-in account')}</dt><dd>{session.email}</dd></div>
          <div className="readout">
            <dt>{tr('로그인 만료까지', 'Sign-in expires in')}</dt>
            <dd>{minutes == null ? '-' : tr(`${minutes}분`, `${minutes} min`)}</dd>
          </div>
          <div className="readout">
            <dt>{tr('마지막 확인', 'Last checked')}</dt>
            <dd>{state.data ? new Date(state.data.checked_at).toLocaleTimeString(locale()) : '-'}</dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
