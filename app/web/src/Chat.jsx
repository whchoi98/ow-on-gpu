import { useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkCjkFriendly from 'remark-cjk-friendly';
import remarkCjkFriendlyGfmStrikethrough from 'remark-cjk-friendly-gfm-strikethrough';
import remarkGfm from 'remark-gfm';
import Sources, { Searches } from './Sources.jsx';
import { addSearch, linkCitations } from './citations.js';
import { ChatError, streamChat } from './stream.js';
import { explainFailure } from './api.js';
import { DECISIONS, MODELS, SEARCH_OFF, TASKS, explain, ms } from './format.js';
import { tr, useLang } from './i18n.js';

const plugins = [remarkGfm, remarkCjkFriendly, remarkCjkFriendlyGfmStrikethrough];
// 출처 링크와 모델이 쓴 링크는 새 탭에서 연다.
const components = { a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" /> };

// 여러 차례 주고받는 대화. 같은 세션 ID를 쓰므로 BFF가 첫 요청에서 내린 결정을 다음 요청에 다시 쓴다.
// 도중에 주민등록번호나 카드번호 형식을 보내면 그때부터 Gemma로 바뀐다.
export default function Chat({ session, onExpired }) {
  useLang();
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [turns, setTurns] = useState([]);  // {role, content, meta}
  const [task, setTask] = useState('');
  const [webSearch, setWebSearch] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);  // 실패한 요청의 오류. 그릴 때 지금 언어의 문구로 바꾼다.
  const end = useRef(null);

  function reset() {
    setSessionId(crypto.randomUUID());
    setTurns([]);
    setNotice(null);
  }

  async function send(event) {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || busy) return;
    const history = [...turns.map(({ role, content: text }) => ({ role, content: text })), { role: 'user', content }];
    setTurns((list) => [...list, { role: 'user', content }, { role: 'assistant', content: '', meta: null, live: true }]);
    setDraft('');
    setBusy(true);
    setNotice(null);
    const patch = (change) => setTurns((list) => list.map((turn, index) => (index === list.length - 1 ? change(turn) : turn)));
    let first = null;
    try {
      await streamChat({
        token: session.token,
        task,
        messages: history,
        sessionId,
        webSearch,
        onHeaders: (info) => patch((turn) => ({ ...turn, meta: info, asked: webSearch })),
        onNote: (note) =>
          note.event === 'tool_call' && note.name === 'web_search' && patch((turn) => ({ ...turn, ...addSearch(turn, note) })),
        onChunk: (chunk) => {
          if (chunk.kind !== 'content') return;
          first ??= chunk.ms;
          patch((turn) => ({ ...turn, content: turn.content + chunk.text, firstMs: first }));
        },
      });
      patch((turn) => ({ ...turn, live: false }));
    } catch (error) {
      if (error instanceof ChatError && error.status === 401) {
        onExpired();
        return;
      }
      setNotice(error);
      // 실패한 차례는 지워서 다음 요청의 대화 기록에 빈 답이 들어가지 않게 한다.
      setTurns((list) => list.slice(0, -2));
      setDraft(content);
    } finally {
      setBusy(false);
      end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }

  return (
    <div className="console__body">
      <section className="panel">
        <header className="panel__head">
          <h2>{tr('대화', 'Chat')}</h2>
          <p className="form-note">
            {tr(
              '한 세션에서 여러 차례 주고받습니다. BFF는 세션의 첫 요청에서 모델을 정하고 다음 요청부터는 그 결정을 다시 씁니다.',
              'A multi-turn conversation in one session. The BFF picks the model on the first request of the session and reuses that decision for later requests.',
            )}
          </p>
          <button type="button" className="link" onClick={reset} disabled={busy}>
            {tr('새 대화 시작', 'New chat')}
          </button>
        </header>

        {turns.length === 0 ? (
          <p className="panel__empty">
            {tr(
              '첫 메시지를 보내면 어느 모델로 갈지 정해집니다. 이어서 보낸 메시지가 같은 모델로 가는지, 도중에 주민등록번호 형식을 보내면 Gemma로 바뀌는지 확인해 보세요.',
              'The model is chosen when you send the first message. Check that later messages go to the same model, and that sending a resident registration number pattern partway through switches to Gemma.',
            )}
          </p>
        ) : (
          <ol className="turns">
            {turns.map((turn, index) => {
              const model = MODELS[turn.meta?.model];
              return (
                <li key={index} className={`turn turn--${turn.role}`}>
                  <span className="turn__who">{turn.role === 'user' ? tr('보낸 메시지', 'Your message') : model?.name ?? tr('답변', 'Answer')}</span>
                  {turn.role === 'user' ? (
                    <p className="turn__text">{turn.content}</p>
                  ) : (
                    <>
                      <Searches searches={turn.searches} />
                      <div className="answer">
                        {turn.content ? (
                          <Markdown remarkPlugins={plugins} components={components}>
                            {linkCitations(turn.content, turn.sources)}
                          </Markdown>
                        ) : (
                          <p className="answer__waiting">
                            {turn.searches?.length
                              ? tr('검색 결과를 읽고 답변을 쓰는 중입니다.', 'Reading the search results and writing the answer.')
                              : tr('답변을 기다리는 중입니다.', 'Waiting for the answer.')}
                          </p>
                        )}
                      </div>
                      <Sources sources={turn.sources} />
                    </>
                  )}
                  {turn.meta && (
                    <p className="turn__meta">
                      {model && <span className={`pen pen--${model.pen}`} aria-hidden="true" />}
                      {DECISIONS[turn.meta.decision] ?? turn.meta.decision}
                      {turn.firstMs != null && tr(`, 첫 토큰 ${ms(turn.firstMs)}`, `, first token ${ms(turn.firstMs)}`)}
                      {'. '}
                      {explain(turn.meta.decision, turn.meta.reason, turn.meta.sensitive).join(' ')}
                      {turn.asked && SEARCH_OFF[turn.meta.search] && ` ${SEARCH_OFF[turn.meta.search]}`}
                    </p>
                  )}
                </li>
              );
            })}
          </ol>
        )}
        <div ref={end} />

        {notice && <p className="record__error" role="alert">{explainFailure(notice)}</p>}

        <form className="chatbox" onSubmit={send}>
          <label className="field chatbox__task">
            <span>{tr('업무 종류', 'Task type')}</span>
            <select value={task} onChange={(event) => setTask(event.target.value)} disabled={turns.length > 0}>
              {TASKS.map((item) => (
                <option key={item.value || 'auto'} value={item.value}>{item.label}</option>
              ))}
            </select>
          </label>
          <label className="field chatbox__draft">
            <span>{tr('메시지', 'Message')}</span>
            <textarea
              id="chat-draft"
              rows={2}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) send(event);
              }}
            />
          </label>
          <button id="chat-send" className="button button--primary" type="submit" disabled={busy || !draft.trim()}>
            {busy ? tr('받는 중', 'Receiving') : tr('보내기', 'Send')}
          </button>
        </form>
        <label className="toggle">
          <input id="chat-web-search" type="checkbox" checked={webSearch} onChange={(event) => setWebSearch(event.target.checked)} />
          <span>{tr('웹 검색 사용', 'Use web search')}</span>
          <span className="toggle__hint">
            {tr(
              '모델이 필요하다고 판단하면 검색하고, 답변 아래에 출처를 보여 줍니다. 검색어는 us-east-1의 Amazon Bedrock AgentCore Web Search로 나갑니다.',
              'The model searches when it decides it needs to, and the sources appear below the answer. Search queries go to Amazon Bedrock AgentCore Web Search in us-east-1.',
            )}
          </span>
        </label>
        <p className="form-note">
          {tr(
            '업무 종류는 대화를 시작할 때만 고를 수 있습니다. 세션의 결정은 30분 동안 유지됩니다.',
            'You can choose the task type only when starting a chat. The session decision is kept for 30 minutes.',
          )}
        </p>
      </section>
    </div>
  );
}
