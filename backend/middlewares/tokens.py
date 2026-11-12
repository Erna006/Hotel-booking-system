import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from backend.core.config import conf

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hasher.verify(password, encoded)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=conf.access_token_minutes),
        "iss": conf.jwt_issuer,
        "aud": conf.jwt_audience,
    }
    return jwt.encode(payload, conf.jwt_secret, algorithm="HS256")


def read_access_token(token: str) -> UUID:
    payload = jwt.decode(
        token,
        conf.jwt_secret,
        algorithms=["HS256"],
        issuer=conf.jwt_issuer,
        audience=conf.jwt_audience,
        options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )
    return UUID(payload["sub"])
def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(48)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> str:
    # Random 384-bit token: a fast hash is enough (no brute force), unlike passwords.
    return hashlib.sha256(raw.encode()).hexdigest()
