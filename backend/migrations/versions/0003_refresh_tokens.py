"""Refresh tokens: only SHA-256 hashes are stored."""
import sqlalchemy as sa
from alembic import op

revision = "0003_refresh_tokens"
down_revision = "0002_uuid_defaults"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True,
                  server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("guest_id", sa.Uuid(),
                  sa.ForeignKey("guests.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_refresh_tokens_guest_id", "refresh_tokens", ["guest_id"])


def downgrade():
    op.drop_index("ix_refresh_tokens_guest_id", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")