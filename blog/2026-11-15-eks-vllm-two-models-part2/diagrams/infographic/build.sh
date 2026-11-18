#!/usr/bin/env bash
# 2부의 인포그래픽 스타일 그림 두 장(그림 1 한눈에 보기, 그림 2 SLO 지표와 동시 실행 한도)을 만든다.
# 그리기 도구는 docs/infographic의 infokit.py, buildkit.py(aws-infographic 스킬)를 그대로 쓴다.
#   ./build.sh    build/ 아래에 16:9 다크, 라이트 SVG와 PNG를 만들고 검사 결과를 출력한 뒤,
#                 라이트판 PNG와 SVG를 ../../images/ 에 그림 번호가 든 이름으로 복사한다
# 필요한 것 (docs/infographic/build.sh와 같다)
#   PYTHON            Pillow와 Playwright(Chromium)가 설치된 파이썬. 기본은 python3.
#                     "uv run --no-project --with playwright==1.64.1 --with pillow python"처럼 여러 단어도 된다
#   INFOKIT_FONTS     nanumsquare/, d2coding/ 폴더가 있는 글꼴 디렉터리
#   AWS_ICON_BUNDLE   aws-diagram 스킬의 assets/icons.json
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
KIT="$(cd ../../../../docs/infographic && pwd)"
SLUG=2026-11-15-eks-vllm-two-models-part2
IMAGES=../../images

# 모듈:빌드 이름:그림 파일 이름
FIGS=(
  "overview:p2-01-overview:fig01-overview"
  "slo_timeline:p2-02-slo-and-concurrency:fig02-slo-and-concurrency"
)

specs=()
for f in "${FIGS[@]}"; do
  IFS=: read -r module stem _ <<<"$f"
  specs+=("$module:$stem")
done
# PYTHON은 여러 단어 명령일 수 있어 따옴표 없이 펼친다
$PYTHON "$KIT/buildkit.py" build "${specs[@]}"

for f in "${FIGS[@]}"; do
  IFS=: read -r _ stem name <<<"$f"
  for ext in png svg; do
    cp "build/${stem}_16x9_light.$ext" "$IMAGES/$SLUG-$name.$ext"
    echo "copied $IMAGES/$SLUG-$name.$ext"
  done
done
