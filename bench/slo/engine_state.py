#!/usr/bin/env python3
"""SLO 측정의 수준마다 엔진이 어떤 상태였는지 AMP에서 읽어 온다.

  python3 engine_state.py <워크스페이스 ID> <모델(gemma|qwen)> <결과 폴더> > engine-state.json

job.log의 수준별 시작 시각으로 구간을 나누고, 그 구간에서 실행 중 요청 수와 대기 요청 수의 최댓값,
KV 캐시 사용률의 최댓값, 선점 횟수를 조회한다. 작업 장비의 AWS 자격 증명으로 서명한다(botocore 필요).
"""
import datetime
import json
import pathlib
import re
import sys
import urllib.parse

import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session

REGION = "ap-northeast-2"
workspace, model, directory = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
session = botocore.session.get_session()
http = URLLib3Session()


def query(expr, at):
    request = AWSRequest(method="POST", url=f"https://aps-workspaces.{REGION}.amazonaws.com/workspaces/{workspace}/api/v1/query",
                         data=urllib.parse.urlencode({"query": expr, "time": at.strftime("%Y-%m-%dT%H:%M:%SZ")}),
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
    SigV4Auth(session.get_credentials(), "aps", REGION).add_auth(request)
    result = json.loads(http.send(request.prepare()).content)["data"]["result"]
    return float(result[0]["value"][1]) if result else None


log = (directory / "job.log").read_text(errors="replace")
day = sys.argv[4] if len(sys.argv) > 4 else datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
starts = [(m.group(1), int(m.group(2)), datetime.datetime.strptime(f"{day} {m.group(3)}", "%Y-%m-%d %H:%M:%S"))
          for m in re.finditer(r">>> (\S+)\s+input=\d+ output=\d+\s+concurrency=(\d+)\s+num_prompts=\d+\s+(\d\d:\d\d:\d\d)", log)]
done = re.search(r"완료: \d+개 결과", log)
rows = []
for index, (scenario, concurrency, started) in enumerate(starts):
    if index + 1 < len(starts):
        ended = starts[index + 1][2]
    else:
        result = directory / f"{scenario}_c{concurrency}.json"
        ended = datetime.datetime.utcfromtimestamp(result.stat().st_mtime) if result.exists() and done else None
    if ended is None:
        continue
    window = f"{max(10, int((ended - started).total_seconds()))}s"
    selector = f'{{model="{model}"}}'
    rows.append({
        "scenario": scenario, "concurrency": concurrency, "started": started.strftime("%H:%M:%S"), "seconds": window[:-1],
        "running_max": query(f"max_over_time(vllm:num_requests_running{selector}[{window}])", ended),
        "waiting_max": query(f"max_over_time(vllm:num_requests_waiting{selector}[{window}])", ended),
        "kv_usage_max": query(f"max_over_time(vllm:kv_cache_usage_perc{selector}[{window}])", ended),
        "preemptions": query(f"increase(vllm:num_preemptions_total{selector}[{window}])", ended),
    })
json.dump(rows, sys.stdout, ensure_ascii=False, indent=1)
