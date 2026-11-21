#!/usr/bin/env bash
# 2부의 인포그래픽 스타일 그림을 만든다. docs/infographic의 infokit.py, buildkit.py, flow.py를 그대로 쓴다.
#   ./build.sh    build/ 아래에 16:9 다크, 라이트 SVG와 PNG를 만들고 검사 결과를 출력한 뒤,
#                 원고가 쓰는 라이트판을 ../../images/ 에 그림 번호가 든 이름으로 복사한다
# 그림 모듈에는 한국어와 영어 글이 함께 있다(common.py의 pick). 이 스크립트는 한국어판만 만든다.
# 영어판은 FIG_LANG=en으로 같은 모듈을 그리면 나온다(개인 블로그 글이 쓴다).
# 필요한 것 (docs/infographic/build.sh와 같다)
#   PYTHON            Pillow와 Playwright(Chromium)가 설치된 파이썬. 기본은 python3. 여러 단어 명령도 받는다
#                     예: PYTHON="uv run --no-project --with playwright==1.64.1 --with pillow python"
#   INFOKIT_FONTS     nanumsquare/, d2coding/ 폴더가 있는 글꼴 디렉터리
#   AWS_ICON_BUNDLE   aws-diagram 스킬의 assets/icons.json
set -euo pipefail
cd "$(dirname "$0")"
KIT="$(cd ../../../../docs/infographic && pwd)"
SLUG=2026-11-15-eks-vllm-two-models-part2
export FIG_LANG=ko
# 따옴표 없이 펼쳐 여러 단어 명령을 받는다
${PYTHON:-python3} "$KIT/buildkit.py" build \
  p1_architecture:p2-01-architecture p2_coldstart:p2-02-cold-start p3_capacity:p2-03-gpu-memory-concurrency \
  p4_priority:p2-04-priority-layers p5_sleep:p2-05-sleep-wake

copy() {  # copy <빌드 이름> <그림 번호와 이름>
  cp "build/$1_16x9_light.png" "../../images/$SLUG-$2.png"
  cp "build/$1_16x9_light.svg" "../../images/$SLUG-$2.svg"
}
copy p2-01-architecture fig01-architecture
copy p2-02-cold-start fig02-cold-start
copy p2-03-gpu-memory-concurrency fig03-gpu-memory-concurrency
copy p2-04-priority-layers fig04-priority-layers
copy p2-05-sleep-wake fig05-sleep-wake
