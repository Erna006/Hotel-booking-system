from uuid import UUID
from decimal import Decimal
from backend.core.errors import ApiError
import sqlalchemy as sa
from fastapi import APIRouter, HTTPException
from backend.models import Rooms, Bookings
from backend.models.availability import overlapping_bookings
from backend.middlewares.auth import require_booking_access
from backend.routers.common import DB, User, Limit, Offset, page
from backend.schemas import Booking, BookingCreate, Page

router = APIRouter(prefix='/bookings', tags=['bookings'])


async def load_booking(db, booking_id, user, lock=False):
    query = sa.select(Bookings).where(Bookings.c.id == booking_id)
    if lock:
        query = query.with_for_update()
    booking = await db.fetch_one(query)
    if not booking:
        raise HTTPException(404, 'Booking not found')
    require_booking_access(booking, user)
    return booking


@router.post('', status_code=201, response_model=Booking)
async def create(body: BookingCreate, db: DB, user: User):
    async with db.transaction():
        room = await db.fetch_one(sa.select(Rooms).where(Rooms.c.id == body.room_id).with_for_update())
        if not room or not room['is_active']:
            raise HTTPException(404, 'Room not found')
        if await db.fetch_one(overlapping_bookings(body.room_id, body.check_in, body.check_out)):
            raise ApiError(409, 'room_unavailable', 'Room unavailable for these dates')
        amount = room['price_per_night'] * (body.check_out - body.check_in).days
        if amount > Decimal('9999999999.99'):
            raise HTTPException(422, 'Booking amount exceeds supported limit')
        return dict(await db.fetch_one(Bookings.insert().values(
            **body.model_dump(), guest_id=user['id'], total_amount=amount,
            currency=room['currency'], status='pending').returning(*Bookings.c)))


@router.get('', response_model=Page[Booking])
async def bookings(db: DB, user: User, limit: Limit = 20, offset: Offset = 0):
    query = sa.select(Bookings)
    if user['role'] == 'guest':
        query = query.where(Bookings.c.guest_id == user['id'])
    return await page(db, query.order_by(Bookings.c.created_at.desc(), Bookings.c.id), limit, offset)


@router.get('/{booking_id}', response_model=Booking)
async def booking(booking_id: UUID, db: DB, user: User):
    return dict(await load_booking(db, booking_id, user))


@router.post('/{booking_id}/cancel', response_model=Booking)
async def cancel(booking_id: UUID, db: DB, user: User):
    async with db.transaction():
        await load_booking(db, booking_id, user, lock=True)
        return dict(await db.fetch_one(Bookings.update().where(Bookings.c.id == booking_id)
            .values(status='cancelled').returning(*Bookings.c)))
