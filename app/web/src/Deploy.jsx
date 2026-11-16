import { useRef } from 'react';
import figure from './assets/build-steps.png';
import figureEn from './assets/build-steps.en.png';
import { DEPLOY } from './deploy-steps.js';
import { tr, useLang } from './i18n.js';
import './deploy.css';

// 구축 과정. 이 환경을 만든 열 단계와 측정에서 확인한 주요 내용을 차례로 보여 준다. 내용은 deploy-steps.js에 있다.
// 그림(build-steps.png)은 구조도의 구성 요소마다 그것을 만든 단계의 번호를 붙인 인포그래픽이고(docs/infographic/build_steps.py),
// 번호는 아래 단계 목록의 번호와 같다.
export default function Deploy() {
  const lang = useLang();
  const list = useRef(null);

  // 위의 번호 줄에서 고른 단계로 옮긴다. 읽는 위치도 함께 옮겨지도록 그 단계에 초점을 준다.
  function jump(n) {
    const target = list.current?.querySelector(`#deploy-step-${n}`);
    if (!target) return;
    const still = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({ behavior: still ? 'auto' : 'smooth', block: 'start' });
    target.focus({ preventScroll: true });
  }

  return (
    <div className="console__body">
      <section className="panel" aria-labelledby="deploy-title">
        <header className="panel__head">
          <h2 id="deploy-title">{tr('구축 과정', 'Build steps')}</h2>
          <p className="form-note">{DEPLOY.lede}</p>
        </header>
        <dl className="deploy__facts">
          {DEPLOY.facts.map(([name, value]) => (
            <div key={name}>
              <dt>{name}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="panel" aria-labelledby="deploy-map-title">
        <header className="panel__head">
          <h2 id="deploy-map-title">{tr('아키텍처에서 보는 구축 단계', 'Build steps on the architecture')}</h2>
          <p className="form-note">
            {tr(
              '구성 요소마다 그것을 만든 단계의 번호를 붙였습니다. 번호는 아래 배포 순서의 번호와 같고, 파란 글자는 그 구성 요소를 만들 때 쓴 도구입니다. +는 8단계 뒤에 더한 웹 검색입니다.',
              'Each component carries the number of the step that built it. The numbers match the deployment order below, and the blue text is the tool used to build that component. The + marks web search, added after step 8.',
            )}
          </p>
        </header>
        <div className="table-scroll">
          <img
            className="about__figure"
            src={lang === 'en' ? figureEn : figure}
            width="1920"
            height="1080"
            loading="lazy"
            alt={tr(
              '구축 단계와 아키텍처. CloudFront, 내부 ALB, BFF, Cognito, S3 페이지에는 7, 게이트웨이에는 4, Decider 2B에는 5, 깨우기 API에는 6, Karpenter NodePool과 GPU 노드, S3 모델 버킷, Pod Identity에는 1, Gemma 4 31B와 Qwen3.8-27B, compile 캐시에는 3, 모델 적재 Job에는 2, AMP에는 8이 붙어 있다. 그림 아래에는 0단계부터 9단계까지의 이름, 쓴 도구, 만든 것을 적었다.',
              'Build steps on the architecture. CloudFront, the internal ALB, the BFF, Cognito, and the S3 pages carry 7. The gateway carries 4, Decider 2B carries 5, and the wake API carries 6. The Karpenter NodePool, the GPU node, the S3 model bucket, and Pod Identity carry 1. Gemma 4 31B, Qwen3.8-27B, and the compile cache carry 3, the model sync Job carries 2, and AMP carries 8. Below the map, steps 0 to 9 are listed with their names, tools, and what they built.',
            )}
          />
        </div>
      </section>

      <section className="panel" aria-labelledby="deploy-steps-title">
        <header className="panel__head">
          <h2 id="deploy-steps-title">{tr('배포 순서', 'Deployment order')}</h2>
          <p className="form-note">
            {tr(
              '0단계부터 차례로 적용했습니다. 번호를 누르면 그 단계로 갑니다. 9단계는 아직 남아 있습니다.',
              'Applied in order from step 0. Select a number to jump to that step. Step 9 is still to do.',
            )}
          </p>
        </header>
        <nav className="deploy__index" aria-label={tr('단계 바로 가기', 'Jump to a step')}>
          {DEPLOY.steps.map((step) => (
            <button key={step.n} type="button" className="deploy__jump" onClick={() => jump(step.n)}>
              <span className="deploy__num" aria-hidden="true">{step.n}</span>
              {step.title}
            </button>
          ))}
        </nav>
        <ol className="deploy__steps" ref={list}>
          {DEPLOY.steps.map((step) => (
            <li
              key={step.n}
              id={`deploy-step-${step.n}`}
              className={`dstep${step.status === 'todo' ? ' is-todo' : ''}`}
              tabIndex={-1}
            >
              <span className="dstep__mark deploy__num" aria-hidden="true">{step.n}</span>
              <div className="dstep__body">
                <header className="dstep__head">
                  <h3>
                    <span className="dstep__order">{tr(`${step.n}단계`, `Step ${step.n}`)}</span>
                    {step.title}
                  </h3>
                  <ul className="dstep__tools" aria-label={tr('쓴 도구', 'Tools used')}>
                    {step.tools.map((tool) => (
                      <li key={tool} className="chip">{tool}</li>
                    ))}
                    {step.status === 'todo' && <li className="chip chip--flag">{tr('남은 단계', 'Not done yet')}</li>}
                  </ul>
                </header>
                <p className="dstep__text">{step.text}</p>
                <div className="dstep__cols">
                  <ul className="dstep__points">
                    {step.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                  <div className="dstep__side">
                    {step.command && (
                      <pre className="dstep__cmd" aria-label={tr('실행한 명령', 'Commands run')}>
                        <code>{step.command}</code>
                      </pre>
                    )}
                    {step.rows.length > 0 && (
                      <dl className="dstep__rows">
                        {step.rows.map(([name, value]) => (
                          <div key={name}>
                            <dt>{name}</dt>
                            <dd>{value}</dd>
                          </div>
                        ))}
                      </dl>
                    )}
                    {step.doc && (
                      <p className="dstep__doc">
                        {tr('기록', 'Notes')} <code>{step.doc}</code>
                      </p>
                    )}
                  </div>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="panel" aria-labelledby="deploy-findings-title">
        <header className="panel__head">
          <h2 id="deploy-findings-title">{tr('주요 내용', 'Key findings')}</h2>
          <p className="form-note">
            {tr(
              '측정에서 확인한 내용입니다. 콜드 스타트와 처리량은 시나리오마다 한 번 잰 값이어서, 반복했을 때의 편차는 확인하지 않았습니다.',
              'These come from the measurements. Cold start and throughput were measured once per scenario, so run-to-run variance is not known.',
            )}
          </p>
        </header>
        <ul className="deploy__findings">
          {DEPLOY.findings.map((item) => (
            <li key={item.title} className="finding">
              <p className="finding__value">{item.value}</p>
              <h3>{item.title}</h3>
              <p className="finding__text">{item.text}</p>
              <p className="dstep__doc">
                {tr('기록', 'Notes')} <code>{item.doc}</code>
              </p>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
