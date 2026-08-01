"""get_current_user: the gate every application route sits behind."""

from datetime import timedelta
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.config import security_settings
from app.routers.dependencies import auth as auth_deps
from app.utils import generate_access_token


def creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture
def allow_all_jtis(monkeypatch):
    """Default to 'not blacklisted' so Redis is never contacted."""

    async def never_blacklisted(jti: str) -> bool:
        return False

    monkeypatch.setattr(auth_deps, "is_jti_blacklisted", never_blacklisted)


async def test_valid_token_yields_the_user_id(allow_all_jtis):
    user_id = uuid4()
    token = generate_access_token({"sub": str(user_id)})

    assert await auth_deps.get_current_user(creds(token)) == user_id


async def test_missing_credentials_are_rejected():
    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


async def test_undecodable_token_is_rejected(allow_all_jtis):
    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(creds("not-a-jwt"))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


async def test_expired_token_is_rejected(allow_all_jtis):
    token = generate_access_token({"sub": str(uuid4())}, expiry=timedelta(seconds=-1))

    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(creds(token))

    assert exc.value.status_code == 401


@pytest.mark.parametrize(
    "payload",
    [{"jti": "abc"}, {"sub": str(uuid4())}],
    ids=["missing-sub", "missing-jti"],
)
async def test_token_missing_required_claims_is_rejected(allow_all_jtis, payload):
    """A token without sub has no user; without jti it can never be revoked."""
    token = jwt.encode(
        payload,
        key=security_settings.JWT_SECRET,
        algorithm=security_settings.JWT_ALGORITHM,
    )

    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(creds(token))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token"


async def test_blacklisted_token_is_rejected(monkeypatch):
    """A logged-out token stays valid by signature, so the jti check must catch it."""
    token = generate_access_token({"sub": str(uuid4())})

    async def always_blacklisted(jti: str) -> bool:
        return True

    monkeypatch.setattr(auth_deps, "is_jti_blacklisted", always_blacklisted)

    with pytest.raises(HTTPException) as exc:
        await auth_deps.get_current_user(creds(token))

    assert exc.value.status_code == 401
    assert exc.value.detail == "Not authenticated"


async def test_only_the_logged_out_jti_is_blacklisted(monkeypatch):
    """Logging out one session must not invalidate the others."""
    revoked_token = generate_access_token({"sub": str(uuid4())})
    revoked_jti = jwt.decode(
        revoked_token,
        key=security_settings.JWT_SECRET,
        algorithms=[security_settings.JWT_ALGORITHM],
    )["jti"]

    live_user = uuid4()
    live_token = generate_access_token({"sub": str(live_user)})

    async def blacklist(jti: str) -> bool:
        return jti == revoked_jti

    monkeypatch.setattr(auth_deps, "is_jti_blacklisted", blacklist)

    assert await auth_deps.get_current_user(creds(live_token)) == live_user
    with pytest.raises(HTTPException):
        await auth_deps.get_current_user(creds(revoked_token))


async def test_returned_user_id_is_a_uuid_not_a_string(allow_all_jtis):
    """The sub claim is a string; callers compare it against UUID columns."""
    user_id = uuid4()
    result = await auth_deps.get_current_user(creds(generate_access_token({"sub": str(user_id)})))

    assert isinstance(result, UUID)
