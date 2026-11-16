// Cognito 로그인. 비밀번호는 브라우저에서 Cognito로 바로 가고 BFF를 거치지 않는다.
// 액세스 토큰은 탭을 닫으면 사라지는 sessionStorage에만 둔다. 비밀번호는 저장하지 않는다.
import { tr } from './i18n.js';

const KEY = 'ow-on-gpu.session';
let config = null;

async function loadConfig() {
  if (!config) {
    const response = await fetch('/config.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(tr('로그인 설정을 불러오지 못했습니다. 잠시 뒤에 다시 시도해 주세요.', 'Could not load the sign-in settings. Try again in a moment.'));
    }
    config = await response.json();
  }
  return config;
}

export async function signIn(email, password) {
  const { region, userPoolClientId } = await loadConfig();
  let response;
  try {
    response = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-amz-json-1.1',
        'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
      },
      body: JSON.stringify({
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: userPoolClientId,
        AuthParameters: { USERNAME: email, PASSWORD: password },
      }),
    });
  } catch {
    throw new Error(
      tr('로그인 서버에 연결하지 못했습니다. 네트워크를 확인하고 다시 시도해 주세요.', 'Could not reach the sign-in server. Check your network and try again.'),
    );
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.AuthenticationResult) {
    const type = String(data.__type || '');
    if (type.includes('NotAuthorizedException') || type.includes('UserNotFoundException')) {
      throw new Error(tr('이메일 또는 비밀번호가 맞지 않습니다.', 'The email or password is incorrect.'));
    }
    if (type.includes('TooManyRequestsException') || type.includes('LimitExceededException')) {
      throw new Error(tr('로그인 시도가 너무 많습니다. 잠시 뒤에 다시 시도해 주세요.', 'Too many sign-in attempts. Try again in a moment.'));
    }
    throw new Error(data.message || tr('로그인하지 못했습니다. 잠시 뒤에 다시 시도해 주세요.', 'Could not sign in. Try again in a moment.'));
  }
  return { email, token: data.AuthenticationResult.AccessToken };
}

export function loadSession() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(KEY) || 'null');
    return saved && saved.token ? saved : null;
  } catch {
    return null;
  }
}

export function saveSession(session) {
  try {
    if (session) sessionStorage.setItem(KEY, JSON.stringify(session));
    else sessionStorage.removeItem(KEY);
  } catch {
    // 저장소를 쓸 수 없으면 이 탭의 메모리에만 둔다.
  }
}
