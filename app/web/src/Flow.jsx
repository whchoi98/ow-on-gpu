import { useEffect, useMemo, useRef, useState } from 'react';
import map from './flow-map.svg?raw';
import mapEn from './flow-map.en.svg?raw';
import { STEPS, stepFlow } from './flow-steps.js';
import { localized, tr, useLang } from './i18n.js';
import './flow-extra.css';

const STATES = ['is-on', 'is-now', 'is-off', 'is-fail', 'is-stream', 'is-feed', 'is-opt'];
const PHASES = localized(() => ({
  waiting: tr(
    'BFF의 응답 헤더를 기다리는 중입니다. 헤더가 오면 실제로 거친 경로를 표시합니다.',
    'Waiting for the response headers from the BFF. Once they arrive, the map shows the path actually taken.',
  ),
  streaming: tr('응답 Chunk가 모델에서 브라우저로 돌아오고 있습니다.', 'Response chunks are coming back from the model to the browser.'),
  done: tr(
    '요청이 끝났습니다. 표시한 경로와 시간은 이 요청의 값입니다.',
    'The request is complete. The path and timing shown are the values of this request.',
  ),
  failed: tr('요청이 분홍색으로 표시한 곳에서 막혔습니다.', 'The request was stopped at the point marked in pink.'),
}));
// 재생할 때 한 단계에 머무는 시간
const STEP_MS = 2600;

