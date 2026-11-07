"""Migration environment. The database URL comes from settings, never from a file."""

from alembic import context
from sqlalchemy import create_engine, pool

from backend import models  # noqa: F401 - registers tables on Base.metadata
from backend.config import normalise_db_url, settings
from backend.db import Base

target_metadata = Base.metadata
url = normalise_db_url(context.config.get_main_option("sqlalchemy.url") or settings.database_url)


def run_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_online() -> None:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_offline()
else:
    run_online()
