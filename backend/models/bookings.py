import sqlalchemy
from sqlalchemy.dialects.postgresql import ExcludeConstraint

from backend.core import db


Bookings = sqlalchemy.Table(
    'bookings',
    db.metadata,
    sqlalchemy.Column(
        'id',
        sqlalchemy.Uuid(),
        primary_key=True,
        server_default=sqlalchemy.text("gen_random_uuid()"),
        nullable=False,
    ),
    sqlalchemy.Column(
        'guest_id',
        sqlalchemy.Uuid(),
        sqlalchemy.ForeignKey('guests.id', ondelete='RESTRICT'),
        nullable=False,
    ),
    sqlalchemy.Column(
        'room_id',
        sqlalchemy.Uuid(),
        sqlalchemy.ForeignKey('rooms.id', ondelete='RESTRICT'),
        nullable=False,
    ),
    sqlalchemy.Column(
        'check_in',
        sqlalchemy.Date(),
        nullable=False,
    ),
    sqlalchemy.Column(
        'check_out',
        sqlalchemy.Date(),
        nullable=False,
    ),
    sqlalchemy.Column(
        'status',
        sqlalchemy.Enum('pending', 'confirmed', 'cancelled', name='booking_status'),
        server_default='pending',
        nullable=False,
    ),
    sqlalchemy.Column(
        'total_amount',
        sqlalchemy.Numeric(precision=12, scale=2),
        nullable=False,
    ),
    sqlalchemy.Column(
        'currency',
        sqlalchemy.String(length=3),
        server_default='KZT',
        nullable=False,
    ),
    sqlalchemy.Column(
        'created_at',
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.func.now(),
        nullable=False,
    ),
    sqlalchemy.CheckConstraint(
        'check_out > check_in',
        name='ck_booking_dates',
    ),
    sqlalchemy.CheckConstraint(
        'total_amount > 0',
        name='ck_booking_amount',
    ),
    sqlalchemy.CheckConstraint(
        "currency ~ '^[A-Z]{3}$'",
        name='ck_booking_currency',
    ),
    ExcludeConstraint(
        ('room_id', '='),
        (sqlalchemy.func.daterange(
            sqlalchemy.column('check_in'),
            sqlalchemy.column('check_out'),
            '[)',
        ), '&&'),
        where=sqlalchemy.text("status IN ('pending', 'confirmed')"),
        using='gist',
        name='excl_booking_room_dates',
    ),
    sqlalchemy.Index('ix_bookings_guest_created', 'guest_id', 'created_at'),
)
