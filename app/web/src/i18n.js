// 화면 언어(한국어, 영어). 문구는 쓰는 자리에 한 쌍으로 적는다: tr('요청', 'Request').
//
// 새로 고침 없이 바꾼다. 요청 기록과 측정 결과가 화면에 남아 있어야 하기 때문이다.
//   컴포넌트       useLang()을 불러 언어가 바뀌면 다시 그리게 한다
//   모듈 상수      localized(() => [...])로 감싼다. 불러올 때 한 번 계산하는 값이라 그대로 두면 처음 언어에 묶인다
//   함수 안의 문구  tr()만 쓰면 된다. 부를 때마다 지금 언어로 고른다
import { useSyncExternalStore } from 'react';

const KEY = 'ow-on-gpu.lang';
const LANGS = ['ko', 'en'];
const listeners = new Set();

function saved() {
  try {
    const value = globalThis.localStorage?.getItem(KEY);
    return LANGS.includes(value) ? value : 'ko';
  } catch {
    return 'ko'; // 저장소를 못 쓰는 창(사생활 보호 모드 등)과 node 시험
  }
}

let current = saved();

export const getLang = () => current;

export function setLang(next) {
  if (!LANGS.includes(next) || next === current) return;
  current = next;
  try {
    globalThis.localStorage?.setItem(KEY, next);
  } catch {
    // 저장하지 못해도 이번 방문에서는 바뀐다
  }
  listeners.forEach((listener) => listener());
}

function subscribe(listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export const useLang = () => useSyncExternalStore(subscribe, getLang, getLang);

// 한 쌍에서 지금 언어의 문구를 고른다.
export const tr = (ko, en) => (current === 'en' ? en : ko);

// 숫자와 시각의 표기에 쓰는 로캘
export const locale = () => (current === 'en' ? 'en-US' : 'ko-KR');

// 문구가 든 모듈 상수를 언어마다 한 번씩 만들어 두고, 읽을 때마다 지금 언어의 것을 내준다.
// 대리 객체라서 STAGES.map(...), STAGES[2].title, Object.keys(SIDES)처럼 쓰던 코드를 그대로 둘 수 있다.
// build는 두 언어에서 모양(키, 길이)이 같은 값을 돌려줘야 한다.
export function localized(build) {
  const made = {};
  const value = () => (made[current] ??= build());
  return new Proxy(value(), {
    get: (_, key) => Reflect.get(value(), key),
    has: (_, key) => Reflect.has(value(), key),
    ownKeys: () => Reflect.ownKeys(value()),
    getOwnPropertyDescriptor: (_, key) => Reflect.getOwnPropertyDescriptor(value(), key),
  });
}
