#!/usr/bin/env python3
"""Hugging Face 저장소의 파일을 받는 대로 s5cmd pipe로 S3에 올린다.

로컬 디스크에 가중치를 쌓지 않는다. 파일마다 받으면서 해시를 계산해 Hugging Face가 알려 준 값과
맞춰 보고, 끝나면 S3의 객체 수와 크기를 기대값과 비교한다. 표준 라이브러리만 쓴다.

  python3 sync.py          적재 실행
  python3 sync.py --plan   Hugging Face 목록만 조회해 올릴 대상과 크기를 출력
"""
import concurrent.futures
import hashlib
import http.client
import io
import json
import os
import platform
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request

BUCKET = os.environ["BUCKET"]
MODELS = json.load(open(os.environ.get("MODELS_FILE", "/config/models.json")))
FILE_CONCURRENCY = int(os.environ.get("FILE_CONCURRENCY", "8"))
ATTEMPTS = 3
USER_AGENT = "model-sync"

S5CMD_VERSION = "2.3.0"
# https://github.com/peak/s5cmd/releases/download/v2.3.0/s5cmd_checksums.txt
S5CMD_SHA256 = {
    "x86_64": ("Linux-64bit", "de0fdbfa3aceae55e069ba81a0fc17b2026567637603734a387b2fca06c299b4"),
    "aarch64": ("Linux-arm64", "1439f0d00ecedcd2a2f1f2c6749bbb0152b2257bf5086f29646ec8ae38798e24"),
}


def log(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=False), flush=True)


def http_get(url, headers=None):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    return urllib.request.urlopen(request, timeout=60)


def install_s5cmd():
    """S5CMD_BIN이 있으면 그것을 쓰고, 없으면 릴리스 파일을 받아 체크섬을 확인한 뒤 /tmp에 푼다."""
    if os.environ.get("S5CMD_BIN"):
        return os.environ["S5CMD_BIN"]
    asset, expected = S5CMD_SHA256[platform.machine()]
    url = f"https://github.com/peak/s5cmd/releases/download/v{S5CMD_VERSION}/s5cmd_{S5CMD_VERSION}_{asset}.tar.gz"
    data = http_get(url).read()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise SystemExit(f"s5cmd 체크섬 불일치: {actual}")
    with tarfile.open(fileobj=io.BytesIO(data)) as tar:
        binary = tar.extractfile("s5cmd").read()
    path = "/tmp/s5cmd"
    with open(path, "wb") as f:
        f.write(binary)
    os.chmod(path, 0o755)
    return path


def aws_env():
    """s5cmd 2.3.0의 AWS SDK(v1.44)는 EKS Pod Identity를 지원하지 않는다(v1.47.11부터 지원).

    Pod Identity 에이전트에서 임시 자격 증명을 직접 받아 환경 변수로 넘긴다.
    Pod Identity 환경이 아니면 s5cmd의 기본 자격 증명 탐색에 맡긴다.
    """
    uri = os.environ.get("AWS_CONTAINER_CREDENTIALS_FULL_URI")
    if not uri:
        return dict(os.environ)
    token = open(os.environ["AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE"]).read().strip()
    credentials = json.load(http_get(uri, {"Authorization": token}))
    env = {k: v for k, v in os.environ.items() if not k.startswith("AWS_CONTAINER_")}
    env.update(
        AWS_ACCESS_KEY_ID=credentials["AccessKeyId"],
        AWS_SECRET_ACCESS_KEY=credentials["SecretAccessKey"],
        AWS_SESSION_TOKEN=credentials["Token"],
    )
    return env


def list_source(model):
    """저장소의 파일 목록. LFS 파일은 sha256, 나머지는 git blob sha1을 기대 해시로 쓴다."""
    url = f"https://huggingface.co/api/models/{model['repo']}/revision/{model['revision']}?blobs=true"
    info = json.load(http_get(url))
    if info["sha"] != model["revision"]:
        raise SystemExit(f"{model['repo']}: 리비전 불일치 {info['sha']}")
    files = []
    for sibling in info["siblings"]:
        lfs = sibling.get("lfs")
        files.append({
            "path": sibling["rfilename"],
            "size": sibling["size"],
            "algo": "sha256" if lfs else "git-sha1",
            "digest": lfs["sha256"] if lfs else sibling["blobId"],
        })
    return files


