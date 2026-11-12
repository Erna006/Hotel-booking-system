from datetime import datetime, timedelta, timezone

import asyncpg
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Response
from starlette.concurrency import run_in_threadpool
from backend.core.config import conf
from backend.core.errors import ApiError
from backend.models import Guests
from backend.models.refresh_tokens import RefreshTokens
from backend.middlewares.tokens import (
    hash_password, verify_password, create_access_token,
    new_refresh_token, hash_refresh_token)
from backend.routers.common import DB
from backend.schemas import Register, Login, Profile, Token, RefreshRequest

router = APIRouter(prefix='/auth', tags=['auth'])
# A real hash keeps unknown-account password checks on the same expensive path.
DUMMY_HASH = hash_password('unusable-dummy-login-password')


def _expires():
    return datetime.now(timezone.utc) + timedelta(days=conf.refresh_token_days)


@router.post('/register', status_code=201, response_model=Profile)
async def register(body: Register, db: DB):
    encoded = await run_in_threadpool(hash_password, body.password)
    try:
        row = await db.fetch_one(Guests.insert().values(
            email=body.email, full_name=body.full_name, password_hash=encoded,
            role='guest').returning(*Guests.c))
    except asyncpg.UniqueViolationError:
        raise ApiError(409, 'email_taken', 'Email is already registered')
    return dict(row)


@router.post('/login', response_model=Token)
async def login(body: Login, db: DB):
    user = await db.fetch_one(sa.select(Guests).where(Guests.c.email == body.email))
    valid = await run_in_threadpool(verify_password, body.password, user['password_hash'] if user else DUMMY_HASH)
    if not user or not valid or not user['is_active']:
        raise HTTPException(401, 'Invalid credentials', headers={'WWW-Authenticate': 'Bearer'})
    raw, digest = new_refresh_token()
    await db.execute(RefreshTokens.insert().values(
        guest_id=user['id'], token_hash=digest, expires_at=_expires()))
    return Token(access_token=create_access_token(user['id']), refresh_token=raw)


@router.post('/refresh', response_model=Token)
async def refresh(body: RefreshRequest, db: DB):
    now = datetime.now(timezone.utc)
    user_id = None
    raw = None
    async with db.transaction():
        row = await db.fetch_one(sa.select(RefreshTokens).where(
            RefreshTokens.c.token_hash == hash_refresh_token(body.refresh_token)).with_for_update())
        if row is not None and row['revoked_at'] is not None:
            # A rotated token was used again: treat as theft and revoke every session.
            await db.execute(RefreshTokens.update().where(
                RefreshTokens.c.guest_id == row['guest_id'],
                RefreshTokens.c.revoked_at.is_(None)).values(revoked_at=now))
        elif row is not None and row['expires_at'] > now:
            user = await db.fetch_one(sa.select(Guests).where(Guests.c.id == row['guest_id']))
            if user is not None and user['is_active']:
                await db.execute(RefreshTokens.update().where(
                    RefreshTokens.c.id == row['id']).values(revoked_at=now))
                raw, digest = new_refresh_token()
                await db.execute(RefreshTokens.insert().values(
                    guest_id=user['id'], token_hash=digest, expires_at=_expires()))
                user_id = user['id']
    # Raise after the block, otherwise the revocation above would be rolled back.
    if user_id is None:
        raise HTTPException(401, 'Invalid refresh token', headers={'WWW-Authenticate': 'Bearer'})
    return Token(access_token=create_access_token(user_id), refresh_token=raw)


@router.post('/logout', status_code=204)
async def logout(body: RefreshRequest, db: DB):
    await db.execute(RefreshTokens.update().where(
        RefreshTokens.c.token_hash == hash_refresh_token(body.refresh_token),
        RefreshTokens.c.revoked_at.is_(None)).values(revoked_at=datetime.now(timezone.utc)))
    return Response(status_code=204)
