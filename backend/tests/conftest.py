import os
import pytest
import asyncio
import aiosqlite
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

# Set required env vars before app imports so Settings() doesn't fail at collection time
os.environ.setdefault("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
os.environ.setdefault("ADMIN_TOKEN", "testtoken")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MEDIA_DIR", "/tmp/board_test_media")

class MockD1Client:
    def __init__(self):
        self.conn = None

    async def init(self):
        if self.conn is None:
            self.conn = await aiosqlite.connect(":memory:")
            self.conn.row_factory = aiosqlite.Row
            # Create the posts table
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE,
                content_type TEXT,
                body TEXT,
                media_path TEXT,
                og_title TEXT,
                og_description TEXT,
                og_image_path TEXT,
                deleted INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
            await self.conn.execute(create_table_sql)
            await self.conn.commit()

    async def execute(self, sql: str, params=None):
        await self.init()
        async with self.conn.execute(sql, params or []) as cursor:
            rows = await cursor.fetchall()
            await self.conn.commit()
            return [dict(row) for row in rows]

    async def clear_db(self):
        if self.conn:
            await self.conn.execute("DELETE FROM posts")
            await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()

# Instantiate mock
mock_d1 = MockD1Client()

# Override app.d1_client.d1
import app.d1_client
app.d1_client.d1 = mock_d1

# Suppress actual DB init
app.d1_client.init_db = mock_d1.init

@pytest.fixture(scope="session")
def test_app():
    """FastAPI app with signal-cli lifespan suppressed."""
    from app.routers import posts, admin

    app = FastAPI()  # no lifespan — no signal-cli socket attempt
    app.include_router(posts.router)
    app.include_router(admin.router)
    return app

@pytest.fixture(autouse=True)
async def clean_db():
    await mock_d1.init()
    await mock_d1.clear_db()
    yield
    await mock_d1.clear_db()

@pytest.fixture
async def client(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as c:
        yield c