// 요청 경로 그림. 그림은 docs/infographic/flow.py가 만든 SVG이고, 여기서는 요소의 상태와 값만 바꾼다.
// 영어 화면에서는 같은 id를 가진 영어판 그림(flow-map.en.svg)을 쓴다.
//   flow   요청 하나의 경로와 값(flow.js의 buildFlow). 없으면 아무것도 켜지 않는다
//   title  그 요청의 이름(예: 기록 3). 바뀌면 단계 선택을 풀고 그 요청을 보인다
//   steps  아래의 단계 띠(0 모델 적재에서 5 추론 요청까지)를 보일지. 기본은 보인다
export default function Flow({ flow, title, steps = true }) {
  const lang = useLang();
  const box = useRef(null);
  const buttons = useRef([]);
  const [step, setStep] = useState(null);       // 띠에서 고른 단계. null이면 요청의 경로를 보인다
  const [playing, setPlaying] = useState(false);

  // 다른 기록을 보기 시작하면(요청을 새로 보냈을 때도) 그 요청의 경로로 돌아간다.
  useEffect(() => {
    setStep(null);
    setPlaying(false);
  }, [title]);

  // 재생: 고른 단계에서 잠시 머물고 다음 단계로 넘어간다. 마지막 단계에서 멈춘다.
  useEffect(() => {
    if (!playing) return undefined;
    const timer = setTimeout(() => {
      if (step == null || step >= STEPS.length - 1) setPlaying(false);
      else setStep(step + 1);
    }, STEP_MS);
    return () => clearTimeout(timer);
  }, [playing, step]);

  // 5번(추론 요청)을 골랐고 표시할 요청이 있으면 측정값 대신 그 요청의 실제 값을 보인다.
  const live = step == null || (step === 5 && Boolean(flow));
  // 단계를 보는 동안에는 요청의 Chunk가 도착해도 그림을 다시 그리지 않는다.
  const record = live ? flow : null;
  const shown = useMemo(() => (live ? record : stepFlow(step)), [live, record, step, lang]);
  // 그림의 번호 배지 가운데 강조할 것. 요청을 보이는 중이면 5번이다.
  const active = step ?? (flow ? 5 : null);

  useEffect(() => {
    const root = box.current;
    root.querySelectorAll('.fnode, .fedge, .fzone, .fbadge').forEach((element) => element.classList.remove(...STATES));
    root.querySelectorAll('.fnode__value').forEach((element) => {
      element.textContent = '';
    });
    root.querySelectorAll('.fbadge').forEach((element) => {
      if (active != null && element.dataset.step === String(active)) element.classList.add('is-on');
    });
    if (!shown) return;
    for (const [name, state] of Object.entries(shown.nodes)) root.querySelector(`#n-${name}`)?.classList.add(`is-${state}`);
    for (const [name, state] of Object.entries(shown.edges)) root.querySelector(`#e-${name}`)?.classList.add(`is-${state}`);
    for (const [name, text] of Object.entries(shown.values)) {
      const slot = root.querySelector(`#v-${name}`);
      if (slot) slot.textContent = text;
    }
    // 좁은 화면에서는 그림을 가로로 밀어 본다. 단계를 고르면 그 단계의 구성 요소가 보이는 곳으로 옮긴다.
    const scroller = root.parentElement;
    if (shown.phase !== 'step' || scroller.scrollWidth <= scroller.clientWidth) return;
    const boxes = [...root.querySelectorAll('.fnode.is-on, .fzone.is-on')].map((element) => element.getBoundingClientRect());
    if (!boxes.length) return;
    const origin = root.getBoundingClientRect().left;
    const left = Math.min(...boxes.map((rect) => rect.left)) - origin;
    const right = Math.max(...boxes.map((rect) => rect.right)) - origin;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollTo({ left: Math.max(0, (left + right - scroller.clientWidth) / 2), behavior: still ? 'auto' : 'smooth' });
    // 언어가 바뀌면 그림이 통째로 바뀌므로 상태와 값을 다시 써넣는다.
  }, [shown, active, lang]);

  function choose(index) {
    setPlaying(false);
    setStep((current) => (current === index ? null : index));
  }

  function play() {
    if (playing) {
      setPlaying(false);
      return;
    }
    setStep(0);
    setPlaying(true);
  }

  // 띠 안에서는 좌우 화살표로 옆 단계로 옮겨 가며 고른다.
  function onKeyDown(event, index) {
    const move = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!move) return;
    event.preventDefault();
    const next = (index + move + STEPS.length) % STEPS.length;
    buttons.current[next]?.focus();
    setPlaying(false);
    setStep(next);
  }

  const chosen = step == null ? null : STEPS[step];

  return (
    <figure className="flow flow--path">
      <figcaption className="flow__head">
        <h2>{tr('요청 경로', 'Request path')}</h2>
        <span className="flow__title">{title}</span>
        <ul className="flow__legend">
          <li><span className="swatch swatch--now" aria-hidden="true" /> {tr('진행 중', 'In progress')}</li>
          <li><span className="swatch swatch--on" aria-hidden="true" /> {tr('지나온 구간', 'Passed')}</li>
          <li><span className="swatch swatch--fail" aria-hidden="true" /> {tr('막힌 구간', 'Blocked')}</li>
        </ul>
      </figcaption>
      <div className="flow__scroll">
        <div
          ref={box}
          className="flow__map"
          role="img"
          aria-label={tr(
            '요청이 브라우저에서 모델까지 가는 경로와, 모델과 이미지를 GPU 노드에 대는 구조',
            'The path a request takes from the browser to a model, and how models and images are supplied to the GPU nodes',
          )}
          data-step={live ? undefined : step}
          data-active={active ?? undefined}
          dangerouslySetInnerHTML={{ __html: lang === 'en' ? mapEn : map }}
        />
      </div>

      {steps && (
        <div className="steps">
          <div className="steps__head">
            <h3>{tr('모델을 올려 서빙하기까지', 'From model upload to serving')}</h3>
            <p>
              {tr(
                '단계를 고르면 그 단계에서 움직이는 구성 요소가 그림에서 켜집니다. 번호는 그림의 번호와 같습니다.',
                'Pick a step to light up the components that take part in it. The numbers match the numbers on the map.',
              )}
            </p>
            <div className="steps__controls">
              <button type="button" className="link" aria-pressed={playing} onClick={play}>
                {playing ? tr('재생 멈춤', 'Stop playback') : tr('0번부터 재생', 'Play from step 0')}
              </button>
              {step != null && (
                <button type="button" className="link" onClick={() => choose(step)}>
                  {flow ? tr('요청 경로로 돌아가기', 'Back to the request path') : tr('선택 풀기', 'Clear selection')}
                </button>
              )}
            </div>
          </div>
          <ol className="steps__list">
            {STEPS.map((item, index) => (
              <li key={item.n}>
                <button
                  ref={(element) => {
                    buttons.current[index] = element;
                  }}
                  type="button"
                  className={`step step--${item.tone}`}
                  aria-pressed={step === index}
                  onClick={() => choose(index)}
                  onKeyDown={(event) => onKeyDown(event, index)}
                >
                  <span className="step__no">{item.n}</span>
                  <span className="step__title">{item.title}</span>
                  <span className="step__value">{item.value}</span>
                </button>
              </li>
            ))}
          </ol>
          <div className="steps__detail" role="status">
            {chosen ? (
              <div className={`steps__card step--${chosen.tone}`}>
                <div className="steps__text">
                  <h4>
                    <span className="step__no">{chosen.n}</span>
                    {chosen.title}
                  </h4>
                  <p>{chosen.text}</p>
                  {chosen.more && <p>{chosen.more}</p>}
                  {step === 5 && flow && (
                    <p className="steps__live">
                      {tr(
                        `지금 그림은 측정값이 아닌 ${title || '이 요청'}의 실제 경로와 시간입니다.`,
                        `The map now shows the actual path and timing of ${title || 'this request'}, not the measured values.`,
                      )}
                    </p>
                  )}
                </div>
                <div className="steps__measured">
                  <dl>
                    {chosen.rows.map(([name, value]) => (
                      <div key={name}>
                        <dt>{name}</dt>
                        <dd>{value}</dd>
                      </div>
                    ))}
                  </dl>
                  <p>{chosen.note}</p>
                </div>
              </div>
            ) : (
              <p className="steps__hint">
                {tr(
                  '1번에서 4번의 값은 Gemma 콜드 스타트의 기준 구성과 최적화 구성, 5번은 Gemma와 Qwen의 중앙값입니다. 1번에서 4번은 2026년 11월 14일에, 5번은 11월 15일에 이 환경에서 잰 값입니다.',
                  'Steps 1 to 4 show the baseline and optimized Gemma cold start, and step 5 shows the medians for Gemma and Qwen. Steps 1 to 4 were measured in this environment on November 14, 2026, and step 5 on November 15.',
                )}
              </p>
            )}
          </div>
        </div>
      )}

      {step == null && (
        <p className="flow__status" role="status">
          {flow
            ? PHASES[flow.phase]
            : tr(
              '요청을 보내면 그 요청이 지나가는 구간과 구간마다 걸린 시간이 이 그림에 표시됩니다.',
              'Send a request and this map shows the segments it passes through and the time spent in each.',
            )}
        </p>
      )}
    </figure>
  );
}
