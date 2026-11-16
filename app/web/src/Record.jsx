import { memo } from 'react';
import Markdown from 'react-markdown';
import remarkCjkFriendly from 'remark-cjk-friendly';
import remarkCjkFriendlyGfmStrikethrough from 'remark-cjk-friendly-gfm-strikethrough';
import remarkGfm from 'remark-gfm';
import Reasoning from './Reasoning.jsx';
import Sources, { Searches } from './Sources.jsx';
import Tape from './Tape.jsx';
import { linkCitations } from './citations.js';
import { DECISIONS, MODELS, SEARCH_OFF, TASKS, explain, ms, seconds, summarize } from './format.js';
import { locale, tr, useLang } from './i18n.js';
import { ChatError, MAX_TOKENS, noResponse } from './stream.js';

// remark-cjk-friendly: 굵게 표시할 구간이 괄호나 따옴표로 끝나고 바로 조사가 붙어도 강조로 처리한다.
// CommonMark 규칙만으로는 `**형식(정규표현식)**과` 같은 문장의 `**`가 글자 그대로 남는다.
// 취소선(~~)도 같은 규칙을 쓰므로 함께 넣는다. 두 플러그인은 remark-gfm 뒤에 와야 한다.
const plugins = [remarkGfm, remarkCjkFriendly, remarkCjkFriendlyGfmStrikethrough];
const components = {
  // 모델이 쓴 링크는 새 탭에서 연다.
  a: ({ node, ...props }) => <a {...props} target="_blank" rel="noreferrer noopener" />,
  // 넓은 표는 표만 가로로 스크롤한다.
  table: ({ node, ...props }) => (
    <div className="table-scroll">
      <table {...props} />
    </div>
  ),
};

// 실패한 요청의 설명. 기록에는 오류를 그대로 두고 그릴 때 문구로 바꾼다. 그래야 언어를 바꾸면 지난 기록도 따라 바뀐다.
// 서버가 보낸 문구(error.message)는 받은 그대로 보여 준다.
function failure(error) {
  if (!(error instanceof ChatError)) return tr('응답을 처리하지 못했습니다. 다시 보내 주세요.', 'The response could not be processed. Please send again.');
  if (error.status === 403) {
    return tr('요청이 많아 이 네트워크가 잠시 차단되었습니다. 5분쯤 뒤에 다시 보내 주세요.',
      'This network is blocked for a while because of too many requests. Please send again in about 5 minutes.');
  }
  if (error.status === 422 || error.status === 400) return error.message || tr('보낼 수 없는 요청입니다.', 'This request cannot be sent.');
  if (error.status === 503) return tr('모델이 아직 준비되지 않았습니다. 잠시 뒤에 다시 보내 주세요.', 'The model is not ready yet. Please send again shortly.');
  if (error.status === 0) return noResponse();
  return error.message
    ? tr(`서버가 ${error.status}로 응답했습니다. ${error.message}`, `The server responded with ${error.status}. ${error.message}`)
    : tr(`서버가 ${error.status}로 응답했습니다.`, `The server responded with ${error.status}.`);
}

// 영어 문장에 쓰는 조각 수
const chunks = (count) => `${count} ${count === 1 ? 'chunk' : 'chunks'}`;

