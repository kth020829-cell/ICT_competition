"""식별자 생성.

`analysis_01XYZ...` 형태의 정렬 가능한 id를 만든다. 앞자리가 시간이라
문자열 정렬만으로 생성 순서가 유지되고, 로그를 시간순으로 훑기 쉽다.
"""

import secrets
import time

#: Crockford base32 — 사람이 눈으로 읽고 옮겨 적기 쉬운 문자만 남긴 집합.
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        value, rem = divmod(value, 32)
        chars.append(_ALPHABET[rem])
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    """`{prefix}_{시간 10자}{난수 6자}` 형태의 id를 만든다."""
    timestamp = _encode(int(time.time() * 1000), 10)
    randomness = "".join(secrets.choice(_ALPHABET) for _ in range(6))
    return f"{prefix}_{timestamp}{randomness}"


def new_analysis_id() -> str:
    return new_id("analysis")


def new_scan_session_id() -> str:
    return new_id("scan")
