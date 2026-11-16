"""요청 경로 인포그래픽의 영어판. 구조와 좌표는 flow.py와 같고 글만 다르다."""
import flow


def landscape(theme):
    flow.use("en")
    try:
        return flow.landscape(theme)
    finally:
        flow.use("ko")


def live_map(theme="light"):
    flow.use("en")
    try:
        return flow.live_map(theme)
    finally:
        flow.use("ko")
