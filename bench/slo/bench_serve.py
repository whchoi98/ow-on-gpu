"""`vllm bench serve`와 같은 벤치마크를 CLI 파서 없이 실행한다.

`vllm bench serve`는 시작할 때 `vllm serve`의 인자까지 함께 만들고, 그 과정에서 GPU가 없는 노드는
"Failed to infer device type"으로 멈춘다(vLLM v0.33.0, 2026-11-14). 부하 발생기는 GPU가 없는 측정 전용
노드에서 돌리므로 벤치마크 모듈(vllm.benchmarks.serve)을 직접 부른다. 인자와 측정 코드는 같다.
"""
import argparse

from vllm.benchmarks.serve import add_cli_args, main

parser = argparse.ArgumentParser()
add_cli_args(parser)
main(parser.parse_args())
