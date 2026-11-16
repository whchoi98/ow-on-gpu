import figure from './assets/request-flow.png';
import figureEn from './assets/request-flow.en.png';
import { tr, useLang } from './i18n.js';

// 구조 한눈에 보기. 그림은 docs/infographic에서 aws-infographic 스킬의 빌더로 만든 것이다.
// 영어판(request-flow.en.png)은 같은 구조와 좌표에 글만 영어로 바꿔 그린 것이다(docs/infographic/flow_en.py).
export default function About() {
  const lang = useLang();
  return (
    <div className="console__body">
      <section className="panel">
        <header className="panel__head">
          <h2>{tr('구조', 'Architecture')}</h2>
          <p className="form-note">
            {tr(
              '요청이 브라우저에서 GPU까지 가는 경로, 모델과 이미지가 GPU 노드에 올라가는 흐름(0번에서 5번), BFF가 모델을 정하는 순서, 구간마다 잰 시간, 경계마다 둔 접근 제한을 한 장에 모았습니다.',
              'One page with the path a request takes from the browser to the GPU, how models and images reach the GPU nodes (steps 0 to 5), the order in which the BFF picks a model, the time measured in each segment, and the access limits at each boundary.',
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
              '요청 경로와 구간별 시간. 브라우저에서 CloudFront, 내부 ALB, BFF, 게이트웨이를 거쳐 Gemma 4 31B 또는 Qwen3.8-27B로 가는 경로와, Hugging Face에서 S3 모델 버킷으로의 모델 적재, Karpenter의 노드 프로비저닝, 이미지 pull, 가중치 로드, 엔진 초기화, 추론 요청으로 이어지는 흐름, 모델 결정 순서, 구간별 측정값, 경계별 접근 제한을 보여 준다.',
              'Request path and segment latency. Shows the path from the browser through CloudFront, the internal ALB, the BFF, and the gateway to Gemma 4 31B or Qwen3.8-27B, the flow from model sync out of Hugging Face into the S3 model bucket through Karpenter node provisioning, image pull, weight load, engine init, and the inference request, the model decision order, the measured value of each segment, and the access limits at each boundary.',
            )}
          />
        </div>
        <p className="form-note">
          {tr(
            '수치는 서울 리전에서 잰 값입니다. 요청 경로의 시간은 2026년 11월 15일에 요청을 하나씩 보내 잰 중앙값이고, 0번에서 4번의 시간은 11월 14일에 잰 값으로 1번에서 4번은 Gemma 콜드 스타트의 기준 구성과 최적화 구성입니다. 요청 보기의 흐름 그림은 같은 지도에 그 요청의 실제 경로와 시간을 표시합니다.',
            'The numbers were measured in the Seoul Region. Request path times are medians of requests sent one at a time on November 15, 2026. Steps 0 to 4 were measured on November 14, and steps 1 to 4 show the baseline and optimized Gemma cold start. The flow map in the Request view marks the actual path and timing of each request on the same map.',
          )}
        </p>
      </section>
    </div>
  );
}
