#!/usr/bin/env python3
"""Grafana 대시보드 JSON(serving.json)을 만든다. 패널과 쿼리를 이 파일에서 고치고 다시 실행한다.

  python3 build.py            serving.json을 다시 쓴다
  python3 build.py --queries  쿼리만 한 줄씩 출력한다(check_queries.py가 AMP에 보내 확인한다)

지표 이름은 2026-11-14에 실제 파드의 /metrics에서 확인한 것이다(vLLM v0.33.0, llm-d-router v1.0.0, agentgateway v1.7.0).
`model` 라벨은 수집기(k8s/observability/prometheus.yml)가 붙인다. 값은 gemma, qwen이다.
"""
import json
import pathlib
import sys

RATE = "$__rate_interval"
MODEL = 'model=~"$model"'


def quantile(q, metric, by="model", selector=MODEL):
    return f"histogram_quantile({q}, sum by (le, {by}) (rate({metric}_bucket{{{selector}}}[{RATE}])))"


# (제목, 단위, [(범례, 쿼리)], 설명)
ROWS = [
    ("모델별 지연과 부하", [
        ("TTFT", "s", [
            ("{{model}} p50", quantile(0.5, "vllm:time_to_first_token_seconds")),
            ("{{model}} p95", quantile(0.95, "vllm:time_to_first_token_seconds")),
            ("{{model}} p99", quantile(0.99, "vllm:time_to_first_token_seconds")),
        ], "vLLM이 요청을 받은 뒤 첫 토큰을 내기까지의 시간. SLO는 p99 500ms"),
        ("ITL", "s", [
            ("{{model}} p50", quantile(0.5, "vllm:inter_token_latency_seconds")),
            ("{{model}} p99", quantile(0.99, "vllm:inter_token_latency_seconds")),
        ], "토큰 사이의 간격. SLO는 p99 50ms"),
        ("대기 요청 수", "short", [
            ("{{model}} 대기", f"sum by (model) (vllm:num_requests_waiting{{{MODEL}}})"),
            ("{{model}} 실행 중", f"sum by (model) (vllm:num_requests_running{{{MODEL}}})"),
        ], "엔진의 대기열과 실행 중인 요청 수"),
        ("KV 캐시 사용률", "percentunit", [
            ("{{model}}", f"max by (model) (vllm:kv_cache_usage_perc{{{MODEL}}})"),
        ], "1에 가까우면 새 요청이 대기하거나 실행 중인 요청이 선점된다"),
        ("MTP 수락률", "percentunit", [
            ("{{model}} 전체", f"sum by (model) (rate(vllm:spec_decode_num_accepted_tokens_total{{{MODEL}}}[{RATE}])) "
                             f"/ sum by (model) (rate(vllm:spec_decode_num_draft_tokens_total{{{MODEL}}}[{RATE}]))"),
            ("{{model}} 위치 {{position}}",
             f"sum by (model, position) (rate(vllm:spec_decode_num_accepted_tokens_per_pos_total{{{MODEL}}}[{RATE}])) "
             f"/ on (model) group_left sum by (model) (rate(vllm:spec_decode_num_drafts_total{{{MODEL}}}[{RATE}]))"),
        ], "드래프트 토큰 중 수락된 비율. speculative decoding을 켠 Qwen에만 값이 있다"),
        ("출력 토큰 처리량", "short", [
            ("{{model}}", f"sum by (model) (rate(vllm:generation_tokens_total{{{MODEL}}}[{RATE}]))"),
        ], "초당 생성 토큰 수"),
        ("대기열에서 보낸 시간", "s", [
            ("{{model}} p50", quantile(0.5, "vllm:request_queue_time_seconds")),
            ("{{model}} p99", quantile(0.99, "vllm:request_queue_time_seconds")),
        ], "요청이 엔진의 대기열에 머문 시간"),
        ("선점과 거절", "short", [
            ("{{model}} 선점", f"sum by (model) (rate(vllm:num_preemptions_total{{{MODEL}}}[{RATE}]))"),
            ("{{model}} 거절", f"sum by (model) (rate(vllm:admission_rejections_total{{{MODEL}}}[{RATE}]))"),
        ], "KV 캐시가 모자라 실행 중인 요청을 밀어낸 횟수와 엔진이 받지 않은 요청 수(초당)"),
        ("sleep 상태", "short", [
            ("{{model}} {{sleep_state}}", f"max by (model, sleep_state) (vllm:engine_sleep_state{{{MODEL}}})"),
        ], "1인 상태가 지금 상태다. awake가 아니면 잠든 것이다"),
    ]),
    ("EPP (풀별)", [
        ("EPP가 본 TTFT", "s", [
            ("{{pool}} p50", quantile(0.5, "llm_d_epp_request_ttft_seconds", by="pool", selector='job="epp"')),
            ("{{pool}} p99", quantile(0.99, "llm_d_epp_request_ttft_seconds", by="pool", selector='job="epp"')),
        ], "EPP가 요청을 받은 뒤 응답의 첫 조각을 보기까지의 시간"),
        ("우선순위별 요청 수", "reqps", [
            ("{{pool}} priority {{priority}}", f'sum by (pool, priority) (rate(llm_d_epp_request_total{{job="epp"}}[{RATE}]))'),
            ("{{pool}} 오류 {{error_code}}",
             f'sum by (pool, error_code) (rate(llm_d_epp_request_error_total{{job="epp"}}[{RATE}]))'),
        ], "InferenceObjective의 priority별 초당 요청 수와 오류"),
        ("EPP가 본 대기열과 KV 캐시", "short", [
            ("{{pool}} 대기열", 'max by (pool) (llm_d_epp_average_queue_size{job="epp"})'),
            ("{{pool}} KV 캐시", 'max by (pool) (llm_d_epp_average_kv_cache_utilization{job="epp"})'),
            ("{{pool}} 준비된 엔드포인트", 'max by (pool) (llm_d_epp_ready_endpoints{job="epp"})'),
        ], "EPP가 vLLM 지표에서 읽은 값. 포화 판단의 근거다"),
        ("스케줄링 시간", "s", [
            ("{{pool}} p99", f'histogram_quantile(0.99, sum by (le, pool) (rate(llm_d_epp_scheduler_e2e_duration_seconds_bucket{{job="epp"}}[{RATE}])))'),
        ], "EPP가 엔드포인트를 고르는 데 쓴 시간"),
    ]),
    ("게이트웨이", [
        ("경로별 요청 수", "reqps", [
            ("{{route}} {{status}}", f'sum by (route, status) (rate(agentgateway_requests_total{{job="gateway"}}[{RATE}]))'),
        ], "HTTPRoute와 상태 코드별 초당 요청 수. 429는 포화 때 거절된 배치 요청이다"),
        ("요청 처리 시간", "s", [
            ("{{route}} p50", f'histogram_quantile(0.5, sum by (le, route) (rate(agentgateway_request_duration_seconds_bucket{{job="gateway"}}[{RATE}])))'),
            ("{{route}} p99", f'histogram_quantile(0.99, sum by (le, route) (rate(agentgateway_request_duration_seconds_bucket{{job="gateway"}}[{RATE}])))'),
        ], "게이트웨이가 요청을 받은 뒤 응답을 끝내기까지의 시간"),
    ]),
]


