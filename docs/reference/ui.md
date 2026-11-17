# UI / UI 구현 상세

<a href="#english"><img src="https://img.shields.io/badge/lang-English-blue.svg" alt="English"></a>
<a href="#korean"><img src="https://img.shields.io/badge/lang-한국어-red.svg" alt="Korean"></a>

<a id="english"></a>
## English

### 1. Overview
The look of the check page: one self-hosted typeface, plain CSS files per area, and figures generated from the same Python sources as the infographics. The request-path map is an SVG whose nodes and edges the page highlights by id.

### 2. Components
| Component | Path | Purpose |
|---|---|---|
| Base styles | `app/web/src/styles.css` | Layout, type scale, `@font-face` |
| API call view styles | `app/web/src/apicall.css` | Styles of the API call view |
| Build steps view styles | `app/web/src/deploy.css` | Styles of the build steps view |
| Request-path map | `app/web/src/flow-map.svg` | Korean map; `flow-map.en.svg` is the English one with the same ids |
| Figures | `app/web/src/assets` | PNG figures of the architecture, API call and build steps views |
| Fonts | `app/web/src/fonts` | Self-hosted NanumSquareOTF WOFF2 files |
| Infographic sources | `docs/infographic/flow.py` | Request path and startup flow; `apicall.py` and `build_steps.py` for the other two |
| Infographic build | `docs/infographic/build.sh` | Builds Korean and English figures and the page assets |

### 3. Key Decisions
- The English figures use the same coordinates as the Korean ones and change only the text, so the page addresses both by the same ids.
- Measured values shown on the page come from the infographic modules, so one edit updates both the figure and the page.
- Body text uses weight 400 or 500 and emphasis uses 800; the Bold file serves up to 700 and the ExtraBold file from 800.
- Values written into map nodes are kept short so English text does not overflow the node.

No ADR has been written yet. The confirmed decisions are recorded in `AGENT.md`.

### 4. Code Pointers
- `app/web/src/styles.css`: `@font-face` and shared layout
- `app/web/src/flow.js`: Node and edge states of the request-path map
- `docs/infographic/apicall.py`: Measured values (`M`) used by the figure and the page
- `docs/infographic/build.sh`: Build entry point

### 5. Cross-references
- Related modules: `app/CLAUDE.md`
- Related documents: `docs/07-bff.md`, `docs/09-api-call-view.md`
- Related ADRs: none yet
- Related runbooks: none yet

<a id="korean"></a>
## 한국어

### 1. 개요
확인용 페이지의 모양입니다. 직접 올린 글꼴 하나, 영역별 CSS 파일, 그리고 인포그래픽과 같은 Python 소스에서 만든 그림을 씁니다. 요청 경로 지도는 SVG이고 화면이 노드와 선을 id로 찾아 강조합니다.

### 2. 구성요소
| 구성요소 | 경로 | 목적 |
|---|---|---|
| Base styles | `app/web/src/styles.css` | 레이아웃, 글자 크기, `@font-face` |
| API call view styles | `app/web/src/apicall.css` | API 호출 보기의 스타일 |
| Build steps view styles | `app/web/src/deploy.css` | 구축 과정 보기의 스타일 |
| Request-path map | `app/web/src/flow-map.svg` | 한국어 지도. `flow-map.en.svg`는 id가 같은 영어 지도 |
| Figures | `app/web/src/assets` | 구조, API 호출, 구축 과정 보기의 PNG 그림 |
| Fonts | `app/web/src/fonts` | 직접 올린 나눔스퀘어OTF WOFF2 파일 |
| Infographic sources | `docs/infographic/flow.py` | 요청 경로와 기동 흐름. 나머지 둘은 `apicall.py`, `build_steps.py` |
| Infographic build | `docs/infographic/build.sh` | 한국어판과 영어판 그림, 화면용 자산을 만듦 |

### 3. 주요 결정
- 영어판 그림은 한국어판과 좌표가 같고 글만 바꿉니다. 화면이 두 그림을 같은 id로 다룹니다.
- 화면에 보이는 측정값은 인포그래픽 모듈에서 옵니다. 한 곳을 고치면 그림과 화면이 함께 바뀝니다.
- 본문은 굵기 400이나 500, 강조는 800입니다. 700까지는 Bold 파일이, 800부터는 ExtraBold 파일이 받습니다.
- 지도의 노드 칸에 써넣는 값은 영어가 칸을 넘지 않게 짧게 씁니다.

ADR은 `docs/decisions/ADR-001-narrow-decider-fallback.md` 하나입니다(Decider 기본값 처리의 범위). 그 밖의 확정된 결정은 `AGENT.md`에 적혀 있습니다.

### 4. 코드 포인터
- `app/web/src/styles.css`: `@font-face`와 공통 레이아웃
- `app/web/src/flow.js`: 요청 경로 지도의 노드와 선 상태
- `docs/infographic/apicall.py`: 그림과 화면이 쓰는 측정값(`M`)
- `docs/infographic/build.sh`: 빌드의 진입점

### 5. 상호 참조
- 관련 모듈: `app/CLAUDE.md`
- 관련 문서: `docs/07-bff.md`, `docs/09-api-call-view.md`
- 관련 ADR: 아직 없음
- 관련 런북: 아직 없음

Last updated: 2026-11-16
