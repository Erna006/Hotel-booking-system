import sqlalchemy
from alembic import context
from sqlalchemy import create_engine, pool

from backend.core.config import conf
from backend.core.db import metadata
from backend import models  # noqa: F401

config = context.config
target_metadata = metadata
# Alembic uses a synchronous driver; application queries use asyncpg.
migration_url = sqlalchemy.engine.make_url(conf.postgres_url).set(drivername="postgresql+psycopg")


def run_migrations_offline():
    context.configure(url=migration_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(migration_url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, compare_server_default=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
