import { useEffect, useRef, useState } from 'react';
import { koreanShare } from './format.js';
import { tr, useLang } from './i18n.js';

// 추론 과정. Qwen은 BFF의 지시문을 따라 한국어로 추론하지만 Gemma는 영어로만 추론한다(2026-11-14 확인).
// 영어로 나온 추론은 펼칠 때 Gemma에게 한국어로 옮기게 해서 보여 주고, 원문은 그 아래에 둔다.
// 영어 화면에서는 옮기지 않고 원문을 그대로 보여 준다.
export default function Reasoning({ text, live, onTranslate }) {
  const lang = useLang();
  // 한국어로 쓴 추론에도 코드와 영어 용어가 섞인다(잰 값 0.5에서 0.96). 영어로 쓴 추론은 0.12 이하였다.
  const korean = koreanShare(text) >= 0.3;
  const asIs = korean || lang === 'en';
  const box = useRef(null);
  const [translation, setTranslation] = useState({ status: 'idle', text: '' });

  async function translate() {
    if (asIs || live || translation.status !== 'idle') return;
    setTranslation({ status: 'running', text: '' });
    try {
      await onTranslate(text, (piece) => setTranslation((current) => ({ ...current, text: current.text + piece })));
      setTranslation((current) => ({ ...current, status: 'done' }));
    } catch {
      setTranslation({ status: 'failed', text: '' });
    }
  }

  // 답변이 나오는 동안 펼쳐 둔 경우에는 답변이 끝난 뒤에 옮기기 시작한다.
  // 영어 화면에서 펼쳐 둔 채 한국어로 바꾼 경우에도 여기서 옮기기 시작한다.
  useEffect(() => {
    if (!live && box.current?.open) translate();
  }, [live, lang]);

  return (
    <details ref={box} className="record__reasoning" onToggle={(event) => event.currentTarget.open && translate()}>
      <summary>{tr('추론 과정 보기', 'Show reasoning')}</summary>
      {asIs ? (
        <p>{text}</p>
      ) : (
        // 이 갈래는 한국어 화면에서만 그려지므로 문구를 한국어로만 둔다.
        <>
          <p className="record__note">이 모델은 추론을 영어로 씁니다. 아래는 Gemma가 한국어로 옮긴 글입니다.</p>
          {translation.status === 'failed' ? (
            <p>한국어로 옮기지 못했습니다. 아래 원문을 확인해 주세요.</p>
          ) : (
            <p>{translation.text || (live ? '답변이 끝나면 한국어로 옮깁니다.' : '한국어로 옮기는 중입니다.')}</p>
          )}
          <details>
            <summary>영어 원문 보기</summary>
            <p>{text}</p>
          </details>
        </>
      )}
    </details>
  );
}
