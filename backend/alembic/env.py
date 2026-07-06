"""Alembic environment: builds target metadata from all ORM models and reads
the database URL from application settings (not from alembic.ini directly),
so a single .env stays the source of truth.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.core.config import get_settings
from app.core.database import Base

# Import every module's models so they register on Base.metadata.
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.constraints import models as constraints_models  # noqa: F401
from app.modules.daily_stock import models as daily_stock_models  # noqa: F401
from app.modules.documents import models as documents_models  # noqa: F401
from app.modules.landed_cost import models as landed_cost_models  # noqa: F401
from app.modules.master_data import models as master_data_models  # noqa: F401
from app.modules.optimization import models as optimization_models  # noqa: F401
from app.modules.recommendations import models as recommendations_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
