import { useEffect, useMemo, useRef, useState } from 'react';
import Markdown from 'react-markdown';
import remarkCjkFriendly from 'remark-cjk-friendly';
import remarkCjkFriendlyGfmStrikethrough from 'remark-cjk-friendly-gfm-strikethrough';
import remarkGfm from 'remark-gfm';
import figureEn from './assets/llm-api-call.en.png';
import figure from './assets/llm-api-call.png';
import mapEn from './flow-map.en.svg?raw';
import map from './flow-map.svg?raw';
import { explainFailure } from './api.js';
import {
  REGIONS, SIDES, STAGES, budgetRows, duration, mapFor, mapForLive, railStates, sideOf, stageCards, stageOfPhase,
  summarizeLive,
} from './apicall.js';
import { linkCitations } from './citations.js';
import { tr, useLang } from './i18n.js';
import Sources, { Searches } from './Sources.jsx';
import { SEARCH_OFF } from './format.js';
import { ChatError, streamChat } from './stream.js';
import './apicall.css';

// 답변은 대화 보기와 같은 구성으로 그린다. 출처 링크와 모델이 쓴 링크는 새 탭에서 연다.
const plugins = [remarkGfm, remarkCjkFriendly, remarkCjkFriendlyGfmStrikethrough];
const components = { a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" /> };

const MAP_STATES = ['is-on', 'is-now', 'is-off', 'is-fail', 'is-stream'];
// 재생할 때 단계마다 머무는 시간(ms). 5단계는 읽을 것이 많아 더 오래 둔다.
const DWELL = { 5: 4200 };
const DWELL_DEFAULT = 2800;
// 실제 요청의 최대 출력. 8단계의 S1과 같은 128토큰이다. 웹 검색을 켠 요청은 검색 결과를 정리한 답이 잘리지 않게 더 준다.
const LIVE_MAX_TOKENS = 128;
const SEARCH_MAX_TOKENS = 512;

// 단계 띠 아래의 펜 표시가 놓일 자리(%). 띠의 칸 너비는 apicall.css의 grid-template-columns와 같다(5번 칸만 1.35배).
const ENGINE_WIDTH = 1.35;
function penLeft(n) {
  const before = n <= 5 ? n - 1 : n - 2 + ENGINE_WIDTH;
  const width = n === 5 ? ENGINE_WIDTH : 1;
  return ((before + width / 2) / (7 + ENGINE_WIDTH)) * 100;
}

// 요청 보기와 같은 지도(flow-map.svg)에 단계의 상태와 값을 표시한다. 지도에 없는 요소는 건너뛴다.
// SVG는 빌드할 때 묶이는 저장소의 파일이라 그대로 넣는다(Flow.jsx와 같은 방식).
// 영어 화면에서는 같은 id와 좌표로 만든 영어판 지도를 쓴다. 지도가 바뀌면 표시를 다시 써넣는다.
function ArchMap({ flow, label }) {
  const lang = useLang();
  const box = useRef(null);

  useEffect(() => {
    const root = box.current;
    root.querySelectorAll('.fnode, .fedge').forEach((element) => element.classList.remove(...MAP_STATES));
    root.querySelectorAll('.fnode__value').forEach((element) => {
      element.textContent = '';
    });
    for (const [name, state] of Object.entries(flow.nodes)) root.querySelector(`#n-${name}`)?.classList.add(`is-${state}`);
    for (const [name, state] of Object.entries(flow.edges)) root.querySelector(`#e-${name}`)?.classList.add(`is-${state}`);
    for (const [name, text] of Object.entries(flow.values)) {
      const slot = root.querySelector(`#v-${name}`);
      if (slot) slot.textContent = text;
    }
  }, [flow, lang]);

  return (
    <div ref={box} className="flow__map" role="img" aria-label={label}
      dangerouslySetInnerHTML={{ __html: lang === 'en' ? mapEn : map }} />
  );
}

function Rows({ rows }) {
  return (
    <dl className="apicall__rows">
      {rows.map(([name, value]) => (
        <div key={name}>
          <dt>{name}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

// LLM API 호출 한 건의 여덟 단계와, 단계마다 이 환경에서 그 일을 하는 구성 요소를 함께 보여 준다.
// 단계를 고르거나 재생하면 지도에서 그 구성 요소가 켜지고, 실제 요청을 보내면 그 요청의 값으로 채운다.
export default function ApiCall({ session, onExpired }) {
  const lang = useLang();
  const [side, setSide] = useState('gemma');
  const [selected, setSelected] = useState(1);
  const [playing, setPlaying] = useState(false);
  const [live, setLive] = useState(null);
  // 웹 검색 경로를 함께 볼지. 켜면 6단계에서 Web Search가 켜지고, 실제 요청도 웹 검색을 켜서 보낸다.
  const [webSearch, setWebSearch] = useState(true);
  const top = useRef(null);

  const running = live?.phase === 'sending' || live?.phase === 'engine' || live?.phase === 'streaming';
  const summary = useMemo(() => (live?.phase === 'failed' ? null : summarizeLive(live)), [live]);
  // 요청이 진행되는 동안에는 지금 진행 중인 단계를 따라간다.
  const shown = running ? stageOfPhase(live.phase) ?? selected : selected;
  const stage = STAGES[shown - 1];
  const states = railStates(shown, live);
  const flow = useMemo(
    () => (running || live?.phase === 'failed' ? mapForLive(live) : mapFor(shown, side, summary, webSearch)),
    [running, live, shown, side, summary, webSearch, lang],
  );
  const budget = budgetRows(side, summary);
  // 끝난 요청의 값. Chunk가 올 때마다 설명 칸이 바뀌지 않도록, 요청의 값은 요청이 끝난 뒤에 적는다. 진행 중의 값은 지도에 나온다.
  const finished = running ? null : summary;
  // 설명 칸은 지금 단계만이 아니라 여덟 단계를 모두 그린다. 재생이나 요청이 지나간 단계의 설명과 값이 그대로 남는다.
  const cards = stageCards(states, side, finished, webSearch);

  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => {
      if (selected >= STAGES.length) setPlaying(false);
      else setSelected(selected + 1);
    }, DWELL[selected] ?? DWELL_DEFAULT);
    return () => clearTimeout(timer);
  }, [playing, selected]);

  function choose(n, scroll = false) {
    if (running) return;
    setPlaying(false);
    setSelected(n);
    if (live?.phase === 'failed') setLive(null);
    if (scroll) top.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function togglePlay() {
    if (running) return;
    if (playing) {
      setPlaying(false);
      return;
    }
    if (live?.phase === 'failed') setLive(null);
    if (selected >= STAGES.length) setSelected(1);
    setPlaying(true);
  }

  function pickSide(next) {
    if (running || next === side) return;
    setSide(next);
    // 다른 모델의 요청에서 얻은 값을 섞어 보이지 않게 한다.
    setLive(null);
  }

  function toggleSearch(next) {
    if (running) return;
    setWebSearch(next);
    // 조건이 다른 요청의 값을 섞어 보이지 않게 한다.
    setLive(null);
  }

  function onRailKey(event, n) {
    const step = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    const next = n + step;
    if (!step || next < 1 || next > STAGES.length) return;
    event.preventDefault();
    choose(next);
    event.currentTarget.parentElement.parentElement.querySelector(`[data-stage="${next}"]`)?.focus();
  }

  async function send() {
    if (running) return;
    setPlaying(false);
    const target = SIDES[side];
    const ticks = [];
    const notes = [];
    const prompt = webSearch ? target.searchPrompt : target.prompt;
    let text = '';
    setLive({ phase: 'sending', side, info: null, ticks, result: null, asked: webSearch, notes, prompt, text });
    try {
      const result = await streamChat({
        token: session.token,
        task: target.task,
        prompt,
        webSearch,
        maxTokens: webSearch ? SEARCH_MAX_TOKENS : LIVE_MAX_TOKENS,
        onHeaders: (info) => {
          if (info.status !== 200) return;
          const actual = sideOf(info.model);
          if (actual) setSide(actual);
          setLive((current) => ({ ...current, phase: 'engine', info }));
        },
        onChunk: (chunk) => {
          ticks.push({ ms: chunk.ms, kind: chunk.kind });
          if (chunk.kind === 'content') text += chunk.text;
          setLive((current) => ({ ...current, phase: 'streaming', ticks: [...ticks], text }));
        },
        // 모델이 web_search 도구를 부를 때마다 검색어, 검색 시간, 출처 목록이 온다.
        onNote: (note) => {
          if (note.event !== 'tool_call' || note.name !== 'web_search') return;
          notes.push(note);
          setLive((current) => ({ ...current, notes: [...notes] }));
        },
      });
      setLive((current) => ({ ...current, phase: 'done', result }));
      setSelected(7);
    } catch (error) {
      if (error instanceof ChatError && error.status === 401) {
        onExpired();
        return;
      }
      // 오류는 그대로 두고 그릴 때 문구로 바꾼다. 언어를 바꾸면 실패 문구도 따라 바뀐다.
      setLive((current) => ({ ...current, phase: 'failed', status: error instanceof ChatError ? error.status : null, error }));
    }
  }

  const searched = live?.notes?.length ?? 0;
  const searchedTimes = searched === 1 ? '1 time' : `${searched} times`;
  const searchedCount = searched === 1 ? '1 web search' : `${searched} web searches`;
  const status = running
    ? { sending: tr(
          '요청을 보냈습니다. 응답 헤더가 오면 1, 2, 4단계의 값이 채워집니다.',
          'Request sent. When the response headers arrive, the values for steps 1, 2, and 4 are filled in.',
        ),
        engine: searched
          ? tr(
              `모델이 웹 검색을 ${searched}회 불렀습니다. BFF가 결과를 붙여 다시 추론을 요청했습니다.`,
              `The model called web search ${searchedTimes}. The BFF attached the results and requested inference again.`,
            )
          : tr('모델이 첫 토큰을 만들고 있습니다.', 'The model is generating the first token.'),
        streaming: searched
          ? tr(
              `웹 검색 ${searched}회의 결과로 모델이 답하고 있습니다. Chunk가 브라우저로 돌아오고 있습니다.`,
              `The model is answering from the results of ${searchedCount}. Chunks are coming back to the browser.`,
            )
          : tr(
              'Chunk가 모델에서 브라우저로 돌아오고 있습니다. 5, 6, 7단계가 Chunk마다 함께 진행됩니다.',
              'Chunks are coming back from the model to the browser. Steps 5, 6, and 7 run together for every chunk.',
            ) }[live.phase]
    : live?.phase === 'failed'
      ? explainFailure(live.error)
      : live?.phase === 'done'
        ? tr(
            `요청이 끝났습니다. 전체 시간은 ${duration(summary.totalMs)}입니다. 지도 아래의 여덟 단계에 이 요청이 보여 준 값을 함께 적었습니다.`,
            `Request finished. Total time was ${duration(summary.totalMs)}. The eight steps below the map now include the values this request showed.`,
          )
        : playing
          ? tr('단계를 차례로 보여 주고 있습니다.', 'Showing the steps in order.')
          : tr(
              '단계를 고르거나 재생하면 그 일을 하는 구성 요소가 지도에서 켜집니다.',
              'Select a step or press Play, and the components that do that work light up on the map.',
            );
  // 질문은 측정에 쓴 한국어 그대로 보낸다. 영어 화면에서는 뜻을 알 수 있게 영어 풀이를 질문 아래에 덧붙인다(한국어 화면에서는 빈 문자열).
  const gloss = live ? SIDES[live.side]?.[live.asked ? 'searchPromptGloss' : 'promptGloss'] : '';

  return (
    <div className="console__body apicall">
      <section className="panel" ref={top}>
        <header className="panel__head">
          <h2>{tr('API 호출', 'API call')}</h2>
          <p className="form-note">
            {tr(
              'LLM API 호출 한 건이 거치는 여덟 단계입니다. 단계마다 이 환경에서 그 일을 하는 구성 요소를 지도에 표시하고, 8단계에서 잰 값과 지금 보낸 요청의 값을 나란히 보여 줍니다.',
              'The eight steps one LLM API call goes through. For each step, the map marks the components that do that work in this environment, and the values measured in build step 8 are shown next to the values of the request you just sent.',
            )}
          </p>
        </header>

        <div className="apicall__controls">
          <div className="apicall__sides" role="group" aria-label={tr('모델', 'Model')}>
            {Object.entries(SIDES).map(([key, item]) => (
              <button key={key} type="button" className="apicall__side" aria-pressed={side === key} disabled={running}
                onClick={() => pickSide(key)}>
                <span className={`pen pen--${key}`} aria-hidden="true" />
                {item.name}
                <span className="apicall__task">{item.taskLabel}</span>
              </button>
            ))}
          </div>
          <button type="button" className="button" onClick={togglePlay} disabled={running}>
            {playing ? tr('멈춤', 'Pause') : selected >= STAGES.length ? tr('처음부터 재생', 'Play from start') : tr('재생', 'Play')}
          </button>
          <button type="button" className="button button--primary" onClick={send} disabled={running}>
            {running ? tr('받는 중', 'Receiving') : tr('실제 요청 보내기', 'Send a real request')}
          </button>
          <p className={`apicall__status${live?.phase === 'failed' ? ' is-failed' : ''}`} role="status">{status}</p>
        </div>
        <label className="toggle">
          <input id="apicall-web-search" type="checkbox" checked={webSearch} disabled={running}
            onChange={(event) => toggleSearch(event.target.checked)} />
          <span>{tr('웹 검색 사용', 'Use web search')}</span>
          <span className="toggle__hint">
            {tr(
              '켜면 6단계에서 Web Search가 지도에 켜지고, 실제 요청도 웹 검색을 켜서 보냅니다. 검색할지는 모델이 정하고, 검색어는 us-east-1의 Amazon Bedrock AgentCore Web Search로 나갑니다.',
              'When on, Web Search lights up on the map at step 6, and the real request is sent with web search on. The model decides whether to search, and the queries go to Amazon Bedrock AgentCore Web Search in us-east-1.',
            )}
          </span>
        </label>

        <ol className="apicall__rail" style={{ '--pen': `${penLeft(shown)}%` }}>
          {STAGES.map((item) => (
            <li key={item.n} className={`apicall__cell${item.n === 5 ? ' apicall__cell--engine' : ''}`}>
              <button
                type="button"
                data-stage={item.n}
                className={`apicall__step${states[item.n] ? ` is-${states[item.n]}` : ''}`}
                aria-current={item.n === shown ? 'step' : undefined}
                disabled={running}
                onClick={() => choose(item.n)}
                onKeyDown={(event) => onRailKey(event, item.n)}
              >
                <span className="apicall__n">{item.n}</span>
                <span className="apicall__en">{item.en}</span>
                <span className="apicall__ko">{item.ko}</span>
              </button>
            </li>
          ))}
          <li className="apicall__pen" aria-hidden="true" />
        </ol>

        <div className="apicall__stage">
          <figure className="flow apicall__map">
            <figcaption className="flow__head">
              <h3>{tr('지금 아키텍처', 'Current architecture')}</h3>
              <span className="flow__title">{stage.n} {stage.en}, {stage.ko}</span>
              <ul className="flow__legend">
                <li><span className="swatch swatch--now" aria-hidden="true" /> {tr('이 단계의 일을 하는 곳', 'Does the work of this step')}</li>
                <li><span className="swatch swatch--on" aria-hidden="true" /> {tr('지나온 곳', 'Already passed')}</li>
              </ul>
            </figcaption>
            <div className="flow__scroll">
              <ArchMap
                flow={flow}
                label={tr(
                  `${stage.n}단계 ${stage.en}에서 일하는 구성 요소를 표시한 아키텍처 지도`,
                  `Architecture map marking the components that work at step ${stage.n}, ${stage.en}`,
                )}
              />
            </div>
            <p className="flow__status">
              {summary && !running
                ? tr(
                    '지도의 값 가운데 이 요청에서 얻은 것은 그 값으로, 나머지는 8단계 측정 중앙값으로 적었습니다.',
                    'Values on the map that came from this request show that value. The rest are build step 8 medians.',
                  )
                : tr(
                    '지도의 값은 8단계 측정 중앙값입니다(요청을 하나씩 보낸 결과).',
                    'Values on the map are build step 8 medians (requests sent one at a time).',
                  )}
            </p>
          </figure>

          <p className="form-note">
            {running
              ? tr(
                  '요청이 끝나면 아래의 단계마다 이 요청이 보여 준 값이 함께 나옵니다. 진행 중의 값은 지도에 표시됩니다.',
                  'When the request finishes, each step below also shows the values this request showed. Values in progress are shown on the map.',
                )
              : finished
                ? tr(
                    '아래는 여덟 단계의 설명입니다. 단계마다 8단계 측정 중앙값과 이 요청이 보여 준 값을 함께 적었습니다.',
                    'Below are the eight steps. Each one lists the build step 8 medians together with the values this request showed.',
                  )
                : tr(
                    '아래는 여덟 단계의 설명과 8단계 측정 중앙값입니다. 실제 요청 보내기를 누르면 그 요청이 단계마다 보여 준 값이 함께 나옵니다.',
                    'Below are the eight steps with the build step 8 medians. Press Send a real request, and the values that request showed at each step are added.',
                  )}
          </p>

          <ol className="apicall__cards">
            {cards.map(({ stage: item, state, measured, search, request }) => (
              <li key={item.n}>
                <article className={`apicall__detail${state ? ` is-${state}` : ''}`} aria-current={item.n === shown ? 'step' : undefined}>
                  <div className="apicall__main">
                    <header className="apicall__detail-head">
                      <span className="apicall__badge">{item.n}</span>
                      <h3>{item.en}</h3>
                      <span className="apicall__detail-ko">{item.ko}</span>
                      {state && (
                        <span className="apicall__state">
                          {state === 'now' ? tr('지금 단계', 'Current step') : tr('지나온 단계', 'Passed step')}
                        </span>
                      )}
                    </header>
                    <p className="apicall__lead">{item.lead}</p>
                    <h4>{tr('이 환경에서 이 일을 하는 것', 'Components that do this work here')}</h4>
                    <dl className="apicall__here">
                      {item.here.map(([name, text]) => (
                        <div key={name}>
                          <dt>{name}</dt>
                          <dd>{text}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>

                  <div className="apicall__side-col">
                    <div className="apicall__values">
                      <section>
                        <h4>{tr('8단계 측정 중앙값', 'Build step 8 medians')} <span>{SIDES[side].name}</span></h4>
                        <Rows rows={measured} />
                      </section>
                      {search.length > 0 && (
                        <section>
                          <h4>{tr('웹 검색', 'Web search')} <span>{tr('작업 장비와 BFF에서 잰 값', 'Measured from the work machine and at the BFF')}</span></h4>
                          <Rows rows={search} />
                        </section>
                      )}
                      {finished && (
                        <section>
                          <h4>{tr('이 요청의 값', 'Values from this request')}</h4>
                          {request.length ? (
                            <Rows rows={request} />
                          ) : (
                            <p className="apicall__none">
                              {tr(
                                '이 단계의 시간은 브라우저에서 알 수 없습니다. 8단계 측정 중앙값은 vLLM 지표와 로그로 잰 값입니다.',
                                'The browser cannot see the time of this step. The build step 8 medians come from vLLM metrics and logs.',
                              )}
                            </p>
                          )}
                        </section>
                      )}
                    </div>
                    <p className="apicall__note">{item.note}</p>
                  </div>
                </article>
              </li>
            ))}
          </ol>

          <div className="apicall__budget">
            <p className="apicall__budget-title">
              {tr('첫 내용까지의 시간', 'Time to first content')} <span>{SIDES[side].name}, {tr('두 줄은 같은 눈금', 'both rows on the same scale')}</span>
            </p>
            {budget.map((row) => (
              <div key={row.key} className="apicall__bar-row">
                <span className="apicall__bar-label">{row.label} <b>{duration(row.total)}</b></span>
                <span className="apicall__bar" role="img"
                  aria-label={row.parts.map((part) => `${part.name} ${duration(part.value)}`).join(', ')}>
                  {row.parts.map((part) => (
                    <span key={part.key} className={`apicall__seg apicall__seg--${part.key}`} style={{ width: `${part.percent}%` }} />
                  ))}
                </span>
                <span className="apicall__bar-text">
                  {row.parts.map((part) => (
                    <span key={part.key}>
                      <i className={`apicall__dot apicall__seg--${part.key}`} aria-hidden="true" />
                      {part.name} {duration(part.value)}
                    </span>
                  ))}
                </span>
              </div>
            ))}
          </div>

          {live?.prompt && live.phase !== 'failed' && (
            <section className="apicall__answer" aria-label={tr('이 요청의 질문과 답변', 'Question and answer of this request')}>
              <h3>{tr('이 요청의 답변', 'Answer to this request')}</h3>
              <p className="apicall__question">
                {live.prompt}
                {lang === 'en' && gloss && (
                  <>
                    <br />
                    <span className="form-note">Sent in Korean, the same question as in the measurements. In English: {gloss}</span>
                  </>
                )}
              </p>
              {live.asked && live.info && (SEARCH_OFF[live.info.search] || live.info.search == null) && (
                <p className="apicall__none">
                  {SEARCH_OFF[live.info.search]
                    ?? tr(
                      'BFF가 웹 검색 상태를 알려 주지 않았습니다. 웹 검색을 넣은 BFF가 아직 배포되지 않았을 수 있습니다.',
                      'The BFF did not report the web search state. The BFF with web search may not be deployed yet.',
                    )}
                </p>
              )}
              <Searches searches={summary?.searches} />
              <div className="answer">
                {live.text ? (
                  <Markdown remarkPlugins={plugins} components={components}>
                    {linkCitations(live.text, summary?.sources)}
                  </Markdown>
                ) : (
                  <p className="answer__waiting">
                    {searched
                      ? tr('검색 결과를 읽고 답변을 쓰는 중입니다.', 'Reading the search results and writing the answer.')
                      : running
                        ? tr('답변을 기다리는 중입니다.', 'Waiting for the answer.')
                        : tr('답변 내용이 없습니다.', 'The answer is empty.')}
                  </p>
                )}
              </div>
              {/* 검색 결과를 쓴 답변에는 출처와 링크를 함께 보여 준다(AgentCore Web Search의 이용 조건). */}
              <Sources sources={summary?.sources} />
            </section>
          )}
        </div>
      </section>

      <section className="panel">
        <header className="panel__head">
          <h2>{tr('한 장으로 보기', 'On one page')}</h2>
          <p className="form-note">
            {tr(
              '같은 여덟 단계를 한 장에 모은 그림입니다. 그림에서 단계를 누르면 위 지도에서 그 단계의 구성 요소가 켜집니다.',
              'The same eight steps in one figure. Select a step in the figure, and its components light up on the map above.',
            )}
          </p>
        </header>
        <div className="table-scroll">
          <div className="apicall__sheet">
            {/* 영어판 그림은 한국어판과 크기와 좌표가 같아서 아래의 영역 버튼을 그대로 쓴다. */}
            <img
              src={lang === 'en' ? figureEn : figure}
              width="1920"
              height="1080"
              loading="lazy"
              alt={tr(
                'LLM API 호출 한 건의 여정. API Gateway, Load Balancer, Tokenization, Model Router, Inference Engine(Prefill, Decode, Hardware), Post-processing, Response & Billing, Logging & Observability의 여덟 단계마다 이 환경에서 그 일을 하는 구성 요소와 측정값을 적었다.',
                'The journey of one LLM API call. For each of the eight steps (API Gateway, Load Balancer, Tokenization, Model Router, Inference Engine with Prefill, Decode, and Hardware, Post-processing, Response & Billing, Logging & Observability), it lists the components that do that work in this environment and the measured values.',
              )}
            />
            {STAGES.map((item) => (
              <button
                key={item.n}
                type="button"
                className={`apicall__spot${item.n === shown ? ' is-current' : ''}`}
                style={{
                  left: `${REGIONS[item.n].left}%`, top: `${REGIONS[item.n].top}%`,
                  width: `${REGIONS[item.n].width}%`, height: `${REGIONS[item.n].height}%`,
                }}
                aria-label={tr(`${item.n}단계 ${item.en}을 지도에서 보기`, `Show step ${item.n}, ${item.en}, on the map`)}
                aria-pressed={item.n === shown}
                disabled={running}
                onClick={() => choose(item.n, true)}
              />
            ))}
            {REGIONS.search && (
              <button
                type="button"
                className={`apicall__spot${shown === 6 && webSearch ? ' is-current' : ''}`}
                style={{
                  left: `${REGIONS.search.left}%`, top: `${REGIONS.search.top}%`,
                  width: `${REGIONS.search.width}%`, height: `${REGIONS.search.height}%`,
                }}
                aria-label={tr(
                  '웹 검색 경로를 지도에서 보기. 6단계 Post-processing으로 갑니다',
                  'Show the web search path on the map. Goes to step 6, Post-processing',
                )}
                disabled={running}
                onClick={() => {
                  if (!webSearch) toggleSearch(true);
                  choose(6, true);
                }}
              />
            )}
          </div>
        </div>
        <p className="form-note">
          {tr(
            '수치는 서울 리전에서 잰 값입니다. 구간 값은 2026년 11월 15일에 요청을 하나씩 보낸 중앙값이고, S1은 11월 14일에 잰 입력 256토큰, 출력 128토큰, 동시성 1의 값입니다.',
            'The numbers were measured in the Seoul Region. Segment values are medians of requests sent one at a time on November 15, 2026, and S1 was measured on November 14 with 256 input tokens, 128 output tokens, and concurrency 1.',
          )}
        </p>
      </section>
    </div>
  );
}
