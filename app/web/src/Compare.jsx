import { useState } from 'react';
import Tape from './Tape.jsx';
import { ChatError, streamChat } from './stream.js';
import { MODELS, aggregate, analyze, measure, ms, seconds } from './format.js';
import { localized, tr, useLang } from './i18n.js';

const SIDES = [
  { key: 'gemma', name: 'Gemma 4 31B', pen: 'gemma' },
  { key: 'qwen', name: 'Qwen3.8-27B', pen: 'qwen' },
];

const PRESETS = localized(() => [
  {
    label: tr('짧은 답', 'Short answer'),
    prompt: tr(
      '대한민국의 수도와 그 도시의 인구를 한 문장으로 알려 주세요.',
      'Tell me the capital of South Korea and the population of that city in one sentence.',
    ),
  },
  {
    label: tr('설명', 'Explanation'),
    prompt: tr('HTTP와 HTTPS의 차이를 다섯 문장으로 설명해 주세요.', 'Explain the difference between HTTP and HTTPS in five sentences.'),
  },
  {
    label: tr('코드', 'Code'),
    prompt: tr(
      '파이썬으로 이진 탐색 함수를 작성하고 시간 복잡도를 설명해 주세요.',
      'Write a binary search function in Python and explain its time complexity.',
    ),
  },
  {
    label: tr('요약', 'Summary'),
    prompt: tr(
      '다음 글을 세 문장으로 요약해 주세요.\n\n쿠버네티스에서 대형 언어 모델을 서빙할 때 시작 시간은 노드 프로비저닝, 이미지 내려받기, 가중치 로드, 엔진 초기화로 나뉩니다. 노드와 이미지는 같은 노드에서 파드만 다시 만들면 사라지지만, 가중치 로드와 엔진 초기화는 매번 반복됩니다. 그래서 가중치를 객체 저장소에서 바로 스트리밍하고 컴파일 결과를 노드에 남겨 두는 방법이 효과가 큽니다.',
      'Summarize the following text in three sentences.\n\nWhen you serve a large language model on Kubernetes, startup time breaks down into node provisioning, image pull, weight load, and engine init. Node provisioning and the image pull go away when only the pod is recreated on the same node, but the weight load and engine init repeat every time. That is why streaming the weights straight from object storage and keeping the compiled results on the node help the most.',
    ),
  },
]);

const number = (value, digits = 1) => (value == null ? '-' : value.toFixed(digits));

const perSecond = (value) => tr(`초당 ${number(value)}토큰`, `${number(value)} tokens/s`);

const ROWS = localized(() => [
  [
    tr('보낸 요청', 'Requests sent'),
    (a) => (a.failed ? tr(`${a.sent}건 중 ${a.failed}건 실패`, `${a.failed} of ${a.sent} failed`) : tr(`${a.sent}건`, `${a.sent}`)),
  ],
  [tr('첫 토큰 (중앙값)', 'First token (median)'), (a) => ms(a.firstMedian)],
  [tr('첫 토큰 (가장 느린 요청)', 'First token (slowest)'), (a) => ms(a.firstMax)],
  [tr('Chunk 간격 (중앙값)', 'Chunk interval (median)'), (a) => ms(a.gapMedian)],
  [tr('Chunk 간격 (95%)', 'Chunk interval (p95)'), (a) => ms(a.gapP95)],
  [tr('요청 하나의 생성 속도', 'Single-request speed'), (a) => (a.tokensPerSecond == null ? '-' : perSecond(a.tokensPerSecond))],
  [tr('모델 전체 처리량', 'Total throughput per model'), (a) => (a.throughput == null ? '-' : perSecond(a.throughput))],
  [tr('출력 토큰 (중앙값)', 'Output tokens (median)'), (a) => (a.tokens == null ? '-' : tr(`${Math.round(a.tokens)}개`, `${Math.round(a.tokens)}`))],
  [tr('전체 시간 (중앙값)', 'Total time (median)'), (a) => seconds(a.totalMedian)],
]);

