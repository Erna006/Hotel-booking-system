from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from backend.core.config import conf
from backend.main import app
from backend.models import Role
from backend.middlewares.tokens import create_access_token, hash_password, verify_password
from backend.middlewares.auth import get_current_user, require_roles, require_booking_access


class FakeDB:
    def __init__(self, user):
        self.user = user

    async def fetch_one(self, query):
        return self.user


def test_password():
    encoded = hash_password("a long private password")
    assert verify_password("a long private password", encoded)
    assert not verify_password("incorrect", encoded)


async def test_token_and_live_roles():
    user = {"id": uuid4(), "role": "guest", "is_active": True}
    token = create_access_token(user["id"])
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    assert await get_current_user(creds, FakeDB(user)) is user
    with pytest.raises(HTTPException) as exc:
        await require_roles(Role.ADMIN)(user)
    assert exc.value.status_code == 403
    user["is_active"] = False
    with pytest.raises(HTTPException) as exc:
        await get_current_user(creds, FakeDB(user))
    assert exc.value.status_code == 401


@pytest.mark.parametrize("kind", ["expired", "wrong_audience", "missing_exp", "invalid_subject", "tampered"])
async def test_bad_tokens(kind):
    s = conf
    payload = {"sub": str(uuid4()), "iat": datetime.now(timezone.utc),
               "exp": datetime.now(timezone.utc) + timedelta(minutes=1), "iss": s.jwt_issuer, "aud": s.jwt_audience}
    if kind == "expired":
        payload["exp"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    if kind == "wrong_audience":
        payload["aud"] = "another-api"
    if kind == "missing_exp":
        del payload["exp"]
    if kind == "invalid_subject":
        payload["sub"] = "broken"
    token = jwt.encode(payload, s.jwt_secret if kind != "tampered" else "x" * 48, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), FakeDB(None))
    assert exc.value.status_code == 401


def test_ownership():
    owner = {"id": uuid4(), "role": "guest"}
    booking = {"guest_id": owner["id"]}
    require_booking_access(booking, owner)
    with pytest.raises(HTTPException) as exc:
        require_booking_access(booking, {"id": uuid4(), "role": "guest"})
    assert exc.value.status_code == 404
    require_booking_access(booking, {"id": uuid4(), "role": "receptionist"})


def test_health_and_error(monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr("backend.main.connect", AsyncMock())
    monkeypatch.setattr("backend.main.disconnect", AsyncMock())
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.headers["x-request-id"]
        response = client.get("/missing")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "http_404"
