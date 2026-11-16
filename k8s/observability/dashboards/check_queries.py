#!/usr/bin/env python3
"""대시보드의 쿼리를 Amazon Managed Service for Prometheus에 보내 문법이 맞는지와 값이 나오는지 확인한다.

  python3 check_queries.py <워크스페이스 ID>

작업 장비의 AWS 자격 증명으로 SigV4 서명을 한다(botocore 필요). Grafana의 변수는 확인용 값으로 바꾼다.
"""
import json
import subprocess
import sys
import urllib.parse

import botocore.session
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session

REGION = "ap-northeast-2"
workspace = sys.argv[1]
session = botocore.session.get_session()
http = URLLib3Session()
lines = subprocess.run([sys.executable, __file__.replace("check_queries.py", "build.py"), "--queries"],
                       capture_output=True, text=True, check=True).stdout.splitlines()
failed = 0
for line in lines:
    item = json.loads(line)
    expr = item["expr"].replace("$__rate_interval", "1m").replace('model=~"$model"', 'model=~".+"')
    # 쿼리에 공백과 기호가 많아 GET의 쿼리 문자열로 보내면 서명이 맞지 않는다(403). 본문으로 보낸다.
    url = f"https://aps-workspaces.{REGION}.amazonaws.com/workspaces/{workspace}/api/v1/query"
    request = AWSRequest(method="POST", url=url, data=urllib.parse.urlencode({"query": expr}),
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
    SigV4Auth(session.get_credentials(), "aps", REGION).add_auth(request)
    response = http.send(request.prepare())
    body = json.loads(response.content)
    ok = response.status_code == 200 and body.get("status") == "success"
    series = len(body.get("data", {}).get("result", [])) if ok else 0
    failed += 0 if ok else 1
    print(f"{'ok ' if ok else 'ERR'} series={series:<3} {item['panel']} / {item['legend']}"
          + ("" if ok else f"  {body.get('error', response.status_code)}"))
sys.exit(1 if failed else 0)
