"""모델 버킷에서 가중치를 뺀 파일(토크나이저와 설정)만 내려받는다.

  python3 fetch_tokenizer.py <models/ 아래 디렉터리 이름> <받을 위치>
"""
import os
import sys

import boto3

model_dir, target = sys.argv[1], sys.argv[2]
bucket = os.environ["MODEL_BUCKET"]
prefix = f"models/{model_dir}/"
s3 = boto3.client("s3")
os.makedirs(target, exist_ok=True)
count = 0
for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
    for item in page.get("Contents", []):
        name = item["Key"][len(prefix):]
        # 가중치와 하위 디렉터리는 받지 않는다.
        if not name or "/" in name or name.endswith((".safetensors", ".bin", ".gguf")):
            continue
        s3.download_file(bucket, item["Key"], os.path.join(target, name))
        count += 1
print(f"tokenizer files: {count} from s3://{bucket}/{prefix}", flush=True)
sys.exit(0 if count else 1)
