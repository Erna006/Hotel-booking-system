from typing import Annotated
import databases
import sqlalchemy as sa
from fastapi import Depends, Query
from backend.core.db import get_session
from backend.middlewares.auth import get_current_user, require_roles, UserRecord
from backend.models import Role

DB = Annotated[databases.Database, Depends(get_session)]
User = Annotated[UserRecord, Depends(get_current_user)]
Admin = Annotated[UserRecord, Depends(require_roles(Role.ADMIN))]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


async def page(db, query, limit, offset):
    total = await db.fetch_val(sa.select(sa.func.count()).select_from(query.subquery()))
    rows = await db.fetch_all(query.limit(limit).offset(offset))
    return dict(items=[dict(row) for row in rows], total=total, limit=limit, offset=offset)
