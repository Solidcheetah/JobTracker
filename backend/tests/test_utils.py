"""Token generation and decoding."""

from datetime import timedelta
from uuid import uuid4

import jwt
import pytest

from app.config import security_settings
from app.utils import decode_access_token, generate_access_token


def test_token_round_trips_its_payload():
    user_id = str(uuid4())
    token = generate_access_token({"sub": user_id, "name": "Ada"})

    payload = decode_access_token(token)

    assert payload is not None
    assert payload["sub"] == user_id
    assert payload["name"] == "Ada"


def test_every_token_gets_a_unique_jti():
    """Logout blacklists by jti, so two tokens must never share one."""
    first = decode_access_token(generate_access_token({"sub": "a"}))
    second = decode_access_token(generate_access_token({"sub": "a"}))

    assert first["jti"] != second["jti"]


def test_token_carries_an_expiry():
    payload = decode_access_token(generate_access_token({"sub": "a"}))

    assert "exp" in payload


def test_expired_token_is_rejected():
    token = generate_access_token({"sub": "a"}, expiry=timedelta(seconds=-30))

    assert decode_access_token(token) is None


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode(
        {"sub": "attacker", "jti": "x"},
        key="not-the-real-secret",
        algorithm=security_settings.JWT_ALGORITHM,
    )

    assert decode_access_token(forged) is None


@pytest.mark.parametrize(
    "token",
    ["", "garbage", "a.b.c", "Bearer sometoken"],
    ids=["empty", "not-a-jwt", "three-empty-segments", "header-value"],
)
def test_malformed_tokens_return_none_rather_than_raising(token):
    assert decode_access_token(token) is None


def test_tampered_payload_is_rejected():
    token = generate_access_token({"sub": "ada"})
    header, _, signature = token.split(".")
    swapped = jwt.utils.base64url_encode(b'{"sub":"attacker"}').decode()

    assert decode_access_token(f"{header}.{swapped}.{signature}") is None
