import { setLang, useLang } from './i18n.js';

// 한영 전환. 고른 언어는 브라우저에 저장되어 다음 방문에도 유지된다. 새로 고침 없이 바뀌므로 요청 기록이 남는다.
// 이름은 그 언어로 적는다(영어 화면에서도 "한국어"로 보여야 한국어 사용자가 찾을 수 있다).
const CHOICES = [
  { lang: 'ko', label: '한국어' },
  { lang: 'en', label: 'English' },
];

export default function LangSwitch() {
  const lang = useLang();
  return (
    <div className="lang" role="group" aria-label="언어 / Language">
      {CHOICES.map((choice) => (
        <button
          key={choice.lang}
          type="button"
          className="lang__choice"
          lang={choice.lang}
          aria-pressed={lang === choice.lang}
          onClick={() => setLang(choice.lang)}
        >
          {choice.label}
        </button>
      ))}
    </div>
  );
}
