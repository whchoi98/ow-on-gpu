import { useEffect, useState } from 'react';
import About from './About.jsx';
import ApiCall from './ApiCall.jsx';
import Chat from './Chat.jsx';
import Compare from './Compare.jsx';
import Console from './Console.jsx';
import Deploy from './Deploy.jsx';
import LangSwitch from './LangSwitch.jsx';
import Route from './Route.jsx';
import Status from './Status.jsx';
import SignIn from './SignIn.jsx';
import { loadSession, saveSession } from './auth.js';
import { tr, useLang } from './i18n.js';

const views = () => [
  { key: 'console', label: tr('요청', 'Request') },
  { key: 'chat', label: tr('대화', 'Chat') },
  { key: 'compare', label: tr('성능 평가', 'Benchmark') },
  { key: 'route', label: tr('경로 판단', 'Routing') },
  { key: 'status', label: tr('상태', 'Status') },
  { key: 'apicall', label: tr('API 호출', 'API call') },
  { key: 'about', label: tr('구조', 'Architecture') },
  { key: 'deploy', label: tr('구축 과정', 'Build steps') },
];

export default function App() {
  const lang = useLang();
  const [session, setSession] = useState(loadSession);
  // 로그인 화면에 보일 안내의 종류('expired' 또는 ''). 문구는 그릴 때 지금 언어로 고른다.
  const [notice, setNotice] = useState('');
  const [view, setView] = useState('console');

  // 화면 낭독기와 브라우저 번역이 언어를 알 수 있게 문서의 언어와 제목도 함께 바꾼다.
  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = tr('ow-on-gpu 토큰 기록계', 'ow-on-gpu token recorder');
  }, [lang]);

  function leave(reason) {
    saveSession(null);
    setNotice(reason);
    setSession(null);
  }

  if (!session) {
    return (
      <SignIn
        notice={notice}
        onSignedIn={(next) => {
          saveSession(next);
          setNotice('');
          setSession(next);
        }}
      />
    );
  }
  const expired = () => leave('expired');
  return (
    <div className="console">
      <header className="topbar">
        <span className="wordmark">ow-on-gpu</span>
        <nav className="topbar__views" aria-label={tr('화면', 'Views')}>
          {views().map((item) => (
            <button
              key={item.key}
              type="button"
              className="view"
              aria-current={view === item.key ? 'page' : undefined}
              onClick={() => setView(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <span className="topbar__user">{session.email}</span>
        <LangSwitch />
        <button id="signout" type="button" className="link" onClick={() => leave('')}>
          {tr('로그아웃', 'Sign out')}
        </button>
      </header>
      {/* 화면을 바꿔도 기록이 남도록 둘 다 띄워 두고 하나만 보인다. */}
      <div hidden={view !== 'console'}>
        <Console session={session} onExpired={expired} />
      </div>
      <div hidden={view !== 'chat'}>
        <Chat session={session} onExpired={expired} />
      </div>
      <div hidden={view !== 'compare'}>
        <Compare session={session} onExpired={expired} />
      </div>
      <div hidden={view !== 'route'}>
        <Route session={session} onExpired={expired} />
      </div>
      <div hidden={view !== 'status'}>
        <Status session={session} active={view === 'status'} onExpired={expired} />
      </div>
      <div hidden={view !== 'apicall'}>
        <ApiCall session={session} onExpired={expired} />
      </div>
      <div hidden={view !== 'about'}>
        <About />
      </div>
      <div hidden={view !== 'deploy'}>
        <Deploy />
      </div>
    </div>
  );
}
