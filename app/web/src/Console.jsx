import { useCallback, useMemo, useRef, useState } from 'react';
import Flow from './Flow.jsx';
import Record from './Record.jsx';
import { addSearch } from './citations.js';
import { buildFlow } from './flow.js';
import { ChatError, streamChat } from './stream.js';
import { EXAMPLE_GROUPS, TASKS } from './format.js';
import { tr, useLang } from './i18n.js';

export default function Console({ session, onExpired }) {
  const lang = useLang();
  const [task, setTask] = useState(EXAMPLE_GROUPS[0].items[0].task);
  // 고른 예시는 [묶음, 항목] 번호로 둔다. 그래야 언어를 바꾸면 내용 칸의 예시 질문도 따라 바뀐다.
  // 내용을 손으로 고치면 예시가 아니게 되므로(picked는 null) 쓴 글을 그대로 둔다.
  const [picked, setPicked] = useState([0, 0]);
  const [typed, setTyped] = useState('');
  const prompt = picked ? EXAMPLE_GROUPS[picked[0]].items[picked[1]].prompt : typed;
  const [webSearch, setWebSearch] = useState(false);
  const [records, setRecords] = useState([]);
  const [busy, setBusy] = useState(false);
  const [focusId, setFocusId] = useState(null);     // 흐름 그림에 보여 줄 기록
  const [folded, setFolded] = useState(() => new Set());
  const counter = useRef(0);
  const flowBox = useRef(null);

  const focused = records.find((record) => record.id === focusId) ?? null;
  const flow = useMemo(() => buildFlow(focused), [focused, lang]);

  const fold = useCallback((id) => {
    setFolded((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const showPath = useCallback((id) => {
    setFocusId(id);
    flowBox.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, []);

  // 영어로 나온 추론 과정을 Gemma에게 한국어로 옮기게 한다(번역 업무는 Gemma로 간다).
  // 한국어 화면에서만 부른다(Reasoning.jsx). 그래서 모델에 보내는 지시문은 한국어로만 둔다.
  const translate = useCallback(
    (text, onPiece) =>
      streamChat({
        token: session.token,
        task: 'translate',
        maxTokens: 2048,
        prompt:
          '다음은 AI 모델이 답을 준비하면서 영어로 적은 추론 과정입니다. 내용을 더하거나 빼지 말고 한국어로 옮겨 주세요. ' +
          '옮긴 글만 쓰고 다른 말은 덧붙이지 마세요.\n\n' +
          text,
        onChunk: (chunk) => chunk.kind === 'content' && onPiece(chunk.text),
      }),
    [session.token],
  );

  const patch = useCallback((id, change) => {
    setRecords((list) => list.map((record) => (record.id === id ? change(record) : record)));
  }, []);

  async function send(event) {
    event?.preventDefault();
    const content = prompt.trim();
    if (!content || busy) return;
    counter.current += 1;
    const id = crypto.randomUUID();
    setBusy(true);
    setFocusId(id);
    setRecords((list) => [
      { id, number: counter.current, task, prompt: content, state: 'streaming', startedAt: performance.now(),
        ticks: [], text: '', reasoning: '', model: null, decision: null, reason: null, sensitive: false,
        headersMs: null, totalMs: null, requestId: null, finishReason: null, error: null,
        status: null, timing: null, cdn: null, toolCalls: 0, asked: webSearch, search: null, searches: [], sources: [] },
      ...list,
    ]);
    try {
      const { totalMs, finishReason } = await streamChat({
        token: session.token,
        task,
        prompt: content,
        webSearch,
        onHeaders: (info) => patch(id, (record) => ({ ...record, ...info })),
        // 웹 검색은 검색어와 출처를 기록에 담고, 주문 조회는 횟수만 센다.
        onNote: (note) =>
          note.event === 'tool_call' &&
          patch(id, (record) =>
            note.name === 'web_search' ? { ...record, ...addSearch(record, note) } : { ...record, toolCalls: record.toolCalls + 1 }),
        onChunk: (chunk) =>
          patch(id, (record) => ({
            ...record,
            ticks: [...record.ticks, { ms: chunk.ms, kind: chunk.kind }],
            text: chunk.kind === 'content' ? record.text + chunk.text : record.text,
            reasoning: chunk.kind === 'reasoning' ? record.reasoning + chunk.text : record.reasoning,
          })),
      });
      patch(id, (record) => ({ ...record, state: 'done', totalMs, finishReason }));
    } catch (error) {
      if (error instanceof ChatError && error.status === 401) {
        onExpired();
        return;
      }
      patch(id, (record) => ({
        ...record,
        state: 'failed',
        status: error instanceof ChatError ? error.status : record.status,
        totalMs: performance.now() - record.startedAt,
        // 문구가 아니라 오류를 둔다. 기록을 그릴 때 지금 언어의 문구로 바꾼다(Record.jsx).
        error,
      }));
    } finally {
      setBusy(false);
    }
  }

  return (
      <div className="console__body">
        <form className="composer" onSubmit={send} aria-labelledby="composer-title">
          <h2 id="composer-title">{tr('요청', 'Request')}</h2>

          <label className="toggle">
            <input id="web-search" type="checkbox" checked={webSearch} onChange={(event) => setWebSearch(event.target.checked)} />
            <span>{tr('웹 검색 사용', 'Use web search')}</span>
            <span className="toggle__hint">
              {tr(
                '모델이 필요하다고 판단하면 검색하고, 답변 아래에 출처를 보여 줍니다. 검색어는 us-east-1의 Amazon Bedrock AgentCore Web Search로 나갑니다. 민감 정보가 있는 요청에는 쓰지 않습니다.',
                'The model searches when it decides it needs to and shows the sources below the answer. Search queries go to Amazon Bedrock AgentCore Web Search in us-east-1. It is not used for requests with sensitive data.',
              )}
            </span>
          </label>

          <fieldset className="tasks">
            <legend>{tr('업무 종류', 'Task type')}</legend>
            {TASKS.map((item) => (
              <label key={item.value || 'auto'} className={`task ${task === item.value ? 'is-on' : ''}`}>
                <input
                  type="radio"
                  name="task"
                  value={item.value}
                  checked={task === item.value}
                  onChange={() => setTask(item.value)}
                />
                <span className={`pen pen--${item.pen}`} aria-hidden="true" />
                <span className="task__label">{item.label}</span>
                <span className="task__hint">{item.hint}</span>
              </label>
            ))}
          </fieldset>

          <label className="field">
            <span>{tr('내용', 'Prompt')}</span>
            <textarea
              id="prompt"
              value={prompt}
              rows={5}
              onChange={(event) => {
                setPicked(null);
                setTyped(event.target.value);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) send(event);
              }}
            />
          </label>

          <div className="examples">
            <h3>{tr('예시', 'Examples')}</h3>
            {EXAMPLE_GROUPS.map((group, groupIndex) => (
              <div key={group.title} className="examples__group">
                <span>{group.title}</span>
                {group.items.map((example, itemIndex) => (
                  <button
                    key={example.label}
                    type="button"
                    className="chip chip--button"
                    onClick={() => {
                      setTask(example.task);
                      setPicked([groupIndex, itemIndex]);
                      setWebSearch(Boolean(example.search));
                    }}
                  >
                    {example.label}
                  </button>
                ))}
              </div>
            ))}
          </div>

          <div className="composer__send">
            <button id="send" className="button button--primary" type="submit" disabled={busy || !prompt.trim()}>
              {busy ? tr('받는 중', 'Receiving') : tr('보내기', 'Send')}
            </button>
            <p className="form-note">
              {tr('Ctrl+Enter(Mac은 Cmd+Enter)로도 보냅니다. 요청마다 새 대화로 보냅니다.',
                'Ctrl+Enter (Cmd+Enter on Mac) also sends. Each request is sent as a new conversation.')}
            </p>
          </div>
        </form>

        <div ref={flowBox}>
          <Flow flow={flow} title={focused ? tr(`기록 ${focused.number}`, `Record ${focused.number}`) : ''} />
        </div>

        <section className="records" aria-label={tr('기록', 'Records')}>
          {records.length === 0 ? (
            <div className="records__empty">
              <h2>{tr('아직 기록이 없습니다', 'No records yet')}</h2>
              <p>
                {tr('요청을 보내면 위 그림에 지나가는 구간이 표시되고, 응답 조각이 도착하는 대로 여기 테이프에 눈금이 찍힙니다.',
                  'When you send a request, the diagram above shows the segments it passes through, and each response chunk marks a tick on the tape here as it arrives.')}
              </p>
              <ul className="legend">
                <li><span className="pen pen--gemma" aria-hidden="true" /> {tr('빨간 펜은 Gemma 4 31B', 'The red pen is Gemma 4 31B')}</li>
                <li><span className="pen pen--qwen" aria-hidden="true" /> {tr('파란 펜은 Qwen3.8-27B', 'The blue pen is Qwen3.8-27B')}</li>
              </ul>
            </div>
          ) : (
            <>
              <div className="records__bar">
                <span>{tr(`기록 ${records.length}건`, `${records.length} ${records.length === 1 ? 'record' : 'records'}`)}</span>
                <button type="button" className="link" onClick={() => setFolded(new Set(records.map((record) => record.id)))}>
                  {tr('모두 접기', 'Collapse all')}
                </button>
                <button type="button" className="link" onClick={() => setFolded(new Set())}>
                  {tr('모두 펼치기', 'Expand all')}
                </button>
              </div>
              {records.map((record) => (
                <Record
                  key={record.id}
                  record={record}
                  folded={folded.has(record.id)}
                  focused={record.id === focusId}
                  onFold={fold}
                  onShowPath={showPath}
                  onTranslate={translate}
                />
              ))}
            </>
          )}
        </section>
      </div>
  );
}
