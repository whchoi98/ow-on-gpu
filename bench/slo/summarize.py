#!/usr/bin/env python3
"""vllm bench serve 결과(S*_c*.json)를 표와 SLO 판정으로 정리한다. 2부의 bench/summarize.py와 같은 값을 뽑는다.

  python3 summarize.py results/2026-11-14-slo/gemma > results/2026-11-14-slo/gemma/SUMMARY.md

SLO: TTFT p99 500ms 이하와 ITL p99 50ms 이하를 함께 만족하는 가장 큰 동시성.
"""
import json
import pathlib
import re
import sys

TTFT_SLO_MS, ITL_SLO_MS = 500, 50
SCENARIOS = {
    "S1_chat": "짧은 채팅 (입력 256, 출력 128)",
    "S2_summary": "요약과 생성 (입력 1024, 출력 256)",
    "S3_moderation": "분류 (입력 512, 출력 16)",
    "S4_rag": "장문 RAG (입력 4096, 출력 256)",
}


def pick(data, *names):
    for name in names:
        if isinstance(data.get(name), (int, float)):
            return data[name]
    return None


def load(directory):
    rows = []
    for path in sorted(pathlib.Path(directory).glob("S*_c*.json")):
        match = re.match(r"(S\d_\w+)_c(\d+)\.json", path.name)
        data = json.loads(path.read_text())
        rows.append({
            "scenario": match.group(1), "concurrency": int(match.group(2)),
            "completed": pick(data, "completed"), "failed": pick(data, "failed"),
            "req_s": pick(data, "request_throughput"), "out_tok_s": pick(data, "output_throughput"),
            "ttft_p50": pick(data, "p50_ttft_ms", "median_ttft_ms"), "ttft_p99": pick(data, "p99_ttft_ms"),
            "itl_p50": pick(data, "p50_itl_ms", "median_itl_ms"), "itl_p99": pick(data, "p99_itl_ms"),
        })
    return sorted(rows, key=lambda row: (row["scenario"], row["concurrency"]))


def verdict(rows):
    """시나리오마다 TTFT, ITL, 둘 다를 만족하는 가장 큰 동시성. 하나도 없으면 None."""
    result = {}
    for scenario in sorted({row["scenario"] for row in rows}):
        levels = [row for row in rows if row["scenario"] == scenario and row["ttft_p99"] is not None]
        ttft = [row["concurrency"] for row in levels if row["ttft_p99"] <= TTFT_SLO_MS]
        itl = [row["concurrency"] for row in levels if row["itl_p99"] is not None and row["itl_p99"] <= ITL_SLO_MS]
        both = sorted(set(ttft) & set(itl))
        best = next((row for row in levels if both and row["concurrency"] == both[-1]), None)
        result[scenario] = {
            "ttft_only": max(ttft) if ttft else None, "itl_only": max(itl) if itl else None,
            "both": both[-1] if both else None,
            # 수준마다 표본이 적어(동시성의 8배, 최소 16건) 낮은 동시성이 탈락하고 높은 동시성이 통과하기도 한다.
            "passing_levels": both,
            "out_tok_s_at_both": best["out_tok_s"] if best else None,
            "req_s_at_both": best["req_s"] if best else None,
        }
    return result


def number(value, digits=1):
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else ""


def main():
    directory = sys.argv[1]
    rows = load(directory)
    if not rows:
        sys.exit(f"결과가 없습니다: {directory}/S*_c*.json")
    slo = verdict(rows)
    print(f"# SLO 하 처리량: {pathlib.Path(directory).name}\n")
    for scenario in sorted({row["scenario"] for row in rows}):
        print(f"## {scenario}: {SCENARIOS.get(scenario, '')}\n")
        print("| 동시성 | 완료 | req/s | 출력 tok/s | TTFT p50 (ms) | TTFT p99 (ms) | ITL p50 (ms) | ITL p99 (ms) | SLO |")
        print("|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for row in (r for r in rows if r["scenario"] == scenario):
            ok_ttft = row["ttft_p99"] is not None and row["ttft_p99"] <= TTFT_SLO_MS
            ok_itl = row["itl_p99"] is not None and row["itl_p99"] <= ITL_SLO_MS
            mark = "충족" if ok_ttft and ok_itl else "미충족(" + ", ".join(
                name for name, ok in (("TTFT", ok_ttft), ("ITL", ok_itl)) if not ok) + ")"
            print(f"| {row['concurrency']} | {number(row['completed'], 0)} | {number(row['req_s'], 2)} | "
                  f"{number(row['out_tok_s'])} | {number(row['ttft_p50'])} | {number(row['ttft_p99'])} | "
                  f"{number(row['itl_p50'])} | {number(row['itl_p99'])} | {mark} |")
        v = slo[scenario]
        print(f"\nTTFT만 만족하는 최대 동시성 {v['ttft_only'] or '없음'}, ITL만 만족하는 최대 동시성 {v['itl_only'] or '없음'}, "
              f"둘 다 만족하는 최대 동시성 {v['both'] or '없음'}\n")
    with open(pathlib.Path(directory) / "slo.json", "w") as out:
        json.dump({"slo": {"ttft_p99_ms": TTFT_SLO_MS, "itl_p99_ms": ITL_SLO_MS}, "verdict": slo, "rows": rows},
                  out, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
