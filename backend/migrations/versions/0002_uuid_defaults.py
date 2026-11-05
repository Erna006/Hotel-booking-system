"""Generate UUID primary keys in PostgreSQL for async Core inserts."""
import sqlalchemy
from alembic import op

revision = "0002_uuid_defaults"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("guests", "rooms", "bookings", "payments"):
        op.alter_column(table, "id", server_default=sqlalchemy.text("gen_random_uuid()"))


def downgrade():
    for table in ("guests", "rooms", "bookings", "payments"):
        op.alter_column(table, "id", server_default=None)
