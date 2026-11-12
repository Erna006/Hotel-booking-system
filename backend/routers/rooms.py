from datetime import date
from decimal import Decimal
from uuid import UUID
import asyncpg
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from backend.core.errors import ApiError
from backend.models import Rooms
from backend.models.availability import overlapping_bookings
from backend.middlewares.auth import get_current_user, bearer
from backend.routers.common import DB, Admin, Limit, Offset, page
from backend.schemas import Room, AvailableRoom, StayPrice, RoomCreate, RoomPatch, Page, validate_dates

router = APIRouter(prefix='/rooms', tags=['rooms'])


def filters(min_price: Decimal | None = Query(None, ge=0),
            max_price: Decimal | None = Query(None, ge=0),
            room_type: str | None = None, capacity: int = Query(1, ge=1)):
    conditions = [Rooms.c.capacity >= capacity]
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(422, 'min_price exceeds max_price')
    if min_price is not None:
        conditions.append(Rooms.c.price_per_night >= min_price)
    if max_price is not None:
        conditions.append(Rooms.c.price_per_night <= max_price)
    if room_type:
        conditions.append(Rooms.c.room_type == room_type)
    return conditions


@router.get('', response_model=Page[Room])
async def rooms(request: Request, db: DB, limit: Limit = 20, offset: Offset = 0,
                include_inactive: bool = False, conditions=Depends(filters)):
    if include_inactive:
        user = await get_current_user(await bearer(request), db)
        if user['role'] != 'admin':
            raise HTTPException(403, 'Administrator required')
    else:
        conditions = [*conditions, Rooms.c.is_active.is_(True)]
    return await page(db, sa.select(Rooms).where(*conditions)
        .order_by(Rooms.c.number, Rooms.c.id), limit, offset)


def available_query(check_in: date, check_out: date, room_id: UUID | None = None,
                    conditions=Depends(filters)):
    try:
        validate_dates(check_in, check_out)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    overlaps = overlapping_bookings(Rooms.c.id, check_in, check_out).correlate(Rooms)
    query = sa.select(Rooms, (Rooms.c.price_per_night * (check_out - check_in).days)
        .label('total_amount')).where(*conditions, Rooms.c.is_active.is_(True),
        ~overlaps.exists())
    if room_id is not None:
        query = query.where(Rooms.c.id == room_id)
    return query


@router.get('/available', response_model=Page[AvailableRoom])
async def available(db: DB, limit: Limit = 20, offset: Offset = 0, query=Depends(available_query)):
    return await page(db, query.order_by(Rooms.c.number, Rooms.c.id), limit, offset)


@router.get('/available/prices', response_model=list[StayPrice])
async def available_prices(db: DB, query=Depends(available_query)):
    rooms = query.subquery()
    totals = sa.select(rooms.c.currency, sa.func.min(rooms.c.total_amount).label('total_amount'))
    return [dict(row) for row in await db.fetch_all(totals.group_by(rooms.c.currency).order_by(rooms.c.currency))]


@router.get('/{room_id}', response_model=Room)
async def room(room_id: UUID, db: DB):
    row = await db.fetch_one(sa.select(Rooms).where(Rooms.c.id == room_id, Rooms.c.is_active.is_(True)))
    if not row:
        raise HTTPException(404, 'Room not found')
    return dict(row)


@router.post('', status_code=201, response_model=Room)
async def create(body: RoomCreate, db: DB, admin: Admin):
    try:
        row = await db.fetch_one(Rooms.insert().values(**body.model_dump()).returning(*Rooms.c))
    except asyncpg.UniqueViolationError:
        raise ApiError(409, 'room_number_taken', 'Room number already exists')
    return dict(row)


@router.patch('/{room_id}', response_model=Room)
async def update(room_id: UUID, body: RoomPatch, db: DB, admin: Admin):
    try:
        async with db.transaction():
            row = await db.fetch_one(sa.select(Rooms).where(Rooms.c.id == room_id).with_for_update())
            if not row:
                raise HTTPException(404, 'Room not found')
            changes = body.model_dump(exclude_unset=True)
            if not changes:
                return dict(row)
            return dict(await db.fetch_one(Rooms.update().where(Rooms.c.id == room_id)
                .values(**changes).returning(*Rooms.c)))
    except asyncpg.UniqueViolationError:
        raise ApiError(409, 'room_number_taken', 'Room number already exists')
