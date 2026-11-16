import { host } from './citations.js';
import { ms } from './format.js';
import { localized, tr, useLang } from './i18n.js';

const FAILURES = localized(() => ({
  sensitive_query: tr('검색어에 민감 정보가 있어 검색하지 않았습니다', 'Not searched because the query contains sensitive data'),
  empty_query: tr('검색어가 비어 있어 검색하지 않았습니다', 'Not searched because the query is empty'),
}));

// 모델이 web_search 도구를 부른 기록. 한 번에 한 줄이다.
export function Searches({ searches }) {
  useLang();
  if (!searches?.length) return null;
  return (
    <ul className="searches" aria-label={tr('웹 검색 기록', 'Web search log')}>
      {searches.map((search, index) => (
        <li key={index} className={search.error ? 'is-failed' : undefined}>
          <span className="searches__label">{tr('웹 검색', 'Web search')}</span>
          <span className="searches__query">{search.query || tr('검색어 없음', 'No query')}</span>
          <span className="searches__result">
            {search.error
              ? FAILURES[search.error] ?? tr('검색에 실패했습니다', 'Search failed')
              : tr(`결과 ${search.count}건`, `${search.count} ${search.count === 1 ? 'result' : 'results'}`) +
                (search.searchMs == null ? '' : `, ${ms(search.searchMs)}`)}
          </span>
        </li>
      ))}
    </ul>
  );
}

// 검색 결과를 쓴 답변에는 출처와 링크를 함께 보여 준다. 답변의 [n]이 이 목록의 번호다.
export default function Sources({ sources }) {
  useLang();
  if (!sources?.length) return null;
  return (
    <section className="sources" aria-label={tr('출처', 'Sources')}>
      <h3>{tr('출처', 'Sources')}</h3>
      <ol>
        {sources.map((source) => (
          <li key={source.n}>
            <span className="sources__n">[{source.n}]</span>
            {/^https?:\/\//i.test(source.url) ? (
              <a href={source.url} target="_blank" rel="noreferrer noopener">{source.title}</a>
            ) : (
              <span>{source.title}</span>
            )}
            <span className="sources__meta">{[host(source.url), source.published_at].filter(Boolean).join(', ')}</span>
          </li>
        ))}
      </ol>
      <p className="sources__note">
        {tr('Amazon Bedrock AgentCore Web Search가 찾은 페이지입니다. 답변은 모델이 이 결과를 읽고 썼습니다.',
          'Pages found by Amazon Bedrock AgentCore Web Search. The model read these results and wrote the answer.')}
      </p>
    </section>
  );
}
