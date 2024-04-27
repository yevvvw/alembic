import contextlib
import os
import uuid
from argparse import Namespace
from pathlib import Path
from typing import AsyncIterator, Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_utils.functions.database import (
    _set_url_database,
    make_url,
)
from sqlalchemy_utils.functions.orm import quote
from yarl import URL

from alembic.config import Config as AlembicConfig

# Получаем конфигурацию alembic
def make_alembic_config(
    cmd_opts: Namespace
) -> AlembicConfig:
    base_path = Path(".")
    if not Path(cmd_opts.config).is_absolute():
        cmd_opts.config = str(base_path.joinpath(cmd_opts.config).absolute())
    config = AlembicConfig(
        file_=cmd_opts.config,
        ini_section=cmd_opts.name,
        cmd_opts=cmd_opts,
    )
    alembic_location = config.get_main_option("script_location")
    if not Path(alembic_location).is_absolute():
        config.set_main_option(
            "script_location", str(base_path.joinpath(alembic_location).absolute())
        )
    if cmd_opts.pg_url:
        config.set_main_option("sqlalchemy.url", cmd_opts.pg_url)
    return config

# Предоставляем объект alembic.ini
def alembic_config_from_url(pg_url: Optional[str] = None) -> AlembicConfig:
    cmd_options = Namespace(
        config="alembic.ini",
        name="alembic",
        pg_url=pg_url,
        raiseerr=True,
        x=None,
    )
    return make_alembic_config(cmd_opts=cmd_options)

# Контекстный менеджер
@contextlib.asynccontextmanager
async def tmp_database(db_url: URL, suffix: str = "", **kwargs) -> AsyncIterator[str]:
    tmp_db_name = ".".join([uuid.uuid4().hex, "tests-base", suffix])
    tmp_db_url = str(db_url.with_path(tmp_db_name))
    await create_database_async(tmp_db_url, **kwargs)
    try:
        yield tmp_db_url
    finally:
        await drop_database_async(tmp_db_url)

# Создаем базу данных
async def create_database_async(
    url: str, encoding: str = "utf8", template: Optional[str] = None
) -> None:
    url = make_url(url)
    database = url.database
    dialect_name = url.get_dialect().name
    dialect_driver = url.get_dialect().driver

    if dialect_name == "postgresql":
        url = _set_url_database(url, database="postgres")
    elif dialect_name == "mssql":
        url = _set_url_database(url, database="master")
    elif dialect_name == "cockroachdb":
        url = _set_url_database(url, database="defaultdb")
    elif not dialect_name == "sqlite":
        url = _set_url_database(url, database=None)

    if (dialect_name == "mssql" and dialect_driver in {"pymssql", "pyodbc"}) or (
        dialect_name == "postgresql"
        and dialect_driver in {"asyncpg", "pg8000", "psycopg2", "psycopg2cffi"}
    ):
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    else:
        engine = create_async_engine(url)

    if dialect_name == "postgresql":
        if not template:
            template = "template1"

        async with engine.begin() as conn:
            text = "CREATE DATABASE {} ENCODING '{}' TEMPLATE {}".format(
                quote(conn, database), encoding, quote(conn, template)
            )
            await conn.execute(sa.text(text))

    elif dialect_name == "mysql":
        async with engine.begin() as conn:
            text = "CREATE DATABASE {} CHARACTER SET = '{}'".format(
                quote(conn, database), encoding
            )
            await conn.execute(sa.text(text))

    elif dialect_name == "sqlite" and database != ":memory:":
        if database:
            async with engine.begin() as conn:
                await conn.execute(sa.text("CREATE TABLE DB(id int)"))
                await conn.execute(sa.text("DROP TABLE DB"))

    else:
        async with engine.begin() as conn:
            text = f"CREATE DATABASE {quote(conn, database)}"
            await conn.execute(sa.text(text))

    await engine.dispose()

# Удаляем базу данных
async def drop_database_async(url: str) -> None:
    url = make_url(url)
    database = url.database
    dialect_name = url.get_dialect().name
    dialect_driver = url.get_dialect().driver

    if dialect_name == "postgresql":
        url = _set_url_database(url, database="postgres")
    elif dialect_name == "mssql":
        url = _set_url_database(url, database="master")
    elif dialect_name == "cockroachdb":
        url = _set_url_database(url, database="defaultdb")
    elif not dialect_name == "sqlite":
        url = _set_url_database(url, database=None)

    if dialect_name == "mssql" and dialect_driver in {"pymssql", "pyodbc"}:
        engine = create_async_engine(url, connect_args={"autocommit": True})
    elif dialect_name == "postgresql" and dialect_driver in {
        "asyncpg",
        "pg8000",
        "psycopg2",
        "psycopg2cffi",
    }:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    else:
        engine = create_async_engine(url)

    if dialect_name == "sqlite" and database != ":memory:":
        if database:
            os.remove(database)
    elif dialect_name == "postgresql":
        async with engine.begin() as conn:
            version = conn.dialect.server_version_info
            pid_column = "pid" if (version >= (9, 2)) else "procpid"
            text = f"""
            SELECT pg_terminate_backend(pg_stat_activity.{pid_column})
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{database}'
            AND {pid_column} <> pg_backend_pid();
            """
            await conn.execute(sa.text(text))

            # Удаляем базу данных
            text = f"DROP DATABASE {quote(conn, database)}"
            await conn.execute(sa.text(text))
    else:
        async with engine.begin() as conn:
            text = f"DROP DATABASE {quote(conn, database)}"
            await conn.execute(sa.text(text))

    await engine.dispose()
