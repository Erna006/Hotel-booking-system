"""Integration tests require a dedicated, migrated TEST_DATABASE_URL (asyncpg)."""
import asyncio
import os
from datetime import date
from uuid import uuid4

import asyncpg
import databases
import pytest
import pytest_asyncio
import sqlalchemy

from backend.models import Bookings, Guests, Payments, Rooms
from backend.models.availability import overlapping_bookings


@pytest_asyncio.fixture
async def records():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    async with databases.Database(url) as session:
        guest_id, room_id = uuid4(), uuid4()
        async with session.transaction():
            await session.execute(Guests.insert().values(
                id=guest_id, email=f"{guest_id}@example.com",
                password_hash="test-only", full_name="Test",
            ))
            await session.execute(Rooms.insert().values(
                id=room_id, number=str(room_id)[:20], room_type="standard",
                capacity=2, price_per_night=100,
            ))
        try:
            yield session, (guest_id, room_id)
        finally:
            async with session.transaction():
                booking_ids = sqlalchemy.select(Bookings.c.id).where(Bookings.c.room_id == room_id)
                await session.execute(Payments.delete().where(Payments.c.booking_id.in_(booking_ids)))
                await session.execute(Bookings.delete().where(Bookings.c.room_id == room_id))
                await session.execute(Rooms.delete().where(Rooms.c.id == room_id))
                await session.execute(Guests.delete().where(Guests.c.id == guest_id))


def booking(ids, start=10, end=12, status="pending"):
    return Bookings.insert().values(
        id=uuid4(), guest_id=ids[0], room_id=ids[1],
        check_in=date(2030, 1, start), check_out=date(2030, 1, end),
        total_amount=200, status=status,
    )


async def test_adjacent_cancelled_and_invalid_dates(records):
    session, ids = records
    await session.execute(booking(ids))
    await session.execute(booking(ids, 12, 14))
    await session.execute(booking(ids, 10, 12, "cancelled"))
    with pytest.raises(asyncpg.ExclusionViolationError):
        await session.execute(booking(ids, 11, 13))
    with pytest.raises(asyncpg.CheckViolationError):
        await session.execute(booking(ids, 15, 15))
    overlaps = await session.fetch_all(overlapping_bookings(ids[1], date(2030, 1, 11), date(2030, 1, 13)))
    assert len(overlaps) == 2


async def test_simultaneous_bookings(records):
    session, ids = records
    barrier = asyncio.Barrier(2)

    async def reserve():
        try:
            async with session.transaction():
                await session.execute("SET LOCAL lock_timeout = '10s'")
                await asyncio.wait_for(barrier.wait(), timeout=10)
                await session.execute(booking(ids))
            return "ok"
        except (asyncpg.ExclusionViolationError, asyncpg.DeadlockDetectedError) as exc:
            return exc.sqlstate

    results = await asyncio.wait_for(asyncio.gather(reserve(), reserve()), timeout=20)
    assert results.count("ok") == 1
    assert next(result for result in results if result != "ok") in {"23P01", "40P01"}
    count = await session.fetch_val(
        sqlalchemy.select(sqlalchemy.func.count()).select_from(Bookings).where(Bookings.c.room_id == ids[1])
    )
    assert count == 1


async def test_payment_uniqueness_and_rollback(records):
    session, ids = records
    booking_id = await session.fetch_val(booking(ids).returning(Bookings.c.id))
    key = uuid4()
    await session.execute(Payments.insert().values(
        booking_id=booking_id, idempotency_key=key, amount=200, status="succeeded",
    ))
    with pytest.raises(asyncpg.UniqueViolationError):
        async with session.transaction():
            await session.execute(Bookings.update().where(Bookings.c.id == booking_id).values(status="confirmed"))
            await session.execute(Payments.insert().values(
                booking_id=booking_id, idempotency_key=uuid4(), amount=200, status="succeeded",
            ))
    status = await session.fetch_val(sqlalchemy.select(Bookings.c.status).where(Bookings.c.id == booking_id))
    assert status == "pending"
    with pytest.raises(asyncpg.UniqueViolationError):
        await session.execute(Payments.insert().values(
            booking_id=booking_id, idempotency_key=key, amount=200, status="failed",
        ))


async def test_foreign_keys_and_reactivation(records):
    session, ids = records
    await session.execute(booking(ids))
    cancelled_id = await session.fetch_val(booking(ids, status="cancelled").returning(Bookings.c.id))
    with pytest.raises(asyncpg.ExclusionViolationError):
        await session.execute(Bookings.update().where(Bookings.c.id == cancelled_id).values(status="confirmed"))
    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await session.execute(Rooms.delete().where(Rooms.c.id == ids[1]))


async def test_application_lifecycle_and_database_auth(records, monkeypatch):
    import httpx
    from fastapi import HTTPException
    from fastapi.security import HTTPAuthorizationCredentials

    from backend.core import db
    from backend.core.config import conf
    from backend.main import app
    from backend.middlewares.auth import get_current_user, require_roles
    from backend.middlewares.tokens import create_access_token
    from backend.models import Role

    session, ids = records
    monkeypatch.setattr(conf, "postgres_url", os.environ["TEST_DATABASE_URL"])
    with pytest.raises(RuntimeError):
        db.get_session()

    async with app.router.lifespan_context(app):
        connected = db.get_session()
        assert await db.connect() is connected
        token = create_access_token(ids[0])
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials, connected)
        assert user["id"] == ids[0]
        assert user["role"] == "guest"

        await session.execute(Guests.update().where(Guests.c.id == ids[0]).values(role="admin"))
        user = await get_current_user(credentials, connected)
        assert await require_roles(Role.ADMIN)(user) is user

        await session.execute(Guests.update().where(Guests.c.id == ids[0]).values(is_active=False))
        with pytest.raises(HTTPException) as exc:
            await get_current_user(credentials, connected)
        assert exc.value.status_code == 401

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health/ready")
            assert response.status_code == 200
            assert response.headers["x-request-id"]

    assert not connected.is_connected
    with pytest.raises(RuntimeError):
        db.get_session()
    await db.disconnect()


async def test_database_conflict_becomes_http_409(records):
    import httpx
    from fastapi import FastAPI

    from backend.core.errors import register_error_handlers
    from backend.middlewares.request_logging import request_logging

    session, ids = records
    await session.execute(booking(ids))
    test_app = FastAPI()
    test_app.middleware("http")(request_logging)
    register_error_handlers(test_app)

    @test_app.post("/bookings")
    async def create_conflicting_booking():
        async with session.transaction():
            await session.execute(booking(ids))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/bookings")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "room_unavailable"
        assert response.json()["request_id"] == response.headers["x-request-id"]
