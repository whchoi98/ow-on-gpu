#!/usr/bin/env bash
# 3부의 인포그래픽 스타일 그림 세 장(그림 1, 3, 6)을 만든다.
# aws-infographic 스킬의 infokit.py, buildkit.py는 복사하지 않고 docs/infographic의 것을 쓴다.
#   ./build.sh    build/ 아래에 16:9 다크, 라이트 SVG와 PNG를 만들고 검사 결과를 출력한 뒤,
#                 라이트판의 PNG(2x)와 SVG를 ../../images/에 원고가 쓰는 이름으로 복사한다
#                 검사에서 이슈가 하나라도 나오면 복사하지 않고 끝난다
# 필요한 것 (docs/infographic/build.sh와 같다)
#   PYTHON            Pillow와 Playwright(Chromium)가 설치된 파이썬. 기본은 python3
#                     여러 단어로 된 명령도 받는다: PYTHON="uv run --no-project --with playwright==1.64.1 --with pillow python"
#   INFOKIT_FONTS     nanumsquare/, d2coding/ 폴더가 있는 글꼴 디렉터리
#   AWS_ICON_BUNDLE   aws-diagram 스킬의 assets/icons.json
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
KIT="$(cd ../../../../docs/infographic && pwd)"
SLUG=2026-11-15-eks-vllm-two-models-part3
IMAGES=../../images

# 모듈:빌드 이름:원고의 그림 이름
FIGURES=(
  "overview:p3-01-overview:fig01-overview"
  "priority_layers:p3-03-priority-layers:fig03-priority-layers"
  "sleep_wake:p3-06-sleep-wake:fig06-sleep-wake"
)

specs=()
for figure in "${FIGURES[@]}"; do
  IFS=: read -r module stem _ <<<"$figure"
  specs+=("$module:$stem")
done
# PYTHON은 여러 단어일 수 있어 따옴표 없이 펼친다.
# shellcheck disable=SC2086
$PYTHON "$KIT/buildkit.py" build "${specs[@]}"

for figure in "${FIGURES[@]}"; do
  IFS=: read -r _ stem name <<<"$figure"
  cp "build/${stem}_16x9_light.png" "$IMAGES/$SLUG-$name.png"
  cp "build/${stem}_16x9_light.svg" "$IMAGES/$SLUG-$name.svg"
  echo "copied $IMAGES/$SLUG-$name.{png,svg}"
done
