"""Persist the guest count for newly created bookings."""

import sqlalchemy as sa
from alembic import op

revision = '0003_booking_guest_count'
down_revision = '0002_uuid_defaults'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bookings', sa.Column('guest_count', sa.Integer(), nullable=True))
    op.create_check_constraint('ck_booking_guest_count', 'bookings', 'guest_count > 0')


def downgrade():
    op.drop_constraint('ck_booking_guest_count', 'bookings', type_='check')
    op.drop_column('bookings', 'guest_count')
