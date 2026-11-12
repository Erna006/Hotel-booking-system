import sqlalchemy

from backend.core import db

RefreshTokens = sqlalchemy.Table(
    'refresh_tokens',
    db.metadata,
    sqlalchemy.Column('id', sqlalchemy.Uuid(), primary_key=True,
                      server_default=sqlalchemy.text('gen_random_uuid()'), nullable=False),
    sqlalchemy.Column('guest_id', sqlalchemy.Uuid(),
                      sqlalchemy.ForeignKey('guests.id', ondelete='RESTRICT'),
                      nullable=False, index=True),
    sqlalchemy.Column('token_hash', sqlalchemy.String(length=64), unique=True, nullable=False),
    sqlalchemy.Column('expires_at', sqlalchemy.DateTime(timezone=True), nullable=False),
    sqlalchemy.Column('revoked_at', sqlalchemy.DateTime(timezone=True), nullable=True),
    sqlalchemy.Column('created_at', sqlalchemy.DateTime(timezone=True),
                      server_default=sqlalchemy.func.now(), nullable=False),
)