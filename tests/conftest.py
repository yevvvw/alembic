# Нужные библиотеки
import asyncio
import pytest
from httpx import AsyncClient
from typing import AsyncGenerator
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from public.db import get_session
from models.dbcontext import *
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

import sys
import os

from main import app

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from config import settings

DATABASE_URL_TEST = settings.POSTGRES_DATABASE_URLT

engine_test = create_async_engine(DATABASE_URL_TEST, poolclass=NullPool, echo=True)
async_session_maker = sessionmaker(engine_test, class_=AsyncSession, expire_on_commit=False)

async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
     async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()

app.dependency_overrides[get_session] = override_get_session

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# Создание тестовой таблицы
@pytest.fixture(scope="session", autouse=True)
async def create_test_tables():
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

@pytest.fixture(scope="session", autouse=True)
def anyio_backend():
    return "asyncio", {"use_uvloop": True}

@pytest.fixture(scope="session")
def app():
    from main import app
    yield app

@pytest.fixture(scope="session")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client