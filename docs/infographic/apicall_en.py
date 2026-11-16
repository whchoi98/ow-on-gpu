"""LLM API 호출 인포그래픽의 영어판. 카드의 위치는 apicall.py와 같고 글만 다르다."""
import apicall


def landscape(theme):
    apicall.use("en")
    try:
        return apicall.landscape(theme)
    finally:
        apicall.use("ko")
