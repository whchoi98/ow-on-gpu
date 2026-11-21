#!/usr/bin/env bash
# 1부의 인포그래픽 스타일 그림을 만든다. docs/infographic의 infokit.py, buildkit.py, apicall.py를 그대로 쓴다.
#   ./build.sh    build/ 아래에 16:9 다크, 라이트 SVG와 PNG를 만들고 검사 결과를 출력한 뒤,
#                 원고가 쓰는 라이트판을 ../../images/ 에 그림 번호가 든 이름으로 복사한다
# 모듈에는 한국어와 영어 글이 함께 있다. 원고는 한국어판을 쓰고, 영어판은 FIG_LANG=en으로 만든다.
# 필요한 것 (docs/infographic/build.sh와 같다)
#   PYTHON            Pillow와 Playwright(Chromium)가 설치된 파이썬. 기본은 python3. 여러 단어 명령도 받는다
#                     예: PYTHON="uv run --no-project --with playwright==1.64.1 --with pillow python"
#   INFOKIT_FONTS     nanumsquare/, d2coding/ 폴더가 있는 글꼴 디렉터리
#   AWS_ICON_BUNDLE   aws-diagram 스킬의 assets/icons.json
set -euo pipefail
cd "$(dirname "$0")"
KIT="$(cd ../../../../docs/infographic && pwd)"
SLUG=2026-11-15-eks-vllm-two-models-part1
# 따옴표 없이 펼쳐 여러 단어 명령을 받는다
FIG_LANG=ko ${PYTHON:-python3} "$KIT/buildkit.py" build \
  f1_apicall:p1-01-llm-api-call f2_decision:p1-02-model-decision f3_websearch:p1-03-web-search-flow

copy() {  # copy <빌드 이름> <그림 번호와 이름>
  cp "build/$1_16x9_light.png" "../../images/$SLUG-$2.png"
  cp "build/$1_16x9_light.svg" "../../images/$SLUG-$2.svg"
}
copy p1-01-llm-api-call fig01-llm-api-call
copy p1-02-model-decision fig02-model-decision
copy p1-03-web-search-flow fig03-web-search-flow
