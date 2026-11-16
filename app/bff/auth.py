"""Cognito 사용자 풀이 발급한 액세스 토큰을 검증한다.

서명 키(JWKS)는 사용자 풀의 공개 주소에서 받아 메모리에 둔다. AWS 자격 증명은 쓰지 않는다.
"""
import time

import jwt
from aiohttp import ClientTimeout

# 모르는 kid가 올 때마다 키를 다시 받으면 임의의 토큰으로 Cognito 호출을 유발할 수 있다.
JWKS_REFRESH_SECONDS = 60


class AuthError(Exception):
    """인증 실패. 인자는 texts.TEXTS의 키다. 문구는 요청의 언어에 맞춰 호출한 쪽이 고른다."""


class CognitoVerifier:
    def __init__(self, issuer, client_id):
        """issuer는 https://cognito-idp.<리전>.amazonaws.com/<사용자 풀 ID> 형식이다."""
        self.issuer = issuer.rstrip("/")
        self.client_id = client_id
        self.keys = {}
        self.fetched_at = None

    async def refresh(self, http):
        self.fetched_at = time.monotonic()
        async with http.get(self.issuer + "/.well-known/jwks.json", timeout=ClientTimeout(total=5)) as response:
            response.raise_for_status()
            jwks = await response.json(content_type=None)
        self.keys = {key["kid"]: jwt.PyJWK.from_dict(key).key for key in jwks["keys"] if key.get("kty") == "RSA"}

    async def verify(self, http, token):
        """검증한 클레임을 돌려준다. 통과하지 못하면 AuthError를 낸다."""
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError as error:
            raise AuthError("auth.bad_format") from error
        if kid not in self.keys and (self.fetched_at is None
                                     or time.monotonic() - self.fetched_at > JWKS_REFRESH_SECONDS):
            try:
                await self.refresh(http)
            except Exception as error:
                raise AuthError("auth.keys_unavailable") from error
        if kid not in self.keys:
            raise AuthError("auth.unknown_key")
        try:
            # 알고리즘을 RS256으로 고정한다. 토큰 머리말의 alg 값은 믿지 않는다.
            claims = jwt.decode(token, self.keys[kid], algorithms=["RS256"], issuer=self.issuer,
                                options={"require": ["exp", "iss"]})
        except jwt.PyJWTError as error:
            raise AuthError("auth.invalid") from error
        # 액세스 토큰에는 aud가 없고 client_id가 있다. ID 토큰은 받지 않는다.
        if claims.get("token_use") != "access" or claims.get("client_id") != self.client_id:
            raise AuthError("auth.wrong_token")
        return claims
