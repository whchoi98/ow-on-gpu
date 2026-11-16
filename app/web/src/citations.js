// 웹 검색 출처를 다루는 순수 함수. 화면과 무관하다.
//
// BFF는 모델이 web_search 도구를 부를 때마다 SSE 주석 줄로 검색어와 출처 목록을 알려 준다(app/bff/websearch.py).
// 모델은 답변에 [1], [2] 같은 번호를 붙인다. 여기서는 그 번호를 출처 링크로 바꾼다.

// 도구 호출 알림을 기록에 더한다. 같은 주소는 BFF가 같은 번호로 보내므로 번호로 합친다.
export function addSearch(state, note) {
  const searches = [...(state.searches ?? []),
    { query: note.query ?? '', searchMs: note.search_ms ?? null, count: note.sources?.length ?? 0, error: note.error ?? null }];
  const sources = [...(state.sources ?? [])];
  for (const source of note.sources ?? []) {
    if (!sources.some((item) => item.n === source.n)) sources.push(source);
  }
  sources.sort((a, b) => a.n - b.n);
  return { searches, sources };
}

// 주소의 호스트 이름. 출처 목록에 제목과 함께 보여 준다.
export function host(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return '';
  }
}

// 답변의 [1], [1, 2], [1][2]를 출처 링크로 바꾼 Markdown을 돌려준다.
// 출처 목록에 없는 번호와 코드(``` 블록, `인라인`) 안의 대괄호는 그대로 둔다.
export function linkCitations(text, sources) {
  if (!text || !sources?.length) return text;
  const byNumber = new Map(sources.map((source) => [source.n, source]));
  const link = (number) => {
    const source = byNumber.get(Number(number));
    // 주소를 <>로 감싸면 괄호가 들어 있어도 링크가 끊기지 않는다.
    return source && /^https?:\/\/[^\s<>]+$/i.test(source.url) ? `[\\[${number}\\]](<${source.url}>)` : `[${number}]`;
  };
  return text
    .split(/(```[\s\S]*?(?:```|$)|`[^`\n]*`)/)
    .map((part, index) =>
      index % 2 === 1
        ? part
        : part.replace(/\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?!\()/g, (match, numbers) => {
            const list = numbers.split(',').map((value) => value.trim());
            return list.some((value) => byNumber.has(Number(value))) ? list.map(link).join('') : match;
          }),
    )
    .join('');
}
