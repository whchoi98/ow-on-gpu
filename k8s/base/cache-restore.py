"""S3의 compile 캐시 prefix를 로컬 캐시 디렉터리로 내려받는다.

vLLM 파드의 initContainer로 실행한다. prefix에 객체가 없으면 아무것도 하지 않고 정상 종료한다.
이미 같은 크기로 있는 파일은 다시 받지 않는다(같은 노드에서 파드만 다시 뜬 경우).
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

started = time.monotonic()
s3 = boto3.client("s3")
objects = []
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
    objects += [(o["Key"], o["Size"]) for o in page.get("Contents", []) if not o["Key"].endswith("/")]


def fetch(item):
    key, size = item
    path = os.path.join(cache_dir, key[len(prefix):])
    if os.path.exists(path) and os.path.getsize(path) == size:
        return 0
    os.makedirs(os.path.dirname(path), exist_ok=True)
    s3.download_file(bucket, key, path)
    return 1


downloaded = 0
if objects:
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        downloaded = sum(pool.map(fetch, objects))

print(json.dumps({
    "event": "cache_restore",
    "source": f"s3://{bucket}/{prefix}",
    "objects": len(objects),
    "bytes": sum(size for _, size in objects),
    "downloaded": downloaded,
    "seconds": round(time.monotonic() - started, 2),
}), flush=True)
sys.exit(0)
