import { useEffect, useMemo, useState } from 'react';
import Tape from './Tape.jsx';
import { RECORDED } from './recorded.js';
import { ms, summarize } from './format.js';
import { localized, tr, useLang } from './i18n.js';

const LENGTH_MS = 7000;

const CHANNELS = localized(() => [
  {
    key: 'gemma',
    pen: 'gemma',
    title: tr('상담 요청', 'Support request'),
    detail: tr('Gemma 4 31B, 주문을 조회한 뒤 답변', 'Gemma 4 31B, answers after looking up the order'),
  },
  {
    key: 'qwen',
    pen: 'qwen',
    title: tr('코딩 요청', 'Coding request'),
    detail: tr('Qwen3.8-27B, 잠들어 있다가 깨어나서 답변', 'Qwen3.8-27B, answers after waking from sleep'),
  },
]);

function toTicks(record) {
  return record.events.map(([at]) => ({ ms: at, kind: 'content' }));
}

// 로그인 화면의 기록 재생. 실제 측정 기록의 도착 시각을 그대로 다시 찍는다.
export default function Replay() {
  const lang = useLang();
  const reduced = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);
  const [startedAt, setStartedAt] = useState(() => (reduced ? null : performance.now()));
  const [elapsed, setElapsed] = useState(reduced ? LENGTH_MS : 0);

  useEffect(() => {
    if (startedAt == null) return undefined;
    let frame;
    const step = () => {
      const now = performance.now() - startedAt;
      if (now >= LENGTH_MS) {
        setElapsed(LENGTH_MS);
        setStartedAt(null);
        return;
      }
      setElapsed(now);
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [startedAt]);

  return (
    <section className="replay" aria-label={tr('기록 재생', 'Record replay')}>
      <div className="replay__head">
        <h2>{tr('2026년 11월 14일의 기록', 'Records from November 14, 2026')}</h2>
        <button
          type="button"
          className="link"
          disabled={startedAt != null}
          onClick={() => {
            setElapsed(0);
            setStartedAt(performance.now());
          }}
        >
          {tr('다시 재생', 'Replay')}
        </button>
      </div>
      {CHANNELS.map((channel) => {
        const record = RECORDED[channel.key];
        const all = toTicks(record);
        const shown = all.filter((tick) => tick.ms <= elapsed);
        const summary = summarize(all);
        return (
          <div key={channel.key} className="replay__channel">
            <div className="replay__label">
              <span className={`pen pen--${channel.pen}`} aria-hidden="true" />
              <div>
                <strong>{channel.title}</strong>
                <span>{channel.detail}</span>
              </div>
              <span className="replay__readout">
                {tr(`첫 토큰 ${ms(summary.firstMs)}, 간격 ${ms(summary.gapMs)}`, `First token ${ms(summary.firstMs)}, interval ${ms(summary.gapMs)}`)}
              </span>
            </div>
            <Tape
              ticks={shown}
              pen={channel.pen}
              startedAt={startedAt}
              minMs={LENGTH_MS}
              label={tr(`${channel.title}: 첫 토큰 ${ms(summary.firstMs)}, 조각 ${summary.count}개, 간격 중앙값 ${ms(summary.gapMs)}`,
                `${channel.title}: first token ${ms(summary.firstMs)}, ${summary.count} chunks, median interval ${ms(summary.gapMs)}`)}
            />
          </div>
        );
      })}
      <p className="replay__note">
        {tr('세로 눈금 하나가 응답 조각 하나입니다. 응답이 중간에서 모였다가 나오면 눈금이 한곳에 뭉칩니다.',
          'Each vertical tick is one response chunk. If the response is buffered on the way and released at once, the ticks bunch up in one place.')}
        {/* 재생하는 기록은 한국어 질문으로 받은 것이다(recorded.js). 영어 화면에서만 알린다. */}
        {lang === 'en' && ' Recorded on 2026-11-14 with Korean prompts.'}
      </p>
    </section>
  );
}
