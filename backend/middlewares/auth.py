from typing import Annotated, Any, Mapping

import databases
import jwt
import sqlalchemy
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.db import get_session
from backend.middlewares.tokens import read_access_token
from backend.models import Guests, Role

bearer = HTTPBearer(auto_error=False)
UserRecord = Mapping[str, Any]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[databases.Database, Depends(get_session)],
) -> UserRecord:
    unauthorized = HTTPException(
        status_code=401,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized

    try:
        user_id = read_access_token(credentials.credentials)
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized

    query = sqlalchemy.select(Guests).where(Guests.c.id == user_id)
    user = await session.fetch_one(query)
    if user is None or not user["is_active"]:
        raise unauthorized
    return user


def require_roles(*roles: Role):
    async def check(
        user: Annotated[UserRecord, Depends(get_current_user)],
    ) -> UserRecord:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return check


def require_booking_access(booking: Mapping[str, Any], user: UserRecord) -> None:
    if user["role"] == Role.GUEST and booking["guest_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Booking not found")
