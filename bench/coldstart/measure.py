#!/usr/bin/env python3
"""콜드 스타트 구간 분해. 파드 생성부터 Ready까지를 노드 프로비저닝, 이미지 pull, 가중치 로드,
엔진 초기화, 기타로 나눈다. 1부의 측정 스크립트(gemma4-vllm/stages/measure-startup.sh)와 같은 방법이다.

작업 장비에서 kubectl로 실행한다. 표준 라이브러리만 쓴다.

  python3 measure.py --model gemma --scenario cold-baseline  --out results/2026-11-14-coldstart
  python3 measure.py --model gemma --scenario warm-baseline  --out ...
  python3 measure.py --model gemma --scenario cold-optimized --out ...
  python3 measure.py --model gemma --scenario warm-optimized --out ...

시나리오
  cold-*  서빙을 0으로 줄이고 이 모델의 GPU 노드를 지운 뒤 다시 1로 올린다. 노드 프로비저닝부터 잰다.
          GPU 노드가 새로 뜬다.
  warm-*  같은 노드에서 파드만 지워 다시 만들게 한다.
  *-baseline   bench/coldstart/k8s/gemma-baseline.yaml (Mountpoint FUSE, 기본 로더, 캐시 없음, 사전 pull 없음)
  *-optimized  k8s/<모델> (runai_streamer, S3의 compile 캐시 복원, hostPath 캐시, 이미지 사전 pull)

구간의 근거
  노드 프로비저닝  NodeClaim 생성 시각부터 노드의 Ready 전환 시각까지
  이미지 pull      kubelet의 Pulled 이벤트에 적힌 시간(vLLM 이미지). 이미 있으면 0
  가중치 로드      vLLM 로그의 "Model loading took"(없으면 "Loading weights took")
  엔진 초기화      vLLM 로그의 "init engine ... took"
  기타             전체에서 위 네 구간을 뺀 값

쿠버네티스의 시각은 1초 단위라서 전체 시간과 노드 프로비저닝에는 최대 1초의 오차가 있다.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
NAMESPACE = "inference"
MODELS = {
    "gemma": {
        "deployment": "vllm-gemma",
        "selector": "app.kubernetes.io/name=vllm-gemma",
        "optimized": ["apply", "-k", os.path.join(ROOT, "k8s/gemma")],
        "baseline": ["apply", "-f", os.path.join(ROOT, "bench/coldstart/k8s/gemma-baseline.yaml")],
        "nodepools": ["gemma-od", "gemma-noprepull"],
    },
    "qwen": {
        "deployment": "vllm-qwen",
        "selector": "app.kubernetes.io/name=vllm-qwen",
        "optimized": ["apply", "-k", os.path.join(ROOT, "k8s/qwen")],
        "baseline": None,
        "nodepools": ["qwen-od"],
    },
}
IMAGE = "vllm/vllm-openai"
MARKERS = re.compile(
    r"Loading weights took|Model loading took|init engine|torch\.compile took|Graph capturing finished"
    r"|Starting vLLM server|Application startup complete|non-default args|cache_restore")


def kubectl(*args, check=True, namespaced=True):
    command = ["kubectl"] + (["-n", NAMESPACE] if namespaced else []) + list(args)
    result = subprocess.run(command, capture_output=True, text=True)
    if check and result.returncode != 0:
        sys.exit(f"실패: {' '.join(command)}\n{result.stderr}")
    return result.stdout


def get(*args, namespaced=True):
    return json.loads(kubectl("get", *args, "-o", "json", namespaced=namespaced))


def parse(stamp):
    return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00")) if stamp else None


def seconds(start, end):
    return None if start is None or end is None else round((end - start).total_seconds(), 1)


def say(message):
    print(f"[{datetime.datetime.now(datetime.timezone.utc).strftime('%H:%M:%S')}] {message}", flush=True)


def live_pods(selector):
    pods = get("pod", "-l", selector)["items"]
    return [p for p in pods if not p["metadata"].get("deletionTimestamp")]


def wait_for(condition, what, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(2)
    sys.exit(f"시간 초과: {what}")


def duration_text(text):
    """kubelet 이벤트의 시간 표기(1m22.3s, 45.0s, 850ms)를 초로 바꾼다."""
    total = 0.0
    for value, unit in re.findall(r"([\d.]+)(ms|h|m|s)", text):
        total += float(value) * {"h": 3600, "m": 60, "s": 1, "ms": 0.001}[unit]
    return round(total, 1)


def prepare(model, scenario):
    """시나리오의 시작 상태를 만들고, 측정할 새 파드가 만들어지기 직전의 시각을 돌려준다."""
    kind, variant = scenario.split("-")
    apply = model[variant]
    if apply is None:
        sys.exit("이 모델에는 기준 구성이 없습니다")
    deployment = "deploy/" + model["deployment"]

    if kind == "cold":
        say("서빙을 0으로 줄입니다")
        kubectl("scale", deployment, "--replicas=0")
        wait_for(lambda: not get("pod", "-l", model["selector"])["items"], "기존 파드 종료", 300)
        pools = ",".join(model["nodepools"])
        claims = get("nodeclaim", "-l", f"karpenter.sh/nodepool in ({pools})", namespaced=False)["items"]
        for claim in claims:
            say(f"GPU 노드를 지웁니다: {claim['metadata']['name']} ({claim['status'].get('nodeName')})")
            kubectl("delete", "nodeclaim", claim["metadata"]["name"], "--wait=false", namespaced=False)
        wait_for(lambda: not get("nodeclaim", "-l", f"karpenter.sh/nodepool in ({pools})", namespaced=False)["items"],
                 "GPU 노드 삭제", 900)
        since = datetime.datetime.now(datetime.timezone.utc)
        say(f"{variant} 구성을 적용하고 1로 올립니다. GPU 노드가 새로 뜹니다")
        kubectl(*apply, namespaced=False)
        kubectl("scale", deployment, "--replicas=1")
        return since

    # 웜: 구성을 맞춘 뒤(바뀌었다면 다시 뜰 때까지 기다린다) 파드만 지운다.
    kubectl(*apply, namespaced=False)
    kubectl("rollout", "status", deployment, "--timeout=1800s")
    before = live_pods(model["selector"])
    if len(before) != 1:
        sys.exit(f"웜 재시작에는 Ready인 파드가 하나 있어야 합니다(지금 {len(before)}개)")
    say(f"파드를 지웁니다: {before[0]['metadata']['name']} (노드 {before[0]['spec'].get('nodeName')})")
    since = datetime.datetime.now(datetime.timezone.utc)
    kubectl("delete", "pod", before[0]["metadata"]["name"], "--wait=false")
    return since


def measure(model, scenario, since, out_dir, label):
    def new_pod():
        for pod in live_pods(model["selector"]):
            if parse(pod["metadata"]["creationTimestamp"]) >= since - datetime.timedelta(seconds=2):
                return pod["metadata"]["name"]
        return None

    name = wait_for(new_pod, "새 파드 생성", 300)
    say(f"파드 {name}이 Ready가 될 때까지 기다립니다(최대 30분)")
    kubectl("wait", "--for=condition=Ready", "pod/" + name, "--timeout=1800s")

    pod = get("pod", name)
    conditions = {c["type"]: parse(c.get("lastTransitionTime")) for c in pod["status"]["conditions"]}
    created = parse(pod["metadata"]["creationTimestamp"])
    main = pod["status"]["containerStatuses"][0]
    node_name = pod["spec"]["nodeName"]
    node = get("node", node_name, namespaced=False)
    node_ready = next((parse(c["lastTransitionTime"]) for c in node["status"]["conditions"] if c["type"] == "Ready"), None)
    claims = [c for c in get("nodeclaim", namespaced=False)["items"] if c["status"].get("nodeName") == node_name]
    claim_created = parse(claims[0]["metadata"]["creationTimestamp"]) if claims else None
    # 이 측정이 만든 노드일 때만 프로비저닝 시간을 적는다.
    new_node = claim_created is not None and claim_created >= since - datetime.timedelta(seconds=2)

    events = get("events", "--field-selector", f"involvedObject.name={name}")["items"]
    events.sort(key=lambda e: e.get("eventTime") or e.get("firstTimestamp") or "")
    pulls = []
    for event in events:
        if event["reason"] == "Pulled" and IMAGE in event["message"]:
            match = re.search(r" in ([\dhms.]+) \(", event["message"])
            pulls.append({"seconds": duration_text(match.group(1)) if match else 0.0, "message": event["message"]})

    log = kubectl("logs", name, "-c", "vllm")
    init_logs = {}
    for status in pod["status"].get("initContainerStatuses", []):
        init_logs[status["name"]] = kubectl("logs", name, "-c", status["name"], check=False)

    def marker(pattern):
        match = re.search(pattern, log)
        return float(match.group(1)) if match else None

    # v0.33.0은 스트리밍 로더 경로에서 "Loading weights took"을 남기지 않는다. 두 구성에 모두 나오는
    # "Model loading took"을 구간 값으로 쓰고, "Loading weights took"은 있을 때 함께 적는다.
    weights_only = marker(r"Loading weights took ([\d.]+) seconds")
    weights = marker(r"Model loading took [\d.]+ GiB memory and ([\d.]+) seconds")
    weights_source = "Model loading took"
    if weights is None:
        weights, weights_source = weights_only, "Loading weights took"
    engine = marker(r"init engine \(profile, create kv cache, warmup model\) took ([\d.]+) s")
    compilation = marker(r"init engine \(.*?\) took [\d.]+ s \(compilation: ([\d.]+) s\)")

    total = seconds(created, conditions.get("Ready"))
    node_provision = seconds(claim_created, node_ready) if new_node else 0.0
    image_pull = round(sum(p["seconds"] for p in pulls), 1)
    known = [node_provision, image_pull, weights, engine]
    other = round(total - sum(known), 1) if total is not None and None not in known else None

    init_containers = []
    for status in pod["status"].get("initContainerStatuses", []):
        done = status["state"].get("terminated", {})
        init_containers.append({"name": status["name"],
                                "seconds": seconds(parse(done.get("startedAt")), parse(done.get("finishedAt")))})

    result = {
        "label": label,
        "scenario": scenario,
        "pod": name,
        "node": node_name,
        "instance_type": node["metadata"]["labels"].get("node.kubernetes.io/instance-type"),
        "capacity_type": node["metadata"]["labels"].get("karpenter.sh/capacity-type"),
        "zone": node["metadata"]["labels"].get("topology.kubernetes.io/zone"),
        "nodepool": node["metadata"]["labels"].get("karpenter.sh/nodepool"),
        "new_node": new_node,
        "restart_count": main["restartCount"],
        "timestamps": {
            "pod_created": pod["metadata"]["creationTimestamp"],
            "nodeclaim_created": claims[0]["metadata"]["creationTimestamp"] if claims else None,
            "node_ready": node_ready.isoformat() if node_ready else None,
            "pod_scheduled": conditions["PodScheduled"].isoformat() if conditions.get("PodScheduled") else None,
            "pod_initialized": conditions["Initialized"].isoformat() if conditions.get("Initialized") else None,
            "container_started": main["state"].get("running", {}).get("startedAt"),
            "pod_ready": conditions["Ready"].isoformat() if conditions.get("Ready") else None,
        },
        "segments_s": {
            "total": total,
            "node_provisioning": node_provision,
            "image_pull": image_pull,
            "weight_load": weights,
            "engine_init": engine,
            "other": other,
        },
        "detail_s": {
            "pod_created_to_scheduled": seconds(created, conditions.get("PodScheduled")),
            "scheduled_to_container_start": seconds(conditions.get("PodScheduled"),
                                                    parse(main["state"].get("running", {}).get("startedAt"))),
            "container_start_to_ready": seconds(parse(main["state"].get("running", {}).get("startedAt")),
                                                conditions.get("Ready")),
            "compilation": compilation,
            "loading_weights_took": weights_only,
            "init_containers": init_containers,
        },
        "weight_load_marker": weights_source,
        "image_pulls": pulls,
    }

    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, label)
    with open(base + ".json", "w") as out:
        json.dump(result, out, ensure_ascii=False, indent=1)
    with open(base + ".log", "w") as out:
        out.write(log)
    with open(base + ".markers", "w") as out:
        lines = [line for line in log.splitlines() if MARKERS.search(line)]
        for container, text in init_logs.items():
            lines += [f"[{container}] {line}" for line in text.splitlines() if MARKERS.search(line)]
        out.write("\n".join(lines) + "\n")
    with open(base + ".events", "w") as out:
        for event in events:
            out.write(f"{event.get('eventTime') or event.get('firstTimestamp')}\t{event['reason']}\t{event['message']}\n")
    with open(base + ".pod.json", "w") as out:
        json.dump(pod, out, ensure_ascii=False, indent=1)
    print(json.dumps(result["segments_s"], ensure_ascii=False))
    say(f"저장: {base}.json")
    if main["restartCount"]:
        say(f"주의: 컨테이너가 {main['restartCount']}번 다시 시작됐습니다. 구간이 실제와 다를 수 있습니다")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--scenario", required=True,
                        choices=["cold-baseline", "warm-baseline", "cold-optimized", "warm-optimized"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--label", help="결과 파일 이름. 기본은 <모델>-<시나리오>")
    args = parser.parse_args()
    model = MODELS[args.model]
    since = prepare(model, args.scenario)
    measure(model, args.scenario, since, args.out, args.label or f"{args.model}-{args.scenario}")


if __name__ == "__main__":
    main()
