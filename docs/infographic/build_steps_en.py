"""구축 단계와 아키텍처 인포그래픽의 영어판. 구조와 좌표는 build_steps.py와 같고 글만 다르다."""
import build_steps


def landscape(theme):
    build_steps.use("en")
    try:
        return build_steps.landscape(theme)
    finally:
        build_steps.use("ko")
