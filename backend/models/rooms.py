import sqlalchemy

from backend.core import db


Rooms = sqlalchemy.Table(
    'rooms',
    db.metadata,
    sqlalchemy.Column(
        'id',
        sqlalchemy.Uuid(),
        primary_key=True,
        server_default=sqlalchemy.text("gen_random_uuid()"),
        nullable=False,
    ),
    sqlalchemy.Column(
        'number',
        sqlalchemy.String(length=20),
        unique=True,
        nullable=False,
    ),
    sqlalchemy.Column(
        'room_type',
        sqlalchemy.String(length=50),
        nullable=False,
    ),
    sqlalchemy.Column(
        'capacity',
        sqlalchemy.Integer(),
        nullable=False,
    ),
    sqlalchemy.Column(
        'price_per_night',
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
        'is_active',
        sqlalchemy.Boolean(),
        server_default=sqlalchemy.text('true'),
        nullable=False,
    ),
    sqlalchemy.CheckConstraint(
        'capacity > 0',
        name='ck_room_capacity',
    ),
    sqlalchemy.CheckConstraint(
        'price_per_night > 0',
        name='ck_room_price',
    ),
    sqlalchemy.CheckConstraint(
        'length(trim(number)) > 0 AND length(trim(room_type)) > 0',
        name='ck_room_labels',
    ),
    sqlalchemy.CheckConstraint(
        "currency ~ '^[A-Z]{3}$'",
        name='ck_room_currency',
    ),
)
