#!/usr/bin/env bash
# 요청 경로(08), LLM API 호출(09), 구축 단계(10) 인포그래픽을 만든다. aws-infographic 스킬의 infokit.py, buildkit.py를 그대로 쓴다.
#   ./build.sh          build/ 아래에 16:9 다크, 라이트 SVG와 PNG를 한국어판과 영어판으로 만들고 검사 결과를 출력한다
#                       웹 화면용 지도(app/web/src/flow-map.svg)도 함께 다시 만든다
# 필요한 것
#   PYTHON            Pillow와 Playwright(Chromium)가 설치된 파이썬. 기본은 python3
#   INFOKIT_FONTS     nanumsquare/, d2coding/ 폴더가 있는 글꼴 디렉터리
#   AWS_ICON_BUNDLE   aws-diagram 스킬의 assets/icons.json
set -euo pipefail
cd "$(dirname "$0")"
PYTHON=${PYTHON:-python3}
# 영어판(flow_en, apicall_en)은 같은 구조와 좌표에 글만 영어로 바꿔 그린다. 웹 화면의 한영 전환이 쓴다.
"$PYTHON" buildkit.py build flow:08-request-flow flow_en:08-request-flow-en
"$PYTHON" - <<'PY'
import pathlib
import flow
import flow_en
for module, name in ((flow, "flow-map.svg"), (flow_en, "flow-map.en.svg")):
    target = pathlib.Path("../../app/web/src") / name
    target.write_text(module.live_map("light"), encoding="utf-8")
    print("wrote", target, target.stat().st_size, "bytes")
PY
# 웹 화면의 "구조" 보기에 쓰는 그림. 글꼴이 그대로 보이도록 PNG를 쓴다.
cp build/08-request-flow_16x9_light.png ../../app/web/src/assets/request-flow.png
cp build/08-request-flow-en_16x9_light.png ../../app/web/src/assets/request-flow.en.png

# LLM API 호출 인포그래픽(09). 웹 화면의 "API 호출" 보기가 쓰는 값(단계 카드의 위치, 측정값)과 그림도 함께 만든다.
"$PYTHON" buildkit.py build apicall:09-llm-api-call apicall_en:09-llm-api-call-en
"$PYTHON" - <<'PY'
import pathlib
import apicall
target = pathlib.Path("../../app/web/src/apicall-data.js")
target.write_text(apicall.web_module(), encoding="utf-8")
print("wrote", target, target.stat().st_size, "bytes")
PY
cp build/09-llm-api-call_16x9_light.png ../../app/web/src/assets/llm-api-call.png
cp build/09-llm-api-call-en_16x9_light.png ../../app/web/src/assets/llm-api-call.en.png

# 구축 단계와 아키텍처 인포그래픽(10). 같은 구조도에 구성 요소를 만든 구축 단계(0~9)의 번호를 붙인 그림이고,
# 웹 화면의 "구축 과정" 보기가 쓴다.
"$PYTHON" buildkit.py build build_steps:10-build-steps build_steps_en:10-build-steps-en
cp build/10-build-steps_16x9_light.png ../../app/web/src/assets/build-steps.png
cp build/10-build-steps-en_16x9_light.png ../../app/web/src/assets/build-steps.en.png
