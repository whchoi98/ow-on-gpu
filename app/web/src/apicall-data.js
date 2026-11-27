// docs/infographic/apicall.py가 만든 파일이다. 직접 고치지 말고 docs/infographic/build.sh로 다시 만든다.
export default {
  "regions": {
    "1": {
      "left": 2.5,
      "top": 13.704,
      "width": 22.344,
      "height": 29.259
    },
    "2": {
      "left": 26.719,
      "top": 13.704,
      "width": 22.344,
      "height": 29.259
    },
    "3": {
      "left": 50.938,
      "top": 13.704,
      "width": 22.344,
      "height": 29.259
    },
    "4": {
      "left": 75.156,
      "top": 13.704,
      "width": 22.344,
      "height": 29.259
    },
    "5": {
      "left": 16.875,
      "top": 45.185,
      "width": 80.625,
      "height": 27.778
    },
    "6": {
      "left": 16.875,
      "top": 75.185,
      "width": 25.625,
      "height": 21.481
    },
    "7": {
      "left": 44.375,
      "top": 75.185,
      "width": 25.625,
      "height": 21.481
    },
    "8": {
      "left": 71.875,
      "top": 75.185,
      "width": 25.625,
      "height": 21.481
    },
    "search": {
      "left": 2.5,
      "top": 45.185,
      "width": 13.021,
      "height": 51.481
    }
  },
  "measured": {
    "gemma": {
      "name": "Gemma 4 31B",
      "edge": 1.8,
      "cloudfront": 5.0,
      "alb": 1.6,
      "bff": 0.1,
      "decide": 0.1,
      "gateway": 9.7,
      "vllm_ttft": 63.2,
      "queue": 0.0,
      "prefill": 58.8,
      "headers": 19.8,
      "first_content": 81.9,
      "s1": {
        "ttft": 81.3,
        "ttft_p99": 86.6,
        "itl": 54.0,
        "itl_p99": 57.7,
        "tpot": 53.91,
        "e2e": 6927.8,
        "tokens_per_s": 18.5,
        "running_max": 45
      },
      "s4_ttft_p99": 1093.2,
      "weights_gib": 30.63,
      "kv_gib": 5.37,
      "kv_tokens": 34052,
      "max_model_len": 16384
    },
    "qwen": {
      "name": "Qwen3.8-27B",
      "edge": 1.9,
      "cloudfront": 5.0,
      "alb": 1.6,
      "bff": 12.8,
      "decide": 0.1,
      "wake_check": 12.8,
      "gateway": 8.4,
      "vllm_ttft": 147.6,
      "queue": 0.0,
      "prefill": 144.4,
      "headers": 32.4,
      "first_content": 177.5,
      "s1": {
        "ttft": 167.6,
        "ttft_p99": 210.4,
        "itl": 69.8,
        "itl_p99": 74.3,
        "tpot": 26.64,
        "e2e": 3554.7,
        "tokens_per_s": 32.5,
        "running_max": 3
      },
      "weights_gib": 34.39,
      "kv_gib": 2.46,
      "kv_tokens": 42780,
      "max_model_len": 32768
    },
    "device_gib": 44.39,
    "epp_ms": 0.03,
    "decider_ms": [
      144,
      160
    ],
    "priority_ttft_ms": {
      "none": 30895,
      "engine": 190
    },
    "fixed_cost_usd_per_hour": 11.35,
    "s1_output_tokens": 128,
    "search": {
      "region": "us-east-1",
      "results": 5,
      "text_chars": 1200,
      "max_rounds": 3,
      "ms": [
        481,
        1065
      ],
      "input_tokens": {
        "gemma": 2606,
        "qwen": 4328
      },
      "searches": {
        "gemma": 1,
        "qwen": 2
      },
      "qwen_round_s": [
        2.6,
        12.1
      ],
      "usd_per_1000": 7,
      "quota_per_s": 10,
      "bff_ms": [
        485,
        662
      ],
      "bff_median_ms": 568,
      "bff_n": 8
    }
  },
  "derived": {
    "gemma": {
      "entry": 8.4,
      "routing": 9.8,
      "share": 77
    },
    "qwen": {
      "entry": 8.5,
      "routing": 21.2,
      "share": 83
    }
  }
};