def list_s3(s5cmd, prefix):
    """prefix 아래 객체의 {상대 경로: 크기}. 객체가 없으면 s5cmd가 1로 끝나므로 빈 결과로 본다."""
    result = subprocess.run(
        [s5cmd, "--json", "ls", f"s3://{BUCKET}/{prefix}/*"],
        env=aws_env(), capture_output=True, text=True,
    )
    if result.returncode != 0 and "no object found" not in result.stderr:
        raise SystemExit(f"s5cmd ls 실패: {result.stderr.strip()}")
    objects = {}
    for line in result.stdout.splitlines():
        entry = json.loads(line)
        if entry.get("type") == "file":
            key = entry["key"].split(f"s3://{BUCKET}/{prefix}/", 1)[1]
            objects[key] = entry.get("size", 0)
    return objects


def transfer(s5cmd, model, file):
    url = "https://huggingface.co/{}/resolve/{}/{}".format(
        model["repo"], model["revision"], urllib.parse.quote(file["path"]))
    destination = f"s3://{BUCKET}/{model['prefix']}/{file['path']}"
    for attempt in range(1, ATTEMPTS + 1):
        started = time.monotonic()
        digest = hashlib.sha256() if file["algo"] == "sha256" else hashlib.sha1(b"blob %d\0" % file["size"])
        received = 0
        process = subprocess.Popen(
            [s5cmd, "pipe", "--concurrency", "4", "--part-size", "64", destination],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=aws_env(),
        )
        error = None
        try:
            with http_get(url) as response:
                while True:
                    chunk = response.read(8 << 20)
                    if not chunk:
                        break
                    digest.update(chunk)
                    process.stdin.write(chunk)
                    received += len(chunk)
        except (OSError, http.client.HTTPException) as e:
            error = f"전송 오류: {e!r}"
        finally:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.wait() != 0:
            error = error or "s5cmd pipe 실패"
        elif received != file["size"]:
            error = f"크기 불일치: {received} != {file['size']}"
        elif digest.hexdigest() != file["digest"]:
            error = f"{file['algo']} 불일치"
        seconds = time.monotonic() - started
        if error is None:
            log("uploaded", model=model["prefix"], path=file["path"], bytes=received,
                seconds=round(seconds, 1), mb_per_s=round(received / 1e6 / max(seconds, 1e-3), 1))
            return True
        log("retry" if attempt < ATTEMPTS else "failed", model=model["prefix"], path=file["path"],
            attempt=attempt, error=error)
    return False


def main():
    plan_only = "--plan" in sys.argv
    sources = {model["prefix"]: list_source(model) for model in MODELS}
    for model in MODELS:
        files = sources[model["prefix"]]
        log("plan", model=model["prefix"], repo=model["repo"], revision=model["revision"],
            objects=len(files), bytes=sum(f["size"] for f in files))
    if plan_only:
        return 0

    s5cmd = install_s5cmd()
    started = time.monotonic()
    jobs = []
    for model in MODELS:
        existing = list_s3(s5cmd, model["prefix"])
        for file in sources[model["prefix"]]:
            # 다시 실행할 때 이미 같은 크기로 올라간 파일은 건너뛴다. 이 경우 내용은 다시 확인하지 않는다.
            if existing.get(file["path"]) == file["size"]:
                log("skipped", model=model["prefix"], path=file["path"], bytes=file["size"])
            else:
                jobs.append((model, file))
    jobs.sort(key=lambda job: -job[1]["size"])
    with concurrent.futures.ThreadPoolExecutor(FILE_CONCURRENCY) as pool:
        results = list(pool.map(lambda job: transfer(s5cmd, *job), jobs))

    ok = all(results)
    total_objects = total_bytes = 0
    for model in MODELS:
        expected = {f["path"]: f["size"] for f in sources[model["prefix"]]}
        actual = list_s3(s5cmd, model["prefix"])
        match = actual == expected
        ok = ok and match
        total_objects += len(actual)
        total_bytes += sum(actual.values())
        log("verified", model=model["prefix"], s3=f"s3://{BUCKET}/{model['prefix']}/",
            objects=len(actual), bytes=sum(actual.values()),
            expected_objects=len(expected), expected_bytes=sum(expected.values()), match=match)
    log("summary", ok=ok, objects=total_objects, bytes=total_bytes,
        transferred=len(jobs), seconds=round(time.monotonic() - started, 1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
