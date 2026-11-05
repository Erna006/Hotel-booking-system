from datetime import date
from uuid import UUID

import sqlalchemy

from backend.models.bookings import Bookings
from backend.models.enums import BookingStatus

BLOCKING_STATUSES = (BookingStatus.PENDING.value, BookingStatus.CONFIRMED.value)


def overlapping_bookings(room_id: UUID, check_in: date, check_out: date):
    """Shared availability query. PostgreSQL remains the final concurrency guard."""
    return sqlalchemy.select(Bookings).where(
        Bookings.c.room_id == room_id,
        Bookings.c.status.in_(BLOCKING_STATUSES),
        Bookings.c.check_in < check_out,
        Bookings.c.check_out > check_in,
    )