function explain(error) {
  if (!(error instanceof ChatError)) return tr('응답을 처리하지 못했습니다.', 'Could not process the response.');
  if (error.status === 403) {
    return tr(
      '요청이 많아 이 네트워크가 잠시 차단되었습니다. 5분쯤 뒤에 다시 실행해 주세요.',
      'Too many requests, so this network is blocked for a while. Run it again in about 5 minutes.',
    );
  }
  if (error.status === 0) return error.message;
  const responded = tr(`서버가 ${error.status}로 응답했습니다.`, `The server responded with ${error.status}.`);
  return error.message ? `${responded} ${error.message}` : responded;
}

// 같은 내용을 두 모델에 보내 첫 토큰까지의 시간과 생성 속도를 견준다.
export default function Compare({ session, onExpired }) {
  useLang();
  // 예시를 고른 채로 두면 지금 언어의 예시가 나가고, 직접 고친 글은 언어를 바꿔도 그대로 둔다.
  const [draft, setDraft] = useState({ preset: 1 });
  const prompt = draft.text ?? PRESETS[draft.preset].prompt;
  const [maxTokens, setMaxTokens] = useState(256);
  const [concurrency, setConcurrency] = useState(1);
  const [rounds, setRounds] = useState(3);
  const [busy, setBusy] = useState(false);
  // 진행 상황과 실패는 문구 대신 값으로 두고, 그릴 때 지금 언어의 문구로 바꾼다.
  const [progress, setProgress] = useState(null);  // {round, rounds}
  const [notice, setNotice] = useState(null);      // 실패한 요청의 결과
  const [results, setResults] = useState({ gemma: [], qwen: [] });
  const [roundTimes, setRoundTimes] = useState({ gemma: [], qwen: [] });
  const [live, setLive] = useState({ gemma: null, qwen: null });
  const [ran, setRan] = useState({ concurrency: 1, rounds: 1 });

  async function one(side, round, index) {
    const ticks = [];
    const startedAt = performance.now();
    const show = index === 0;  // 모델마다 첫 요청 하나만 테이프에 그린다
    if (show) setLive((current) => ({ ...current, [side]: { ticks: [], startedAt, endMs: null } }));
    let info = null;
    try {
      const { totalMs, usage } = await streamChat({
        token: session.token,
        prompt: prompt.trim(),
        evalModel: side,
        maxTokens,
        onHeaders: (headers) => {
          info = headers;
        },
        onChunk: (chunk) => {
          ticks.push({ ms: chunk.ms, kind: chunk.kind });
          if (show) setLive((current) => ({ ...current, [side]: { ...current[side], ticks: [...ticks] } }));
        },
      });
      if (show) setLive((current) => ({ ...current, [side]: { ticks, startedAt: null, endMs: totalMs } }));
      // 민감 정보 규칙에 걸리면 BFF가 Qwen 대신 Gemma로 보낸다. 그 결과는 견줄 수 없다.
      if (MODELS[info?.model]?.pen !== side) {
        return {
          round,
          index,
          gaps: [],
          error: tr('민감 정보 형식이 있어 요청한 모델로 보내지 않았습니다.', 'The request contains a sensitive data pattern, so it was not sent to the requested model.'),
          policy: true,
        };
      }
      return { round, index, ...measure(ticks, totalMs, usage) };
    } catch (error) {
      if (show) setLive((current) => ({ ...current, [side]: { ticks, startedAt: null, endMs: performance.now() - startedAt } }));
      if (error instanceof ChatError && error.status === 401) throw error;
      return { round, index, gaps: [], error: explain(error), cause: error };
    }
  }

  async function run(event) {
    event.preventDefault();
    if (!prompt.trim() || busy) return;
    setBusy(true);
    setRan({ concurrency, rounds });
    setNotice(null);
    setResults({ gemma: [], qwen: [] });
    setRoundTimes({ gemma: [], qwen: [] });
    try {
      for (let round = 0; round < rounds; round += 1) {
        setProgress({ round: round + 1, rounds });
        // 두 모델에 함께 보내되, 걸린 시간은 모델마다 따로 잰다. 먼저 끝난 모델의 처리량이 낮게 나오지 않게 하기 위해서다.
        const timed = async (side) => {
          const started = performance.now();
          const items = await Promise.all(Array.from({ length: concurrency }, (_, index) => one(side.key, round, index)));
          return { items, wallMs: performance.now() - started };
        };
        const [gemma, qwen] = await Promise.all(SIDES.map(timed));
        setRoundTimes((current) => ({
          gemma: [...current.gemma, { index: round, wallMs: gemma.wallMs }],
          qwen: [...current.qwen, { index: round, wallMs: qwen.wallMs }],
        }));
        setResults((current) => ({ gemma: [...current.gemma, ...gemma.items], qwen: [...current.qwen, ...qwen.items] }));
        const failed = [...gemma.items, ...qwen.items].find((result) => result.error);
        if (failed) {
          setNotice(failed);
          if (failed.policy) break;
        }
      }
    } catch {
      onExpired();
      return;
    } finally {
      setBusy(false);
      setProgress(null);
    }
  }

  const summary = { gemma: aggregate(results.gemma, roundTimes.gemma), qwen: aggregate(results.qwen, roundTimes.qwen) };
  const measured = results.gemma.length + results.qwen.length > 0;
  // 측정이 끝난 뒤에만 분석을 보여 준다. 설정은 측정을 시작할 때의 값으로 고정해 둔다.
  const analysis = !busy && measured ? analyze(summary, ran) : [];

  return (
    <div className="console__body">
      <form className="composer" onSubmit={run} aria-labelledby="compare-title">
        <h2 id="compare-title">{tr('성능 평가', 'Benchmark')}</h2>
        <p className="form-note composer__intro">
          {tr(
            '같은 내용을 Gemma와 Qwen에 함께 보내 첫 토큰까지의 시간과 생성 속도를 견줍니다. 두 모델 모두 thinking을 끄고 같은 우선순위로 보냅니다.',
            'Sends the same prompt to Gemma and Qwen at the same time and compares the time to first token and the generation speed. Both models run with thinking off and at the same priority.',
          )}
        </p>

        <label className="field">
          <span>{tr('내용', 'Prompt')}</span>
          <textarea id="compare-prompt" value={prompt} rows={5} onChange={(event) => setDraft({ text: event.target.value })} />
        </label>

        <div className="examples composer__side">
          <div className="examples__group">
            <span>{tr('예시', 'Examples')}</span>
            {PRESETS.map((preset, index) => (
              <button key={preset.label} type="button" className="chip chip--button" onClick={() => setDraft({ preset: index })}>
                {preset.label}
              </button>
            ))}
          </div>

        <div className="settings">
          <label className="field">
            <span>{tr('최대 출력 토큰', 'Max tokens')}</span>
            <select value={maxTokens} onChange={(event) => setMaxTokens(Number(event.target.value))}>
              {[64, 128, 256, 512, 1024].map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{tr('동시 요청 수', 'Concurrency')}</span>
            <select id="compare-concurrency" value={concurrency} onChange={(event) => setConcurrency(Number(event.target.value))}>
              {[1, 2, 4, 8].map((value) => (
                <option key={value} value={value}>{tr(`모델마다 ${value}개`, `${value} per model`)}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{tr('반복', 'Rounds')}</span>
            <select id="compare-rounds" value={rounds} onChange={(event) => setRounds(Number(event.target.value))}>
              {[1, 3, 5].map((value) => (
                <option key={value} value={value}>{tr(`${value}회`, `${value}`)}</option>
              ))}
            </select>
          </label>
        </div>
        </div>

        <div className="composer__send">
          <button id="compare-run" className="button button--primary" type="submit" disabled={busy || !prompt.trim()}>
            {busy ? tr('측정하는 중', 'Measuring') : tr('측정 시작', 'Start measuring')}
          </button>
          <p className="form-note" role="status">
            {progress
              ? tr(`${progress.rounds}회 중 ${progress.round}회째를 보내는 중입니다.`, `Sending round ${progress.round} of ${progress.rounds}.`)
              : tr(
                  `요청 ${2 * concurrency * rounds}건을 보냅니다. 5분 안에 300건을 넘기면 잠시 차단됩니다.`,
                  `Sends ${2 * concurrency * rounds} requests. Over 300 in 5 minutes gets you blocked for a while.`,
                )}
          </p>
        </div>
      </form>

      <section className="records" aria-label={tr('성능 평가 결과', 'Benchmark results')}>
        {!measured && !busy ? (
          <div className="records__empty">
            <h2>{tr('아직 측정하지 않았습니다', 'Nothing measured yet')}</h2>
            <p>
              {tr(
                '측정을 시작하면 두 모델의 응답 Chunk가 같은 축척의 테이프에 찍히고, 반복한 요청의 값이 표로 정리됩니다. 눈금이 촘촘할수록 생성이 빠른 모델입니다.',
                'Once you start measuring, the response chunks from both models are marked on tapes drawn to the same scale, and the values from the repeated requests are summarized in a table. The denser the ticks, the faster the model generates.',
              )}
            </p>
          </div>
        ) : (
          <article className="record">
            <header className="record__head">
              <span className="record__number">{tr('테이프', 'Tape')}</span>
              <span className="record__decision">{tr('모델마다 가장 최근 회차의 첫 요청입니다', 'First request of the latest round for each model')}</span>
            </header>
            {SIDES.map((side) => (
              <div key={side.key} className="compare__tape">
                <div className="compare__label">
                  <span className={`pen pen--${side.pen}`} aria-hidden="true" />
                  <strong>{side.name}</strong>
                </div>
                <Tape
                  ticks={live[side.key]?.ticks ?? []}
                  pen={side.pen}
                  startedAt={live[side.key]?.startedAt ?? null}
                  endMs={live[side.key]?.endMs ?? null}
                  label={tr(`${side.name}의 토큰 테이프`, `Token tape for ${side.name}`)}
                />
              </div>
            ))}

            {notice && (
              <p className="record__error" role="alert">
                {notice.policy
                  ? tr(
                      '이 내용에는 민감 정보 형식이 있어 Qwen으로 보낼 수 없습니다. 내용을 바꿔 다시 실행해 주세요.',
                      'This prompt contains a sensitive data pattern, so it cannot be sent to Qwen. Change the prompt and run it again.',
                    )
                  : explain(notice.cause)}
              </p>
            )}

            <div className="table-scroll">
              <table className="compare__table">
                <thead>
                  <tr>
                    <th scope="col">{tr('항목', 'Metric')}</th>
                    {SIDES.map((side) => (
                      <th key={side.key} scope="col">
                        <span className={`pen pen--${side.pen}`} aria-hidden="true" /> {side.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {ROWS.map(([label, value]) => (
                    <tr key={label}>
                      <th scope="row">{label}</th>
                      {SIDES.map((side) => (
                        <td key={side.key}>{summary[side.key].sent ? value(summary[side.key]) : '-'}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {analysis.length > 0 && (
              <section className="analysis" aria-labelledby="analysis-title">
                <h3 id="analysis-title">{tr('결과 분석', 'Analysis')}</h3>
                <ul>
                  {analysis.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </section>
            )}
            <p className="record__cut">
              {tr(
                '생성 속도는 첫 토큰이 나온 뒤부터 잰 값이고, 모델 전체 처리량은 한 회차에 그 모델이 낸 토큰을 그 모델의 요청이 모두 끝날 때까지의 시간으로 나눈 값입니다. 이 화면에서 보낸 요청만으로 잰 값이어서, 다른 사람이 함께 쓰고 있으면 느리게 나옵니다.',
                'Generation speed is measured from the first token on. Total throughput per model is the tokens the model produced in a round divided by the time until all of its requests finished. These values come only from the requests sent from this screen, so they are lower while other people are using the models.',
              )}
            </p>
          </article>
        )}
      </section>
    </div>
  );
}
