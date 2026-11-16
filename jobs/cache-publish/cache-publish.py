"""노드의 vLLM 캐시 디렉터리를 S3의 compile 캐시 prefix로 올린다.

vLLM 파드가 한 번 기동해 캐시를 만든 뒤, 같은 노드에서 실행한다. 올린 객체 수와 크기를 한 줄로 남긴다.
assets/는 S3의 모델 설정 파일 사본이라 올리지 않는다. 파드가 뜰 때마다 다시 받는다.
"""
import concurrent.futures
import json
import os
import sys
import time

import boto3

bucket = os.environ["MODEL_BUCKET"]
prefix = os.environ["CACHE_PREFIX"].strip("/") + "/"
cache_dir = os.environ.get("CACHE_DIR", "/vllm-cache")
excluded = tuple(p for p in os.environ.get("EXCLUDE", "assets/").split(",") if p)

started = time.monotonic()
files = []
for root, _, names in os.walk(cache_dir):
    for name in names:
        path = os.path.join(root, name)
        relative = os.path.relpath(path, cache_dir)
        if not relative.startswith(excluded):
            files.append((path, relative, os.path.getsize(path)))

if not files:
    print(json.dumps({"event": "cache_publish", "error": f"{cache_dir}에 올릴 파일이 없습니다"}, ensure_ascii=False))
    sys.exit(1)

s3 = boto3.client("s3")
with concurrent.futures.ThreadPoolExecutor(16) as pool:
    list(pool.map(lambda f: s3.upload_file(f[0], bucket, prefix + f[1]), files))

uploaded = {}
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
    uploaded.update({o["Key"][len(prefix):]: o["Size"] for o in page.get("Contents", [])})
expected = {relative: size for _, relative, size in files}
missing = sorted(k for k, size in expected.items() if uploaded.get(k) != size)

print(json.dumps({
    "event": "cache_publish",
    "destination": f"s3://{bucket}/{prefix}",
    "objects": len(files),
    "bytes": sum(expected.values()),
    "by_top_level": {
        top: sum(size for relative, size in expected.items() if relative.split("/")[0] == top)
        for top in sorted({relative.split("/")[0] for relative in expected})
    },
    "missing": missing,
    "seconds": round(time.monotonic() - started, 2),
}, ensure_ascii=False), flush=True)
sys.exit(1 if missing else 0)
