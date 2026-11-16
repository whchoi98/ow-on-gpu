#!/usr/bin/env python3
"""측정 스크립트를 클러스터 안의 측정 전용 노드에서 Job으로 실행하고 결과를 내려받는다.

작업 장비에서 kubectl로 실행한다. 표준 라이브러리만 쓴다.

  python3 bench/job.py --name slo-gemma --service-account gemma --out results/2026-11-14-slo/gemma \
      --env MODEL_NAME=gemma-4-31b --env MODEL_DIR=gemma-4-31B-it-FP8-dynamic \
      --env BASE_URL=http://vllm-gemma.inference.svc:8000 -- bash /bench/run-bench.sh

  python3 bench/job.py --name priority-gemma --service-account gemma --out results/2026-11-14-priority \
      -- python3 /bench/run.py

- 파드는 vLLM 이미지로 뜬다. `vllm bench serve`와 aiohttp가 이 이미지에 들어 있다.
- 노드는 k8s/bench의 NodePool `bench`가 만든다. 처음 실행할 때 노드가 뜨고 이미지(9.1GiB)를 받는 시간이 든다.
- 스크립트는 ConfigMap `bench-scripts`로 /bench에 마운트된다. 결과는 파드의 /results에 쓰고, 끝나면 --out으로 복사한다.
- 서비스 계정은 모델 버킷을 읽을 수 있는 gemma 또는 qwen을 쓴다(토크나이저를 S3에서 받는다).
"""
import argparse
import json
import os
import shlex
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMESPACE = "inference"
IMAGE = "vllm/vllm-openai:v0.33.0"
SCRIPTS = ["bench/slo/run-bench.sh", "bench/slo/bench_serve.py", "bench/slo/fetch_tokenizer.py", "bench/priority/run.py"]


def kubectl(*args, check=True, stdin=None):
    result = subprocess.run(["kubectl", "-n", NAMESPACE, *args], capture_output=True, text=True, input=stdin)
    if check and result.returncode != 0:
        sys.exit(f"실패: kubectl {' '.join(args)}\n{result.stderr}")
    return result.stdout


def manifest(args, command):
    env = [
        {"name": "MODEL_BUCKET", "valueFrom": {"configMapKeyRef": {"name": "platform", "key": "MODEL_BUCKET"}}},
        {"name": "AWS_DEFAULT_REGION", "valueFrom": {"configMapKeyRef": {"name": "platform", "key": "AWS_REGION"}}},
        # 측정 파드도 Hugging Face에서 받지 않는다.
        {"name": "HF_HUB_OFFLINE", "value": "1"},
        {"name": "RESULTS_DIR", "value": "/results"},
    ] + [{"name": item.split("=", 1)[0], "value": item.split("=", 1)[1]} for item in args.env]
    # 끝난 뒤에도 파드를 남겨 두어야 결과를 복사할 수 있다. 종료 코드를 파일로 남기고 기다린다.
    shell = shlex.join(command) + "; echo $? > /results/EXIT; sleep 86400"
    return {
        "apiVersion": "batch/v1", "kind": "Job",
        "metadata": {"name": args.name, "labels": {"app.kubernetes.io/name": "bench"}},
        "spec": {
            "backoffLimit": 0,
            # 이 스크립트가 중간에 죽어도 파드가 계속 남지 않게 한다.
            "activeDeadlineSeconds": args.timeout + 1800,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {"labels": {
                    "app.kubernetes.io/name": "bench",
                    # Qwen의 8000 포트는 NetworkPolicy가 이 라벨의 파드만 받는다(k8s/sleep-controller).
                    "ow-on-gpu/qwen-admin": "true",
                }},
                "spec": {
                    "restartPolicy": "Never",
                    "serviceAccountName": args.service_account,
                    "nodeSelector": {"karpenter.sh/nodepool": "bench"},
                    "tolerations": [{"key": "ow-on-gpu/bench", "operator": "Exists", "effect": "NoSchedule"}],
                    "containers": [{
                        "name": "bench", "image": IMAGE, "command": ["bash", "-c", shell], "env": env,
                        "resources": {"requests": {"cpu": "6", "memory": "10Gi"}},
                        "volumeMounts": [{"name": "scripts", "mountPath": "/bench", "readOnly": True},
                                         {"name": "results", "mountPath": "/results"}],
                    }],
                    "volumes": [{"name": "scripts", "configMap": {"name": "bench-scripts"}},
                                {"name": "results", "emptyDir": {}}],
                },
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--service-account", required=True, choices=["gemma", "qwen"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--env", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument("--timeout", type=int, default=7200, help="측정이 끝나기를 기다리는 최대 시간(초)")
    parser.add_argument("--print", action="store_true", help="매니페스트만 출력하고 끝낸다")
    parser.add_argument("command", nargs="+")
    args = parser.parse_args()
    job = manifest(args, args.command)
    if args.print:
        print(json.dumps(job, ensure_ascii=False, indent=1))
        return 0

    files = [f"--from-file={os.path.join(ROOT, path)}" for path in SCRIPTS]
    rendered = kubectl("create", "configmap", "bench-scripts", *files, "--dry-run=client", "-o", "yaml")
    kubectl("apply", "-f", "-", stdin=rendered)
    kubectl("delete", "job", args.name, "--ignore-not-found", "--wait=true")
    kubectl("apply", "-f", "-", stdin=json.dumps(job))
    print(f"Job {args.name}을 만들었습니다. 측정 노드와 이미지를 기다립니다", flush=True)

    pod = ""
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        pods = json.loads(kubectl("get", "pod", "-l", f"job-name={args.name}", "-o", "json"))["items"]
        if pods and pods[0]["status"].get("phase") == "Running":
            pod = pods[0]["metadata"]["name"]
            break
        time.sleep(5)
    if not pod:
        sys.exit("측정 파드가 20분 안에 뜨지 않았습니다")

    os.makedirs(args.out, exist_ok=True)
    log = open(os.path.join(args.out, "job.log"), "w")
    follower = subprocess.Popen(["kubectl", "-n", NAMESPACE, "logs", "-f", pod], stdout=log, stderr=subprocess.STDOUT)
    print(f"파드 {pod}에서 실행 중입니다. 로그: {os.path.join(args.out, 'job.log')}", flush=True)
    code = None
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        result = subprocess.run(["kubectl", "-n", NAMESPACE, "exec", pod, "--", "cat", "/results/EXIT"],
                                capture_output=True, text=True)
        if result.returncode == 0:
            code = int(result.stdout.strip() or 1)
            break
        time.sleep(15)
    follower.terminate()
    log.close()

    subprocess.run(["kubectl", "cp", f"{NAMESPACE}/{pod}:/results", args.out], check=False)
    kubectl("delete", "job", args.name, "--wait=false")
    if code is None:
        sys.exit(f"{args.timeout}초 안에 끝나지 않았습니다. 그때까지의 결과만 복사했습니다")
    print(f"끝났습니다(종료 코드 {code}). 결과: {args.out}", flush=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
