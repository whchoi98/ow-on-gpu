import { useState } from 'react';
import { ChatError } from './stream.js';
import { callJson, explainFailure } from './api.js';
import { DECISIONS, EXAMPLE_GROUPS, MODELS, TASKS, explain, ms } from './format.js';
import { tr, useLang } from './i18n.js';

// 업무 종류가 자동인 예시와 민감 정보 형식(주민등록번호, 카드번호)이 든 예시를 한 줄씩 넣는다.
// 예시의 이름은 언어마다 달라서 내용의 형식으로 고른다. 부를 때마다 지금 언어의 예시로 만든다.
const SENSITIVE = /\d{6}-\d{7}|(?:\d{4} ){3}\d{4}/;
const sample = () =>
  EXAMPLE_GROUPS.flatMap((group) => group.items)
    .filter((item) => item.task === '' || SENSITIVE.test(item.prompt))
    .map((item) => item.prompt.replace(/\n+/g, ' '))
    .join('\n');

// 모델을 부르지 않고 BFF의 결정만 확인한다. 한 줄이 요청 하나다.
export default function Route({ session, onExpired }) {
  useLang();
  // 고치기 전에는 예시를 지금 언어로 보여 주고, 한 번 고친 뒤에는 고친 글을 그대로 둔다.
  const [edited, setEdited] = useState(null);
  const text = edited ?? sample();
  const [task, setTask] = useState('');
  const [rows, setRows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);  // 실패한 요청의 오류. 그릴 때 지금 언어의 문구로 바꾼다.

  async function run(event) {
    event.preventDefault();
    const lines = text.split('\n').map((line) => line.trim()).filter(Boolean).slice(0, 30);
    if (!lines.length || busy) return;
    setBusy(true);
    setNotice(null);
    setRows([]);
    try {
      for (const line of lines) {
        const result = await callJson('/v1/route', session.token, {
          method: 'POST',
          headers: task ? { 'x-task': task } : {},
          body: { messages: [{ role: 'user', content: line }] },
        });
        setRows((current) => [...current, { line, ...result }]);
      }
    } catch (error) {
      if (error instanceof ChatError && error.status === 401) {
        onExpired();
        return;
      }
      setNotice(error);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="console__body">
      <form className="composer" onSubmit={run} aria-labelledby="route-title">
        <h2 id="route-title">{tr('경로 판단', 'Routing')}</h2>
        <p className="form-note composer__intro">
          {tr(
            '모델에 보내지 않고 BFF가 어느 모델로 보낼지만 확인합니다. 한 줄이 요청 하나이고, 업무 종류를 자동으로 두면 규칙에 걸리지 않은 줄은 Decider에 묻습니다.',
            'Checks only which model the BFF would send each request to, without calling the model. Each line is one request. With the task type set to Auto, the BFF asks Decider about lines that match no rule.',
          )}
        </p>
        <label className="field">
          <span>{tr('요청 (한 줄에 하나, 30줄까지)', 'Requests (one per line, up to 30 lines)')}</span>
          <textarea id="route-text" rows={8} value={text} onChange={(event) => setEdited(event.target.value)} />
        </label>
        <div className="examples composer__side">
          <label className="field">
            <span>{tr('업무 종류', 'Task type')}</span>
            <select value={task} onChange={(event) => setTask(event.target.value)}>
              {TASKS.map((item) => (
                <option key={item.value || 'auto'} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <p className="form-note">
            {tr(
              '판단 순서는 민감 정보 규칙, 업무 종류, 이미지 첨부, Decider입니다. Decider의 신뢰도가 0.6보다 낮으면 기본값(Gemma, thinking 끔, 민감 처리)을 씁니다. 모델 선택의 신뢰도만 낮으면 민감 처리는 하지 않습니다.',
              'The order is sensitive data rule, task type, image attachment, then Decider. If its confidence is below 0.6, the defaults are used (Gemma, thinking off, treated as sensitive). If only the model choice confidence is low, the request is not treated as sensitive.',
            )}
          </p>
        </div>
        <div className="composer__send">
          <button id="route-run" className="button button--primary" type="submit" disabled={busy || !text.trim()}>
            {busy ? tr('판단하는 중', 'Deciding') : tr('판단하기', 'Decide')}
          </button>
          <p className="form-note" role="status">
            {busy
              ? tr(`${rows.length}줄을 판단했습니다.`, `${rows.length} ${rows.length === 1 ? 'line' : 'lines'} decided.`)
              : tr('모델을 부르지 않으므로 답변은 나오지 않습니다.', 'The model is not called, so no answer is returned.')}
          </p>
        </div>
      </form>

      {notice && <p className="record__error" role="alert">{explainFailure(notice)}</p>}

      {rows.length > 0 && (
        <section className="panel">
          <div className="table-scroll">
            <table className="grid-table">
              <thead>
                <tr>
                  <th scope="col">{tr('요청', 'Request')}</th>
                  <th scope="col">{tr('모델', 'Model')}</th>
                  <th scope="col">{tr('결정', 'Decision')}</th>
                  <th scope="col">{tr('근거', 'Reason')}</th>
                  <th scope="col">{tr('판단 시간', 'Decision time')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => {
                  const model = MODELS[row.model];
                  return (
                    <tr key={index}>
                      <td className="grid-table__text">{row.line}</td>
                      <td>
                        <span className={`pen pen--${model?.pen}`} aria-hidden="true" /> {model?.name ?? row.model}
                        {row.sensitive && <span className="chip chip--flag">{tr('민감 정보', 'Sensitive data')}</span>}
                      </td>
                      <td>{DECISIONS[row.decision] ?? row.decision}{row.thinking ? tr(', thinking 켬', ', thinking on') : ''}</td>
                      <td className="grid-table__text">{explain(row.decision, row.reason, row.sensitive).join(' ')}</td>
                      <td className="grid-table__number">{ms(row.decide_ms)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
