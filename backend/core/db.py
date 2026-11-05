import typing

import databases
import sqlalchemy

from backend.core.config import conf

metadata = sqlalchemy.MetaData()
_SESSION: typing.Optional[databases.Database] = None


async def get_connected_session() -> databases.Database:
    session = databases.Database(url=conf.postgres_url)
    await session.connect()
    return session


async def connect() -> databases.Database:
    global _SESSION

    if _SESSION is None:
        _SESSION = await get_connected_session()
    return _SESSION


def get_session() -> databases.Database:
    if _SESSION is None or not _SESSION.is_connected:
        raise RuntimeError("Database session not initialized")
    return _SESSION


async def disconnect() -> None:
    global _SESSION

    if _SESSION is not None:
        if _SESSION.is_connected:
            await _SESSION.disconnect()
        _SESSION = None
