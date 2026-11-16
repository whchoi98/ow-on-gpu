"""BFF가 만드는 문구의 한국어와 영어 쌍.

요청 헤더 x-lang이 en이면 영어를, 그 밖에는 한국어를 쓴다. 화면의 한영 전환이 이 헤더를 보낸다.
Decider에 보내는 질문과 한국어 추론 지시문은 여기에 없다. 판단 결과와 추론 언어가 화면 언어에 따라
달라지지 않게 하려고 한 벌만 둔다(bff.py의 DECIDER_QUESTIONS, THINKING_IN_KOREAN).
"""
import re

FIELDS = re.compile(r"\{(\w+)\}")  # 문구 안의 채울 자리. 두 언어가 같은 자리를 가져야 한다.

TEXTS = {
    # 인증 실패(401). 로그에는 문구가 아닌 이 키를 남긴다.
    "auth.login_required": ("로그인이 필요합니다", "Sign-in is required"),
    "auth.bad_format": ("토큰 형식이 올바르지 않습니다", "The token is malformed"),
    "auth.keys_unavailable": ("서명 키를 받지 못했습니다", "Could not fetch the signing keys"),
    "auth.unknown_key": ("알 수 없는 서명 키입니다", "The signing key is unknown"),
    "auth.invalid": ("토큰이 유효하지 않습니다", "The token is not valid"),
    "auth.wrong_token": ("이 서비스용 액세스 토큰이 아닙니다", "This is not an access token for this service"),
    # 요청 오류(400, 422, 502)
    "request.messages_required": ("messages가 있는 JSON 본문이 필요합니다", "A JSON body with messages is required"),
    "request.bad_eval_model": ("x-eval-model은 gemma 또는 qwen이어야 합니다", "x-eval-model must be gemma or qwen"),
    "request.sensitive_image": ("민감 정보가 있는 요청은 Gemma로만 보내는데, Gemma는 이미지를 받지 않습니다",
                                "Requests with sensitive data go only to Gemma, and Gemma does not accept images"),
    "wake.failed": ("Qwen을 깨우지 못했습니다", "Could not wake Qwen"),
    # 주문 조회 도구: 모델에 주는 설명과 고정 데이터
    "order.tool": ("주문 번호로 주문 상태를 조회한다", "Look up the status of an order by its order number"),
    "order.tool.order_id": ("주문 번호. 예: A-1024", "Order number, for example A-1024"),
    "order.in_transit": ("배송 중", "In transit"),
    "order.delivered": ("배송 완료", "Delivered"),
    "order.carrier": ("한빛택배", "Hanbit Express"),
    "order.not_found": ("주문을 찾을 수 없음", "Order not found"),
    "tool.unknown": ("{name} 도구는 쓸 수 없습니다", "The {name} tool is not available"),
    # 웹 검색 도구: 모델에 주는 설명, 지시문, 검색하지 못했을 때의 결과
    "search.tool": ("웹을 검색해 최신 정보와 출처를 가져온다. 최근 일이나 확실하지 않은 사실을 답할 때 쓴다",
                    "Search the web for current information and sources. "
                    "Use it for recent events or facts you are not sure about"),
    "search.tool.query": ("검색어. 핵심어 위주로 200자 이하", "Search query. Keywords, at most 200 characters"),
    "search.instruction": (
        "오늘은 {today}입니다(한국 시간). 최근 일이나 확실하지 않은 사실은 web_search 도구로 검색한 뒤 답하세요. "
        "검색 결과를 근거로 쓴 문장 끝에는 그 결과의 번호를 [1], [2]처럼 붙이세요. "
        "검색 결과에 없는 내용에는 번호를 붙이지 말고, 주소(URL)를 지어내지 마세요. "
        "출처 목록은 화면이 따로 보여 주므로 답변 끝에 다시 적지 않습니다.",
        "Today is {today} (Korea time). For recent events or facts you are not sure about, search with the "
        "web_search tool before you answer. At the end of each sentence that relies on a search result, add the "
        "number of that result, like [1], [2]. Do not add numbers to content that is not in the search results, "
        "and do not make up URLs. The page shows the source list separately, so do not repeat it at the end of "
        "your answer."),
    "search.empty_query": ("검색어가 비어 있습니다", "The search query is empty"),
    "search.sensitive_query": ("검색어에 민감 정보가 있어 검색하지 않았습니다",
                               "The search query contains sensitive data, so no search was run"),
    "search.failed": ("검색에 실패했습니다. 검색 결과 없이 답하고, 검색하지 못했다고 알리세요",
                      "The search failed. Answer without search results and say that you could not search"),
}


def language(headers):
    return "en" if headers.get("x-lang") == "en" else "ko"


def text(key, lang, **values):
    template = TEXTS[key][1 if lang == "en" else 0]
    return template.format(**values) if values else template
