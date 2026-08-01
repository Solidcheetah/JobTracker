"""Registration, lookup and login."""

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.user import UserCreateSchema
from app.services.user import password_hasher
from app.utils import decode_access_token


async def test_registering_stores_a_hash_not_the_password(user_service):
    payload = UserCreateSchema(name="Ada", email="ada@new.com", password="s3cret-pw")

    created = await user_service.add_user(payload)

    assert created.password_hash != "s3cret-pw"
    assert "s3cret-pw" not in created.password_hash
    assert password_hasher.verify("s3cret-pw", created.password_hash)


async def test_registering_persists_the_user(user_service):
    created = await user_service.add_user(
        UserCreateSchema(name="Ada", email="ada@new.com", password="pw")
    )

    assert await user_service.get_by_email("ada@new.com") is not None
    assert created.id is not None


async def test_two_users_with_the_same_password_get_different_hashes(user_service):
    """Per-user salting: identical passwords must not produce identical hashes."""
    first = await user_service.add_user(
        UserCreateSchema(name="A", email="a@x.com", password="same-password")
    )
    second = await user_service.add_user(
        UserCreateSchema(name="B", email="b@x.com", password="same-password")
    )

    assert first.password_hash != second.password_hash


async def test_get_user_returns_the_user(user_service, user):
    assert (await user_service.get_user(user.id)).id == user.id


async def test_get_user_raises_for_an_unknown_id(user_service):
    with pytest.raises(HTTPException) as exc:
        await user_service.get_user(uuid4())

    assert exc.value.status_code == 400


async def test_get_by_email_returns_none_when_absent(user_service):
    assert await user_service.get_by_email("nobody@example.com") is None


async def test_login_with_correct_password_returns_a_usable_token(user_service, user):
    token = await user_service.generate_user_token(user.email, "correct-horse")

    payload = decode_access_token(token)
    assert payload["sub"] == str(user.id)
    assert payload["name"] == user.name


@pytest.mark.parametrize(
    "email,password",
    [
        ("ada@example.com", "wrong-password"),
        ("nobody@example.com", "correct-horse"),
    ],
    ids=["wrong-password", "unknown-email"],
)
async def test_login_failures_are_401(user_service, user, email, password):
    with pytest.raises(HTTPException) as exc:
        await user_service.generate_user_token(email, password)

    assert exc.value.status_code == 401


async def test_login_error_does_not_reveal_which_field_was_wrong(user_service, user):
    """Same message either way, so the endpoint cannot be used to enumerate emails."""
    with pytest.raises(HTTPException) as wrong_pw:
        await user_service.generate_user_token(user.email, "wrong-password")
    with pytest.raises(HTTPException) as no_user:
        await user_service.generate_user_token("nobody@example.com", "whatever")

    assert wrong_pw.value.detail == no_user.value.detail