def queries():
    for _, panels in ROWS:
        for title, _, targets, _ in panels:
            for legend, expr in targets:
                yield title, legend, expr


def dashboard():
    panels, panel_id, y = [], 1, 0
    for row_title, row_panels in ROWS:
        panels.append({"id": panel_id, "type": "row", "title": row_title, "collapsed": False,
                       "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}})
        panel_id += 1
        y += 1
        for index, (title, unit, targets, description) in enumerate(row_panels):
            panels.append({
                "id": panel_id, "type": "timeseries", "title": title, "description": description,
                "datasource": {"type": "prometheus", "uid": "${datasource}"},
                "gridPos": {"h": 8, "w": 8, "x": (index % 3) * 8, "y": y + (index // 3) * 8},
                "fieldConfig": {"defaults": {"unit": unit, "min": 0,
                                             "custom": {"lineWidth": 1, "fillOpacity": 0, "showPoints": "never",
                                                        "spanNulls": False}},
                                "overrides": []},
                "options": {"legend": {"displayMode": "table", "placement": "bottom", "calcs": ["lastNotNull", "max"]},
                            "tooltip": {"mode": "multi", "sort": "desc"}},
                "targets": [{"refId": chr(ord("A") + i), "expr": expr, "legendFormat": legend,
                             "datasource": {"type": "prometheus", "uid": "${datasource}"}}
                            for i, (legend, expr) in enumerate(targets)],
            })
            panel_id += 1
        y += ((len(row_panels) + 2) // 3) * 8
    return {
        "uid": "ow-on-gpu-serving", "title": "ow-on-gpu 서빙", "tags": ["ow-on-gpu", "vllm"],
        "schemaVersion": 39, "version": 1, "editable": True, "graphTooltip": 1,
        "time": {"from": "now-1h", "to": "now"}, "refresh": "10s", "timezone": "browser",
        "templating": {"list": [
            {"name": "datasource", "label": "데이터 소스", "type": "datasource", "query": "prometheus"},
            {"name": "model", "label": "모델", "type": "query", "datasource": {"type": "prometheus", "uid": "${datasource}"},
             "query": {"query": "label_values(vllm:num_requests_running, model)", "refId": "model"},
             "refresh": 2, "includeAll": True, "multi": True, "current": {"text": "All", "value": "$__all"}},
        ]},
        "panels": panels,
    }


if __name__ == "__main__":
    if "--queries" in sys.argv:
        for title, legend, expr in queries():
            print(json.dumps({"panel": title, "legend": legend, "expr": expr}, ensure_ascii=False))
    else:
        target = pathlib.Path(__file__).with_name("serving.json")
        target.write_text(json.dumps(dashboard(), ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {target} ({len(list(queries()))} queries)")