function Readout({ label, value }) {
  return (
    <div className="readout">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function Record({ record, folded, focused, onFold, onShowPath, onTranslate }) {
  useLang();
  const model = MODELS[record.model];
  const pen = model?.pen ?? null;
  const task = TASKS.find((item) => item.value === record.task);
  const summary = summarize(record.ticks);
  const live = record.state === 'streaming';
  const waiting = live && record.ticks.length === 0;
  const reasons = explain(record.decision, record.reason);
  const error = record.error ? failure(record.error) : null;

  return (
    <article className={`record record--${pen ?? 'idle'} ${folded ? 'is-folded' : ''}`} aria-busy={live}>
      <header className="record__head">
        <span className="record__number">{tr(`기록 ${record.number}`, `Record ${record.number}`)}</span>
        <span className="record__task">{task?.label ?? tr('자동', 'Auto')}</span>
        {model ? (
          <span className="chip chip--model">
            <span className={`pen pen--${pen}`} aria-hidden="true" />
            {model.name}
          </span>
        ) : (
          live && <span className="chip chip--pending">{tr('모델을 정하는 중', 'Choosing a model')}</span>
        )}
        {record.decision && <span className="record__decision">{DECISIONS[record.decision] ?? record.decision}</span>}
        {record.sensitive && <span className="chip chip--flag">{tr('민감 정보', 'Sensitive data')}</span>}
        {record.search === 'on' && <span className="chip">{tr('웹 검색 켬', 'Web search on')}</span>}
        <span className="record__actions">
          <button type="button" className="link" aria-pressed={focused} onClick={() => onShowPath(record.id)}>
            {focused ? tr('경로 표시 중', 'Showing path') : tr('경로 보기', 'Show path')}
          </button>
          <button type="button" className="link" aria-expanded={!folded} onClick={() => onFold(record.id)}>
            {folded ? tr('펼치기', 'Expand') : tr('접기', 'Collapse')}
          </button>
        </span>
      </header>

      <p className="record__prompt">{record.prompt}</p>

      {folded && (
        <p className="record__brief">
          {error ||
            tr(`첫 토큰 ${ms(summary.firstMs)}, 조각 ${summary.count}개, 전체 ${seconds(record.totalMs)}`,
              `First token ${ms(summary.firstMs)}, ${chunks(summary.count)}, total ${seconds(record.totalMs)}`)}
        </p>
      )}
      {!folded && (
        <>

      {reasons.length > 0 && (
        <div className="record__reason">
          <h3>{tr('결정 이유', 'Decision reason')}</h3>
          <ul>
            {reasons.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        </div>
      )}

      <Tape
        ticks={record.ticks}
        pen={pen}
        startedAt={live ? record.startedAt : null}
        endMs={record.totalMs}
        label={tr(`기록 ${record.number}의 토큰 테이프: 첫 토큰 ${ms(summary.firstMs)}, 조각 ${summary.count}개`,
          `Token tape for record ${record.number}: first token ${ms(summary.firstMs)}, ${chunks(summary.count)}`)}
      />

      <dl className="readouts">
        <Readout label={tr('응답 헤더', 'Headers')} value={ms(record.headersMs)} />
        {summary.reasoningCount > 0 && <Readout label={tr('추론 시작', 'Reasoning start')} value={ms(summary.reasoningMs)} />}
        <Readout
          label={summary.reasoningCount > 0 ? tr('답변의 첫 토큰', 'Answer start') : tr('첫 토큰', 'First token')}
          value={ms(summary.firstMs)}
        />
        <Readout label={tr('조각 간격', 'Chunk interval')} value={ms(summary.gapMs)} />
        <Readout label={tr('조각 수', 'Chunks')} value={summary.count ? tr(`${summary.count}개`, `${summary.count}`) : '-'} />
        <Readout label={tr('전체', 'Total')} value={seconds(record.totalMs)} />
      </dl>

      {record.reasoning && <Reasoning text={record.reasoning} live={live} onTranslate={onTranslate} />}

      {record.asked && SEARCH_OFF[record.search] && <p className="record__cut">{SEARCH_OFF[record.search]}</p>}
      <Searches searches={record.searches} />

      {error ? (
        <p className="record__error" role="alert">
          {error}
        </p>
      ) : (
        <div className="answer">
          {record.text ? (
            <Markdown remarkPlugins={plugins} components={components}>
              {linkCitations(record.text, record.sources)}
            </Markdown>
          ) : (
            <p className="answer__waiting">
              {waiting
                ? tr('첫 토큰을 기다리는 중입니다.', 'Waiting for the first token.')
                : live && record.searches?.length
                  ? tr('검색 결과를 읽고 답변을 쓰는 중입니다.', 'Reading the search results and writing the answer.')
                  : ''}
            </p>
          )}
        </div>
      )}

      {!error && <Sources sources={record.sources} />}

      {record.finishReason === 'length' && (
        <p className="record__cut">
          {tr(`최대 길이(${MAX_TOKENS.toLocaleString(locale())} 토큰)에 닿아 답변이 여기서 끊겼습니다.`,
            `The answer was cut off here because it reached the maximum length (${MAX_TOKENS.toLocaleString(locale())} tokens).`)}
        </p>
      )}

      {record.requestId && <p className="record__id">{tr(`요청 ID ${record.requestId}`, `Request ID ${record.requestId}`)}</p>}
        </>
      )}
    </article>
  );
}

export default memo(Record);
