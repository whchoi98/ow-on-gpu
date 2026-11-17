"""요청을 어느 모델로 보낼지 정하는 규칙. HTTP와 무관한 순수 함수만 둔다."""
import re
from dataclasses import dataclass, field, replace

MODELS = {"gemma": "gemma-4-31b", "qwen": "qwen38-27b"}

# 업무 종류별 배정(AGENT.md의 "업무와 모델 배정"). 우선순위가 None이면 요청이 정한다.
TASKS = {
    "support": ("gemma", "interactive"),
    "translate": ("gemma", "batch"),
    "summarize": ("gemma", "batch"),
    "vision": ("qwen", None),
    "ocr": ("qwen", None),
    "coding": ("qwen", "interactive"),
}

RRN = re.compile(r"(?<!\d)\d{6}[- ]?[1-8]\d{6}(?!\d)")
CARD = re.compile(r"(?<!\d)\d(?:[ -]?\d){12,18}(?!\d)")


def luhn_valid(digits):
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n > 4 else n * 2
        total += n
    return total % 10 == 0


def sensitive_kind(text):
    """형식이 정해진 민감 정보의 종류. 주민등록번호면 rrn, 카드번호면 card, 없으면 None."""
    if RRN.search(text):
        return "rrn"
    if any(luhn_valid(re.sub(r"[ -]", "", m.group())) for m in CARD.finditer(text)):
        return "card"
    return None


def has_sensitive(text):
    """형식이 정해진 민감 정보(주민등록번호, 카드번호)가 있는지. Decider보다 먼저 적용한다."""
    return sensitive_kind(text) is not None


@dataclass(frozen=True)
class Decision:
    model: str        # gemma 또는 qwen
    priority: str     # interactive 또는 batch
    thinking: bool
    sensitive: bool
    source: str       # rule, task, attachment, decider, fallback, eval
    # 이렇게 정한 근거. 응답 헤더 x-bff-reason으로 나간다. 결정이 같은지 견줄 때는 보지 않는다.
    reason: dict = field(default_factory=dict, compare=False)

    @property
    def model_name(self):
        return MODELS[self.model]

    @property
    def objective(self):
        return f"{self.model}-{self.priority}"


# Decider가 답하지 않거나 신뢰도가 낮을 때: Gemma, thinking off, 민감 정보 있음.
# 모델 선택의 신뢰도만 낮은 경우는 from_decider가 민감 정보 여부를 Decider의 판단대로 둔다.
FALLBACK = Decision("gemma", "interactive", False, True, "fallback", {"why": "decider_unavailable"})


def message_text(messages):
    parts = []
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts += [p.get("text", "") for p in content if p.get("type") == "text"]
    return "\n".join(parts)


def has_image(messages):
    return any(
        part.get("type") in ("image_url", "input_image")
        for message in messages if isinstance(message.get("content"), list)
        for part in message["content"]
    )


def from_decider(answers, min_confidence):
    """Decider의 세 판단(route, policy, thinking)을 결정으로 바꾼다. 신뢰도가 낮으면 FALLBACK.

    모델 선택만 불확실하고 개인정보가 없다는 판단이 기준 이상이면 기본 모델로 보내되 민감 정보 요청으로 다루지 않는다.
    일반 질문은 route의 두 선택지 어디에도 뚜렷이 들지 않아 신뢰도가 낮게 나오는데, 그 이유만으로 웹 검색까지
    막지 않기 위해서다(2026-11-17).
    """
    try:
        route, policy, thinking = answers["route"], answers["policy"]["noul"], answers["thinking"]["noul"]
        choice, confidence = route["choice"], route["confidence"]
    except (KeyError, TypeError):
        return replace(FALLBACK, reason={"why": "decider_unavailable", "detail": "bad_response"})
    judged = {"route": choice, "route_confidence": round(confidence, 3), "policy": round(policy, 3),
              "thinking": round(thinking, 3), "min_confidence": min_confidence}
    # 예/아니오 판단의 신뢰도는 확률이 0.5에서 떨어진 정도로 본다.
    policy_confidence = abs(policy - 0.5) * 2
    low = [name for name, short in (("route", choice not in MODELS or confidence < min_confidence),
                                    ("policy", policy_confidence < min_confidence)) if short]
    if low:
        return replace(FALLBACK, sensitive=low != ["route"] or policy >= 0.5,
                       reason={"why": "low_confidence", "low": low,
                               "policy_confidence": round(policy_confidence, 3), **judged})
    sensitive = policy >= 0.5
    return Decision("gemma" if sensitive else choice, "interactive", thinking >= 0.5, sensitive, "decider", judged)


def decide_without_decider(messages, task, priority):
    """규칙만으로 정해지면 결정을, Decider가 필요하면 None을 돌려준다."""
    pattern = sensitive_kind(message_text(messages))
    if pattern:
        default = TASKS.get(task, (None, None))[1]
        return Decision("gemma", priority or default or "interactive", False, True, "rule", {"pattern": pattern})
    if task in TASKS:
        model, default = TASKS[task]
        return Decision(model, priority or default or "interactive", False, False, "task", {"task": task})
    if has_image(messages):
        return Decision("qwen", priority or "interactive", False, False, "attachment", {"attachment": "image"})
    return None


def for_evaluation(messages, model):
    """성능 평가 요청. 요청한 모델로 보내되 데이터 정책 규칙이 먼저다.

    두 모델을 같은 조건으로 견주려고 우선순위는 interactive, thinking은 끔으로 고정한다.
    """
    pattern = sensitive_kind(message_text(messages))
    if pattern:
        return Decision("gemma", "interactive", False, True, "rule", {"pattern": pattern, "requested": model})
    return Decision(model, "interactive", False, False, "eval", {"requested": model})


def with_sensitive(decision, pattern):
    """세션 도중 민감 정보가 나오면 그 뒤로는 Gemma로만 보낸다."""
    return replace(decision, model="gemma", sensitive=True, source="rule",
                   reason={"pattern": pattern, "during_session": True})
