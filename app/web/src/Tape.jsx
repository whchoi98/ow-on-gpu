import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { tr, useLang } from './i18n.js';

// 시간축의 축척은 모든 테이프가 같다. 그래야 기록끼리 눈금 간격을 바로 견줄 수 있다.
// 한 줄에 다 들어가지 않는 응답은 기록계의 용지처럼 다음 줄로 넘어간다.
const PX_PER_SECOND = 64;
const ROW_HEIGHT = 40;
const AXIS_HEIGHT = 18;
const ROW_PITCH = ROW_HEIGHT + AXIS_HEIGHT;
// 긴 응답은 테이프가 여러 줄이 된다. 접힌 상태에서는 이만큼만 보여 준다.
const MAX_ROWS = 4;

/**
 * 토큰 테이프. 조각이 도착한 시각마다 눈금을 찍는다.
 *   ticks      [{ms, kind}]  kind는 content 또는 reasoning
 *   pen        gemma, qwen 또는 null(아직 모름)
 *   startedAt  기록이 진행 중일 때 시작 시각(performance.now 기준). 끝났으면 null
 *   endMs      끝난 기록의 전체 시간
 *   minMs      눈금이 없어도 이 시간까지는 용지를 보여 준다
 */
export default function Tape({ ticks, pen, startedAt = null, endMs = null, minMs = 0, label }) {
  useLang();
  const box = useRef(null);
  const cursor = useRef(null);
  const firstVisible = useRef(0);
  const [rowMs, setRowMs] = useState(10000);
  const [liveRows, setLiveRows] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const live = startedAt != null;

  useLayoutEffect(() => {
    const measure = () => {
      const seconds = Math.floor(box.current.clientWidth / PX_PER_SECOND);
      setRowMs(Math.min(24, Math.max(3, seconds)) * 1000);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box.current);
    return () => observer.disconnect();
  }, []);

  // 진행 중에는 펜 위치만 프레임마다 옮기고, 줄이 넘어갈 때만 다시 그린다.
  useEffect(() => {
    if (!live) return undefined;
    let frame;
    const step = () => {
      const elapsed = performance.now() - startedAt;
      const row = Math.floor(elapsed / rowMs);
      setLiveRows((current) => (row + 1 > current ? row + 1 : current));
      if (cursor.current) {
        cursor.current.style.top = `${(row - firstVisible.current) * ROW_PITCH}px`;
        cursor.current.style.left = `${((elapsed % rowMs) / rowMs) * 100}%`;
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [live, startedAt, rowMs]);

  const lastMs = ticks.length ? ticks[ticks.length - 1].ms : 0;
  const spanMs = Math.max(endMs ?? 0, lastMs, minMs, 1);
  const rows = Math.max(Math.ceil(spanMs / rowMs), live ? liveRows : 1);
  const first = ticks.find((tick) => tick.kind === 'content') ?? ticks[0];
  const perRow = Array.from({ length: rows }, () => []);
  ticks.forEach((tick, index) => {
    const row = Math.min(rows - 1, Math.floor(tick.ms / rowMs));
    perRow[row].push({ ...tick, index });
  });
  const marks = Array.from({ length: rowMs / 1000 + 1 }, (_, index) => index * 1000);
  // 접힌 상태: 진행 중에는 펜이 있는 마지막 줄들을, 끝난 뒤에는 첫 토큰이 보이는 처음 줄들을 보여 준다.
  const folded = !expanded && rows > MAX_ROWS;
  const from = folded && live ? rows - MAX_ROWS : 0;
  const to = folded && !live ? MAX_ROWS : rows;
  firstVisible.current = from;

  return (
    <div className="tape-wrap">
    <div ref={box} className={`tape tape--${pen ?? 'idle'}`} role="img" aria-label={label}>
      {perRow.slice(from, to).map((rowTicks, shown) => {
        const row = from + shown;
        const offset = row * rowMs;
        // 첫 토큰을 기다린 구간. 여러 줄에 걸치면 줄마다 이어서 그린다.
        const wait = first ? Math.min(1, Math.max(0, (first.ms - offset) / rowMs)) : 0;
        return (
          <div key={row} className="tape__row">
            <div className="tape__paper">
              {marks.map((at) => (
                <span key={at} className="tape__grid" style={{ left: `${(at / rowMs) * 100}%` }} />
              ))}
              {wait > 0 && <span className="tape__wait" style={{ width: `${wait * 100}%` }} />}
              {rowTicks.map((tick) => (
                <span
                  key={tick.index}
                  className={`tape__tick tape__tick--${tick.kind}`}
                  style={{ left: `${((tick.ms - offset) / rowMs) * 100}%` }}
                />
              ))}
            </div>
            <div className="tape__axis" aria-hidden="true">
              {marks.map((at) => (
                <span key={at} style={{ left: `${(at / rowMs) * 100}%` }}>
                  {offset + at === 0 ? '0' : tr(`${(offset + at) / 1000}초`, `${(offset + at) / 1000}s`)}
                </span>
              ))}
            </div>
          </div>
        );
      })}
      {live && <span ref={cursor} className="tape__cursor" />}
    </div>
      {rows > MAX_ROWS && (
        <button type="button" className="link tape__more" onClick={() => setExpanded((value) => !value)}>
          {expanded
            ? tr('테이프 접기', 'Collapse tape')
            : tr(`테이프 전체 보기 (${rows}줄 중 ${MAX_ROWS}줄 표시)`, `Show full tape (${MAX_ROWS} of ${rows} rows shown)`)}
        </button>
      )}
    </div>
  );
}
