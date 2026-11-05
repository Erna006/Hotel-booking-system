from typing import Annotated

import databases
import sqlalchemy
from fastapi import APIRouter, Depends

from backend.core.db import get_session

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
async def live():
    return {"status": "ok"}


@router.get("/ready")
async def ready(session: Annotated[databases.Database, Depends(get_session)]):
    await session.fetch_val(sqlalchemy.text("SELECT 1"))
    return {"status": "ok"}
