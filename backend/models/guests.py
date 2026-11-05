import sqlalchemy

from backend.core import db


Guests = sqlalchemy.Table(
    'guests',
    db.metadata,
    sqlalchemy.Column(
        'id',
        sqlalchemy.Uuid(),
        primary_key=True,
        server_default=sqlalchemy.text("gen_random_uuid()"),
        nullable=False,
    ),
    sqlalchemy.Column(
        'email',
        sqlalchemy.String(length=254),
        unique=True,
        nullable=False,
    ),
    sqlalchemy.Column(
        'password_hash',
        sqlalchemy.String(length=255),
        nullable=False,
    ),
    sqlalchemy.Column(
        'full_name',
        sqlalchemy.String(length=200),
        nullable=False,
    ),
    sqlalchemy.Column(
        'role',
        sqlalchemy.Enum('guest', 'receptionist', 'admin', name='user_role'),
        server_default='guest',
        nullable=False,
    ),
    sqlalchemy.Column(
        'is_active',
        sqlalchemy.Boolean(),
        server_default=sqlalchemy.text('true'),
        nullable=False,
    ),
    sqlalchemy.Column(
        'created_at',
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.func.now(),
        nullable=False,
    ),
    sqlalchemy.CheckConstraint(
        "email = lower(trim(email)) AND position('@' in email) > 1",
        name='ck_guest_email',
    ),
    sqlalchemy.CheckConstraint(
        'length(trim(full_name)) > 0',
        name='ck_guest_name',
    ),
)
