import { useState } from 'react';
import LangSwitch from './LangSwitch.jsx';
import Replay from './Replay.jsx';
import { signIn } from './auth.js';
import { tr, useLang } from './i18n.js';

// notice: 로그인 화면에 처음 보일 안내의 종류('expired'면 로그인 만료). 로그인을 시도하면 지운다.
export default function SignIn({ notice, onSignedIn }) {
  useLang();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [tried, setTried] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setTried(true);
    setError('');
    try {
      const session = await signIn(email.trim(), password);
      setPassword('');
      onSignedIn(session);
    } catch (failure) {
      setError(failure.message);
      setBusy(false);
    }
  }

  const expired = !tried && notice === 'expired'
    ? tr('로그인이 만료되었습니다. 다시 로그인해 주세요.', 'Your sign-in expired. Sign in again.')
    : '';

  return (
    <div className="signin">
      <header className="signin__brand">
        <span className="wordmark">ow-on-gpu</span>
        <span className="tagline">
          {tr('EKS 위의 Gemma 4 31B와 Qwen3.8-27B', 'Gemma 4 31B and Qwen3.8-27B on Amazon EKS')}
        </span>
        <LangSwitch />
      </header>

      <main className="signin__main">
        <div className="signin__story">
          <h1>{tr('토큰이 도착하는 순간을 기록합니다', 'We record the moment each token arrives')}</h1>
          <p className="lede">
            {tr(
              '요청은 CloudFront, 내부 ALB, BFF, 게이트웨이를 거쳐 두 모델 중 하나로 갑니다. 어느 모델이 답했는지와 응답 조각이 도착한 시각을 그대로 보여 줍니다.',
              'A request goes through CloudFront, the internal ALB, the BFF, and the gateway to one of two models. This page shows which model answered and when each response chunk arrived, as recorded.',
            )}
          </p>
          <Replay />
        </div>

        <form className="signin__form" onSubmit={submit} aria-labelledby="signin-title">
          <h2 id="signin-title">{tr('로그인', 'Sign in')}</h2>
          <label className="field">
            <span>{tr('이메일', 'Email')}</span>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
              autoFocus
            />
          </label>
          <label className="field">
            <span>{tr('비밀번호', 'Password')}</span>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <p id="login-error" className="form-error" role="alert">
            {error || expired}
          </p>
          <button id="signin" className="button button--primary" type="submit" disabled={busy}>
            {busy ? tr('확인하는 중', 'Checking') : tr('로그인', 'Sign in')}
          </button>
          <p className="form-note">
            {tr('등록된 계정만 쓸 수 있습니다. 가입은 받지 않습니다.', 'Only registered accounts can sign in. Sign-up is closed.')}
          </p>
        </form>
      </main>
    </div>
  );
}
