from logging.config import fileConfig

import asyncio
from contextvars import ContextVar
from typing import Any

from alembic.runtime.environment import EnvironmentContext
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool

from alembic import context

from config import settings
from models.dbcontext import Base

config = context.config

section = config.config_ini_section
config.set_section_option(section, "DB_USER", settings.POSTGRES_USER)
config.set_section_option(section, "DB_PASS", settings.POSTGRES_PASSWORD)
config.set_section_option(section, "DB_HOST", settings.POSTGRES_HOST)
config.set_section_option(section, "DB_PORT", settings.POSTGRES_PORT)
config.set_section_option(section, "DB_NAME", settings.POSTGRES_DB)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


ctx_var: ContextVar[dict[str, Any]] = ContextVar("ctx_var")

# Миграция в режиме 'Оффлайн'
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

# Выполнение миграции
def do_run_migrations(connection: Connection) -> None:
    try:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()
    except AttributeError:
        context_data = ctx_var.get()
        with EnvironmentContext(
                config=context_data["config"],
                script=context_data["script"],
                **context_data["opts"],
        ):
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()

# Асинхронная миграция
async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

# Миграция в режиме 'Онлайн'
def run_migrations_online() -> None:
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(run_async_migrations())
        return
    from tests import conftest
    ctx_var.set({
        "config": context.config,
        "script": context.script,
        "opts": context._proxy.context_opts,
    })
    conftest.MIGRATION_TASK = asyncio.create_task(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()