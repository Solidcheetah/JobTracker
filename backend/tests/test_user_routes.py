"""/user endpoints."""

import pytest

from app.routers import user as user_router
from app.utils import generate_access_token


async def test_register_returns_only_public_fields(anon_client):
    response = await anon_client.post(
        "/user/register",
        json={"name": "Ada", "email": "ada@new.com", "password": "s3cret-pw"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body == {"name": "Ada", "email": "ada@new.com"}
    assert "password" not in body
    assert "password_hash" not in body


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Ada", "email": "not-an-email", "password": "pw"},
        {"name": "Ada", "email": "ada@new.com"},
        {"email": "ada@new.com", "password": "pw"},
        {},
    ],
    ids=["invalid-email", "no-password", "no-name", "empty"],
)
async def test_register_rejects_invalid_payloads(anon_client, payload):
    response = await anon_client.post("/user/register", json=payload)

    assert response.status_code == 422


async def test_login_returns_a_jwt(anon_client, user):
    response = await anon_client.post(
        "/user/login",
        json={"email": user.email, "password": "correct-horse"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["type"] == "jwt"
    assert body["token"]


async def test_login_with_a_bad_password_is_401(anon_client, user):
    response = await anon_client.post(
        "/user/login",
        json={"email": user.email, "password": "wrong-password"},
    )

    assert response.status_code == 401


async def test_register_then_login_works_end_to_end(anon_client):
    await anon_client.post(
        "/user/register",
        json={"name": "New", "email": "new@example.com", "password": "hunter2-long"},
    )

    response = await anon_client.post(
        "/user/login",
        json={"email": "new@example.com", "password": "hunter2-long"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["token"]


async def test_logout_blacklists_the_tokens_jti(anon_client, user, monkeypatch):
    blacklisted = {}

    async def fake_add(jti: str, exp: int):
        blacklisted[jti] = exp

    monkeypatch.setattr(user_router, "add_jti_to_blacklist", fake_add)
    token = generate_access_token({"sub": str(user.id)})

    response = await anon_client.post(
        "/user/logout", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200, response.text
    assert len(blacklisted) == 1


async def test_logout_with_an_invalid_token_is_401(anon_client, monkeypatch):
    async def fake_add(jti: str, exp: int):  # pragma: no cover - must not run
        raise AssertionError("should not blacklist an invalid token")

    monkeypatch.setattr(user_router, "add_jti_to_blacklist", fake_add)

    response = await anon_client.post(
        "/user/logout", headers={"Authorization": "Bearer garbage"}
    )

    assert response.status_code == 401
