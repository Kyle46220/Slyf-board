import os

# Set required env vars before app imports so Settings() doesn't fail at collection time
os.environ.setdefault("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
os.environ.setdefault("ADMIN_TOKEN", "testtoken")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MEDIA_DIR", "/tmp/board_test_media")

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import get_db
from app.models import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def test_app():
    """FastAPI app with signal-cli lifespan suppressed and DB overridden."""
    from app.routers import posts, admin

    app = FastAPI()  # no lifespan — no signal-cli socket attempt
    app.include_router(posts.router)
    app.include_router(admin.router)
    return app


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(test_app, db_session):
    async def override_get_db():
        yield db_session
    test_app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        yield c
    test_app.dependency_overrides.clear()
