#!/usr/bin/env bash
# 3부(구축 과정)의 인포그래픽 스타일 그림 세 장(그림 1, 2, 3)을 만든다.
# aws-infographic 스킬의 infokit.py, buildkit.py와 그림 1의 바탕인 build_steps.py, flow.py는 복사하지 않고
# docs/infographic의 것을 쓴다. 모듈은 한국어와 영어 글을 함께 담고 있고(common.py의 FIG_LANG), 여기서는 한국어판만 만든다.
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
  "p1_build_map:p3-01-build-map:fig01-build-map"
  "p2_tools:p3-02-tools-and-order:fig02-tools-and-order"
  "p3_checks:p3-03-step-checks:fig03-step-checks"
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
