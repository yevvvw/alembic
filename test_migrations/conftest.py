import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from db_utils import alembic_config_from_url, tmp_database

import os
from yarl import URL
from config import settings

# Получение URL базы данных
@pytest.fixture()
def pg_url():
    return URL(os.getenv('CI_STAFF_PG_URL', settings.POSTGRES_DATABASE_URLA))

# Создаем пустую временную базу данных
@pytest.fixture()
async def postgres(pg_url):
    async with tmp_database(pg_url, "pytest") as tmp_url:
        yield tmp_url

# Инициализируем движок
@pytest.fixture()
async def postgres_engine(postgres):
    engine = create_async_engine(
        url=postgres,
        pool_pre_ping=True,
    )
    try:
        yield engine
    finally:
        await engine.dispose()

# Привязываем конфигурацию alembic к базе данных
@pytest.fixture()
def alembic_config(postgres):
    return alembic_config_from_url(postgres)