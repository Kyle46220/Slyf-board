# Secure Anonymous Notice Board — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a strictly anonymous, media-rich bulletin board where trusted posters submit content via Signal using a TOTP code; the backend strips all sender metadata and the public frontend displays posts in a real-time masonry grid.

**Architecture:** Single FastAPI monolith on a 1984.is VPS. signal-cli runs as a systemd daemon and exposes a JSON-RPC socket. FastAPI validates TOTP, processes media synchronously, writes to PostgreSQL, then broadcasts SSE events to connected React clients.

**Tech Stack:** Python 3.12 / FastAPI / pyotp / Pillow / ffmpeg / httpx / BeautifulSoup / PostgreSQL / React / Tailwind CSS / Vite / signal-cli / Nginx / certbot

---

## File Structure

```
board/
├── backend/
│   ├── pyproject.toml              # dependencies + project metadata
│   ├── .env.example                # TOTP_SECRET, ADMIN_TOKEN, DATABASE_URL, MEDIA_DIR
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   │       └── 001_create_posts.py
│   └── app/
│       ├── main.py                 # FastAPI app init, lifespan, router registration
│       ├── config.py               # settings loaded from env vars
│       ├── database.py             # async SQLAlchemy engine + session factory
│       ├── models.py               # Post ORM model
│       ├── schemas.py              # Pydantic response schemas
│       ├── totp.py                 # TOTP verify helper
│       ├── media.py                # image/video/OG processing
│       ├── signal_listener.py      # signal-cli JSON-RPC client + message ingestion loop
│       ├── sse.py                  # SSE event broadcaster (in-memory queue)
│       └── routers/
│           ├── posts.py            # GET /api/posts, GET /api/posts/{hash}, GET /api/stream
│           └── admin.py            # DELETE /api/admin/posts/{hash}
├── token-generator/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       └── main.ts                 # TOTP generation with otpauth, display + copy UI
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx                 # router (/ and /post/:hash)
│       ├── api.ts                  # fetch wrappers for /api/posts and /api/stream
│       ├── types.ts                # Post TypeScript type
│       ├── components/
│       │   ├── Board.tsx           # masonry grid + SSE listener
│       │   ├── PostCard.tsx        # card renderer (text/image/video/link)
│       │   └── SinglePost.tsx      # /post/:hash view
│       └── index.css               # Tailwind directives + column-count masonry CSS
├── nginx/
│   ├── board.conf                  # reverse proxy + static file serving + access_log off
│   └── token-generator.conf
└── deploy/
    ├── signal-cli.service          # systemd unit file
    └── setup.sh                    # one-shot VPS bootstrap script
```

---

## Chunk 1: Backend Foundation (config, DB, models, migrations)

### Task 1: Project scaffold and dependencies

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/.env.example`

- [ ] **Step 1: Create pyproject.toml**

```toml
[project]
name = "board-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "psycopg2-binary>=2.9",
    "alembic>=1.13",
    "pyotp>=2.9",
    "pillow>=10.3",
    "httpx>=0.27",
    "beautifulsoup4>=4.12",
    "python-dotenv>=1.0",
    "python-multipart>=0.0.9",
    "pydantic-settings>=2.2",
    "websockets>=12.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .env.example**

```
TOTP_SECRET=BASE32SECRETHERE
ADMIN_TOKEN=changeme
DATABASE_URL=postgresql+asyncpg://board:password@localhost/board
MEDIA_DIR=/var/board/media
```

- [ ] **Step 3: Install dependencies**

```bash
cd backend
pip install -e ".[dev]"
```

Expected: all packages install without error.

- [ ] **Step 4: Commit**

```bash
git add backend/pyproject.toml backend/.env.example
git commit -m "chore: scaffold backend project with dependencies"
```

---

### Task 2: Config, database, and models

**Files:**
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`

- [ ] **Step 1: Write failing test for config loading**

Create `backend/tests/test_config.py`:

```python
import os
import pytest

def test_config_loads_required_vars(monkeypatch):
    monkeypatch.setenv("TOTP_SECRET", "JBSWY3DPEHPK3PXP")
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/db")
    monkeypatch.setenv("MEDIA_DIR", "/tmp/media")
    # reimport to pick up monkeypatched env
    import importlib
    import app.config as cfg
    importlib.reload(cfg)
    from app.config import settings
    assert settings.totp_secret == "JBSWY3DPEHPK3PXP"
    assert settings.admin_token == "secret"
    assert settings.media_dir == "/tmp/media"

def test_config_raises_on_missing_totp_secret(monkeypatch):
    monkeypatch.delenv("TOTP_SECRET", raising=False)
    import importlib
    import app.config as cfg
    with pytest.raises(Exception):
        importlib.reload(cfg)
        from app.config import settings
        _ = settings.totp_secret
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `app.config` doesn't exist yet.

- [ ] **Step 3: Implement config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    totp_secret: str
    admin_token: str
    database_url: str
    media_dir: str = "/var/board/media"

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_config.py -v
```

Expected: PASS.

- [ ] **Step 5: Implement database.py**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
```

- [ ] **Step 6: Implement models.py**

```python
# backend/app/models.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hash: Mapped[str] = mapped_column(String(36), unique=True, nullable=False,
                                       default=lambda: str(uuid.uuid4()))
    content_type: Mapped[str] = mapped_column(
        SAEnum("text", "image", "video", "link", name="content_type_enum"), nullable=False
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    og_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
```

- [ ] **Step 7: Implement schemas.py**

```python
# backend/app/schemas.py
from datetime import datetime
from pydantic import BaseModel

class PostOut(BaseModel):
    hash: str
    content_type: str
    body: str | None
    media_path: str | None
    og_title: str | None
    og_description: str | None
    og_image_path: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/config.py backend/app/database.py backend/app/models.py backend/app/schemas.py backend/tests/test_config.py
git commit -m "feat: config, database, ORM models, and response schemas"
```

---

### Task 3: Alembic migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_create_posts.py`

- [ ] **Step 1: Initialize alembic**

```bash
cd backend
alembic init alembic
```

- [ ] **Step 2: Configure alembic/env.py to use async engine**

Edit `backend/alembic/env.py`. Replace the `run_migrations_online` function:

```python
# at top of file, add:
from app.models import Base
from app.config import settings

# replace run_migrations_online:
def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    # swap asyncpg driver for psycopg2 (sync) for alembic migrations
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    connectable = create_engine(sync_url)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
```

Also set `target_metadata = Base.metadata` at module level.

- [ ] **Step 3: Set sqlalchemy.url in alembic.ini**

In `alembic.ini`, set:
```
sqlalchemy.url = %(DATABASE_URL)s
```

Then in `alembic/env.py` at the top of `run_migrations_online`, override with `settings.database_url`.

- [ ] **Step 4: Generate migration**

```bash
cd backend
alembic revision --autogenerate -m "create posts table"
```

Expected: a new file in `alembic/versions/` with `op.create_table("posts", ...)`.

- [ ] **Step 5: Verify migration SQL looks correct**

```bash
alembic upgrade head --sql
```

Expected: SQL output containing `CREATE TABLE posts`, `CREATE TYPE content_type_enum`, all columns present, `deleted BOOLEAN DEFAULT FALSE NOT NULL`.

- [ ] **Step 6: Apply migration to local dev DB**

First create the database:
```bash
createdb board
```

Then apply:
```bash
alembic upgrade head
```

Expected: `Running upgrade -> <rev>, create posts table`.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic.ini backend/alembic/
git commit -m "feat: alembic migration to create posts table"
```

---

## Chunk 2: TOTP, media processing, SSE broadcaster

### Task 4: TOTP validation

**Files:**
- Create: `backend/app/totp.py`
- Create: `backend/tests/test_totp.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_totp.py
import pyotp
import time
from app.totp import verify_totp

SECRET = "JBSWY3DPEHPK3PXP"

def test_valid_current_code():
    totp = pyotp.TOTP(SECRET, interval=300)
    code = totp.now()
    assert verify_totp(code, SECRET) is True

def test_invalid_code():
    assert verify_totp("000000", SECRET) is False

def test_wrong_length_rejected():
    assert verify_totp("12345", SECRET) is False
    assert verify_totp("1234567", SECRET) is False

def test_non_numeric_rejected():
    assert verify_totp("abcdef", SECRET) is False
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_totp.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement totp.py**

```python
# backend/app/totp.py
import pyotp

def verify_totp(code: str, secret: str) -> bool:
    if not code or len(code) != 6 or not code.isdigit():
        return False
    totp = pyotp.TOTP(secret, interval=300)
    return totp.verify(code, valid_window=1)
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_totp.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/totp.py backend/tests/test_totp.py
git commit -m "feat: TOTP verification with 5-minute window"
```

---

### Task 5: Media processing

**Files:**
- Create: `backend/app/media.py`
- Create: `backend/tests/test_media.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_media.py
import shutil
import subprocess
import pytest
from pathlib import Path
from PIL import Image
from app.media import process_image, process_video, scrape_og

TMP = Path("/tmp/board_test_media")

@pytest.fixture(autouse=True)
def tmp_dir():
    TMP.mkdir(exist_ok=True)
    yield
    shutil.rmtree(TMP, ignore_errors=True)

def make_jpeg_with_exif(path: Path):
    img = Image.new("RGB", (100, 100), color=(255, 0, 0))
    exif_bytes = img.getexif()
    exif_bytes[0x013B] = "Test Artist"  # Artist tag — survives JPEG save
    img.save(path, "JPEG", exif=exif_bytes.tobytes())

def make_test_mp4(path: Path):
    """Create a minimal valid MP4 using ffmpeg (requires ffmpeg installed)."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:size=64x64:duration=1",
         "-c:v", "libx264", "-t", "1", str(path)],
        capture_output=True, check=True
    )

def test_process_image_strips_exif_and_converts_to_webp(tmp_path):
    src = tmp_path / "input.jpg"
    make_jpeg_with_exif(src)
    out = process_image(src, TMP / "abc123")
    assert out is not None
    assert out.suffix == ".webp"
    result = Image.open(out)
    assert len(result.getexif()) == 0  # no EXIF

def test_process_image_returns_none_on_corrupt_file(tmp_path):
    src = tmp_path / "bad.jpg"
    src.write_bytes(b"not an image")
    out = process_image(src, TMP / "def456")
    assert out is None

def test_process_video_re_encodes_to_mp4(tmp_path):
    """Requires ffmpeg installed: apt install ffmpeg"""
    src = tmp_path / "input.mp4"
    make_test_mp4(src)
    out = process_video(src, TMP / "vid123")
    assert out is not None
    assert out.suffix == ".mp4"
    assert out.exists()

def test_process_video_returns_none_on_corrupt_file(tmp_path):
    src = tmp_path / "bad.mp4"
    src.write_bytes(b"not a video")
    out = process_video(src, TMP / "vid456")
    assert out is None

def test_scrape_og_returns_none_on_network_error():
    # use an unroutable address
    result = scrape_og("http://10.255.255.1/")
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_media.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement media.py**

```python
# backend/app/media.py
import io
import subprocess
import shutil
from pathlib import Path
from typing import Optional
import httpx
from PIL import Image
from bs4 import BeautifulSoup

def _ensure_dir(dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir

def process_image(src: Path, dest_dir: Path) -> Optional[Path]:
    """Strip EXIF and convert to WebP. Returns output path or None on failure."""
    try:
        _ensure_dir(dest_dir)
        img = Image.open(src)
        img_clean = img.copy()  # drops EXIF
        out = dest_dir / "media.webp"
        img_clean.save(out, "WEBP")
        return out
    except Exception:
        return None

def process_video(src: Path, dest_dir: Path) -> Optional[Path]:
    """Strip metadata and re-encode to MP4. Returns output path or None on failure."""
    try:
        _ensure_dir(dest_dir)
        out = dest_dir / "media.mp4"
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(src),
                "-map_metadata", "-1",    # strip global metadata
                "-fflags", "+bitexact",   # suppress encoder tags
                "-c:v", "libx264",        # full re-encode (strips in-stream metadata)
                "-crf", "23",
                "-preset", "fast",
                "-c:a", "aac",
                str(out),
            ],
            capture_output=True,
            timeout=300,
        )
        if result.returncode != 0:
            return None
        return out
    except Exception:
        return None

class OGResult:
    def __init__(self, title, description, image_path):
        self.title = title
        self.description = description
        self.image_path = image_path  # local Path or None

def scrape_og(url: str, dest_dir: Optional[Path] = None) -> Optional[OGResult]:
    """Fetch OG tags from URL. Downloads and strips EXIF from OG image if dest_dir given."""
    try:
        resp = httpx.get(url, timeout=10, follow_redirects=True)
        soup = BeautifulSoup(resp.text, "html.parser")

        def og(prop):
            tag = soup.find("meta", property=f"og:{prop}")
            return tag["content"] if tag and tag.get("content") else None

        title = og("title") or (soup.title.string if soup.title else None)
        description = og("description")
        image_url = og("image")
        image_path = None

        if image_url and dest_dir:
            img_resp = httpx.get(image_url, timeout=10, follow_redirects=True)
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                raw = Path(tmp.name)
            raw.write_bytes(img_resp.content)
            image_path = process_image(raw, dest_dir)
            if image_path:
                image_path = image_path.parent / "og.webp"
                (image_path.parent / "media.webp").rename(image_path)

        return OGResult(title=title, description=description, image_path=image_path)
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/test_media.py -v
```

Expected: 5 PASS. (video tests require ffmpeg with libx264: `apt install ffmpeg`)

- [ ] **Step 5: Commit**

```bash
git add backend/app/media.py backend/tests/test_media.py
git commit -m "feat: media processing — image EXIF strip, video re-encode, OG scraping"
```

---

### Task 6: SSE broadcaster

**Files:**
- Create: `backend/app/sse.py`
- Create: `backend/tests/test_sse.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_sse.py
import asyncio
import pytest
from app.sse import SSEBroadcaster

@pytest.mark.asyncio
async def test_subscriber_receives_published_event():
    broadcaster = SSEBroadcaster()
    queue = broadcaster.subscribe()
    await broadcaster.publish({"type": "new_post", "hash": "abc"})
    event = await asyncio.wait_for(queue.get(), timeout=1)
    assert event["hash"] == "abc"

@pytest.mark.asyncio
async def test_unsubscribed_queue_does_not_receive():
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe()
    broadcaster.unsubscribe(q1)
    await broadcaster.publish({"type": "new_post", "hash": "xyz"})
    assert q1.empty()

@pytest.mark.asyncio
async def test_multiple_subscribers_all_receive():
    broadcaster = SSEBroadcaster()
    q1 = broadcaster.subscribe()
    q2 = broadcaster.subscribe()
    await broadcaster.publish({"type": "delete", "hash": "zzz"})
    e1 = await asyncio.wait_for(q1.get(), timeout=1)
    e2 = await asyncio.wait_for(q2.get(), timeout=1)
    assert e1["hash"] == e2["hash"] == "zzz"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_sse.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement sse.py**

```python
# backend/app/sse.py
import asyncio
import json
from typing import AsyncGenerator

class SSEBroadcaster:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def publish(self, event: dict):
        for q in list(self._queues):
            await q.put(event)

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            self.unsubscribe(q)

broadcaster = SSEBroadcaster()
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_sse.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/sse.py backend/tests/test_sse.py
git commit -m "feat: SSE broadcaster for real-time post events"
```

---

## Chunk 3: Signal ingestion + API routers + FastAPI app

### Task 7: Signal ingestion loop

**Files:**
- Create: `backend/app/signal_listener.py`
- Create: `backend/tests/test_signal_listener.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_signal_listener.py
import pytest
from app.signal_listener import parse_message

def test_parse_text_message():
    result = parse_message("123456 hello world", attachments=[])
    assert result["totp"] == "123456"
    assert result["body"] == "hello world"
    assert result["content_type"] == "text"

def test_parse_code_only_no_body():
    result = parse_message("123456", attachments=[])
    assert result["totp"] == "123456"
    assert result["body"] is None
    assert result["content_type"] == "text"

def test_parse_attachment_with_caption():
    result = parse_message("123456 my caption", attachments=[{"content_type": "image/jpeg", "filename": "photo.jpg"}])
    assert result["totp"] == "123456"
    assert result["body"] == "my caption"
    assert result["content_type"] == "image"

def test_parse_attachment_no_caption():
    result = parse_message("123456", attachments=[{"content_type": "video/mp4", "filename": "clip.mp4"}])
    assert result["body"] is None
    assert result["content_type"] == "video"

def test_parse_link_message():
    result = parse_message("123456 https://example.com/article", attachments=[])
    assert result["content_type"] == "link"
    assert result["body"] == "https://example.com/article"

def test_short_code_rejected():
    result = parse_message("12345 hello", attachments=[])
    assert result is None

def test_missing_code_rejected():
    result = parse_message("hello world", attachments=[])
    assert result is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_signal_listener.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement parse_message in signal_listener.py**

```python
# backend/app/signal_listener.py
import asyncio
import json
import logging
import re
import websockets
from pathlib import Path
from typing import Optional
from app.config import settings
from app.totp import verify_totp

logger = logging.getLogger(__name__)

URL_RE = re.compile(r"^https?://\S+$")

def parse_message(text: str, attachments: list) -> Optional[dict]:
    """Extract TOTP and content from a raw Signal message. Returns None if malformed."""
    if not text:
        return None
    parts = text.strip().split(" ", 1)
    code = parts[0]
    if len(code) != 6 or not code.isdigit():
        return None
    body = parts[1].strip() if len(parts) > 1 else None

    # determine content type
    if attachments:
        first = attachments[0].get("content_type", "")
        if first.startswith("image/"):
            content_type = "image"
        elif first.startswith("video/"):
            content_type = "video"
        else:
            content_type = "text"
    elif body and URL_RE.match(body):
        content_type = "link"
    else:
        content_type = "text"

    return {
        "totp": code,
        "body": body,
        "content_type": content_type,
        "attachments": attachments,
    }


async def listen(on_message, signal_socket_path: str = "/var/run/signal-cli/socket"):
    """
    Connect to signal-cli JSON-RPC socket and call on_message(parsed) for each valid message.
    Reconnects with exponential backoff (max 10 retries, cap 60s).
    """
    delay = 1
    retries = 0
    max_retries = 10

    while retries < max_retries:
        try:
            async with websockets.unix_connect(signal_socket_path) as ws:
                logger.info("Connected to signal-cli socket")
                delay = 1
                retries = 0
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        envelope = msg.get("params", {}).get("envelope", {})
                        data_msg = envelope.get("dataMessage", {})
                        text = data_msg.get("message", "") or ""
                        attachments = data_msg.get("attachments", [])

                        # strip sender metadata immediately
                        envelope.pop("source", None)
                        envelope.pop("sourceNumber", None)
                        envelope.pop("sourceName", None)
                        envelope.pop("sourceDevice", None)
                        envelope.pop("sourceUuid", None)
                        data_msg.pop("timestamp", None)

                        parsed = parse_message(text, attachments)
                        if parsed is None:
                            continue
                        if not verify_totp(parsed["totp"], settings.totp_secret):
                            continue

                        await on_message(parsed)
                    except Exception as e:
                        logger.error(f"Error processing message: {e}")
        except Exception as e:
            retries += 1
            logger.error(f"signal-cli connection failed (attempt {retries}/{max_retries}): {e}")
            await asyncio.sleep(min(delay, 60))
            delay *= 2

    logger.error("Max retries reached. signal-cli listener stopped.")
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_signal_listener.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/signal_listener.py backend/tests/test_signal_listener.py
git commit -m "feat: signal-cli message parser and ingestion loop"
```

---

### Task 8: Posts and admin routers

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/posts.py`
- Create: `backend/app/routers/admin.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_routers.py`

- [ ] **Step 1: Create routers package and conftest**

```bash
touch backend/app/routers/__init__.py
touch backend/app/__init__.py
touch backend/tests/__init__.py
```

Create `backend/tests/conftest.py`:

```python
# backend/tests/conftest.py
import os
import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import get_db
from app.models import Base

# Use a separate test database (sqlite in-memory for speed)
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def test_app():
    """Return a FastAPI app with the signal-cli lifespan suppressed and DB overridden."""
    from app.routers import posts, admin
    from app.sse import broadcaster

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
```

Edit `backend/pyproject.toml` to add `aiosqlite` to dev dependencies:

```toml
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "httpx>=0.27", "aiosqlite>=0.20"]
```

Then reinstall:
```bash
cd backend && pip install -e ".[dev]"
```

- [ ] **Step 2: Write failing tests**

Create `backend/tests/test_routers.py`:

```python
# backend/tests/test_routers.py
import pytest
from httpx import AsyncClient

async def test_get_posts_returns_list(client: AsyncClient):
    resp = await client.get("/api/posts")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

async def test_get_post_not_found(client: AsyncClient):
    resp = await client.get("/api/posts/nonexistent-hash")
    assert resp.status_code == 404

async def test_admin_delete_requires_auth(client: AsyncClient):
    resp = await client.delete("/api/admin/posts/somehash")
    assert resp.status_code == 401

async def test_admin_delete_wrong_token(client: AsyncClient):
    resp = await client.delete(
        "/api/admin/posts/somehash",
        headers={"Authorization": "Bearer wrongtoken"}
    )
    assert resp.status_code == 403

async def test_stream_returns_event_stream_content_type(client: AsyncClient):
    async with client.stream("GET", "/api/stream") as resp:
        assert resp.headers["content-type"].startswith("text/event-stream")
    # exiting the async with closes the connection — no break needed
```

- [ ] **Step 3: Run to verify failure**

```bash
cd backend
pytest tests/test_routers.py -v
```

Expected: ImportError (`app.routers` not found — routers not yet implemented).

- [ ] **Step 4: Implement posts router**

```python
# backend/app/routers/posts.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Post
from app.schemas import PostOut
from app.sse import broadcaster

router = APIRouter(prefix="/api")

@router.get("/posts", response_model=list[PostOut])
async def list_posts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).where(Post.deleted == False).order_by(Post.id.desc())
    )
    return result.scalars().all()

@router.get("/posts/{hash}", response_model=PostOut)
async def get_post(hash: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).where(Post.hash == hash, Post.deleted == False)
    )
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    return post

@router.get("/stream")
async def stream_events():
    q = broadcaster.subscribe()
    return StreamingResponse(
        broadcaster.stream(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: Implement admin router**

```python
# backend/app/routers/admin.py
import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models import Post
from app.sse import broadcaster

router = APIRouter(prefix="/api/admin")

async def require_admin(authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")

@router.delete("/posts/{hash}", dependencies=[Depends(require_admin)])
async def delete_post(hash: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Post).where(Post.hash == hash))
    post = result.scalar_one_or_none()
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")

    # purge media files
    media_dir = Path(settings.media_dir) / hash
    if media_dir.exists():
        shutil.rmtree(media_dir)

    # nullify content fields
    post.deleted = True
    post.body = None
    post.media_path = None
    post.og_title = None
    post.og_description = None
    post.og_image_path = None
    await db.commit()

    # notify connected frontends
    await broadcaster.publish({"type": "delete", "hash": hash})
    return {"ok": True}
```

- [ ] **Step 6: Implement main.py**

```python
# backend/app/main.py
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import SessionLocal
from app.models import Post
from app.routers import posts, admin
from app.signal_listener import listen
from app.media import process_image, process_video, scrape_og
from app.sse import broadcaster

logger = logging.getLogger(__name__)

async def handle_message(parsed: dict):
    """Ingest a validated, metadata-stripped Signal message into the DB."""
    import uuid
    post_hash = str(uuid.uuid4())
    media_dir = Path(settings.media_dir) / post_hash
    content_type = parsed["content_type"]
    media_path = None
    og_title = og_description = og_image_path = None

    # process media synchronously before DB write
    if content_type == "image" and parsed.get("attachments"):
        src = Path(parsed["attachments"][0].get("filename", ""))
        if src.exists():
            out = process_image(src, media_dir)
            media_path = str(out) if out else None
            if not media_path:
                content_type = "text"

    elif content_type == "video" and parsed.get("attachments"):
        src = Path(parsed["attachments"][0].get("filename", ""))
        if src.exists():
            out = process_video(src, media_dir)
            media_path = str(out) if out else None
            if not media_path:
                content_type = "text"

    elif content_type == "link" and parsed.get("body"):
        og = scrape_og(parsed["body"], media_dir)
        if og:
            og_title = og.title
            og_description = og.description
            og_image_path = str(og.image_path) if og.image_path else None

    async with SessionLocal() as db:
        post = Post(
            hash=post_hash,
            content_type=content_type,
            body=parsed.get("body"),
            media_path=media_path,
            og_title=og_title,
            og_description=og_description,
            og_image_path=og_image_path,
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)

    await broadcaster.publish({"type": "new_post", "hash": post_hash})
    logger.info(f"Post {post_hash} ingested ({content_type})")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(listen(handle_message))
    yield
    task.cancel()

app = FastAPI(lifespan=lifespan)
app.include_router(posts.router)
app.include_router(admin.router)
```

- [ ] **Step 7: Run tests**

```bash
cd backend
pytest tests/test_routers.py -v
```

Expected: 5 PASS. Tests use SQLite in-memory — no external database needed.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/ backend/app/main.py backend/tests/conftest.py backend/tests/test_routers.py
git commit -m "feat: posts + admin routers, FastAPI app with signal-cli lifespan"
```

---

## Chunk 4: Token Generator

### Task 9: Token Generator static site

**Files:**
- Create: `token-generator/package.json`
- Create: `token-generator/vite.config.ts`
- Create: `token-generator/index.html`
- Create: `token-generator/src/main.ts`

- [ ] **Step 1: Scaffold Vite project**

```bash
cd token-generator
npm create vite@latest . -- --template vanilla-ts
npm install otpauth
```

- [ ] **Step 2: Write main.ts**

```typescript
// token-generator/src/main.ts
import * as OTPAuth from "otpauth";

const secret = import.meta.env.VITE_TOTP_SECRET as string;
if (!secret) {
  throw new Error("VITE_TOTP_SECRET is not set");
}

const totp = new OTPAuth.TOTP({
  secret: OTPAuth.Secret.fromBase32(secret),
  period: 300,    // 5-minute windows to match backend
  digits: 6,
  algorithm: "SHA1",
});

function renderCode() {
  const code = totp.generate();
  const codeEl = document.getElementById("code")!;
  codeEl.textContent = code;
}

function secondsUntilExpiry(): number {
  return totp.period - (Math.floor(Date.now() / 1000) % totp.period);
}

function renderTimer() {
  const timerEl = document.getElementById("timer")!;
  timerEl.textContent = `Expires in ${secondsUntilExpiry()}s`;
}

document.getElementById("copy-btn")!.addEventListener("click", () => {
  const code = document.getElementById("code")!.textContent!;
  navigator.clipboard.writeText(code);
  const btn = document.getElementById("copy-btn")!;
  btn.textContent = "Copied!";
  setTimeout(() => { btn.textContent = "Copy"; }, 1500);
});

// update timer every second; refresh code when window turns over
function tick() {
  renderCode();
  renderTimer();
}

renderCode();
renderTimer();
setInterval(tick, 1000);
```

- [ ] **Step 3: Write index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Token Generator</title>
  <style>
    body { font-family: monospace; display: flex; flex-direction: column;
           align-items: center; justify-content: center; height: 100vh;
           background: #111; color: #eee; margin: 0; }
    #code { font-size: 4rem; letter-spacing: 0.5rem; margin-bottom: 1rem; }
    #timer { font-size: 1rem; color: #888; margin-bottom: 2rem; }
    #copy-btn { padding: 0.75rem 2rem; font-size: 1rem; cursor: pointer;
                background: #222; color: #eee; border: 1px solid #444;
                border-radius: 4px; }
  </style>
</head>
<body>
  <div id="code">------</div>
  <div id="timer"></div>
  <button id="copy-btn">Copy</button>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 4: Test build with a real secret**

```bash
cd token-generator
VITE_TOTP_SECRET=JBSWY3DPEHPK3PXP npm run build
```

Expected: `dist/` folder created with no errors. Verify `dist/assets/*.js` does NOT contain the literal string `VITE_TOTP_SECRET` (the secret will be inlined as its value).

```bash
grep -r "VITE_TOTP_SECRET" dist/
```

Expected: no output. (Vite inlines the value, not the variable name.)

- [ ] **Step 5: Verify the built site works**

```bash
npx serve dist
```

Open `http://localhost:3000` — should show a 6-digit code that refreshes and a working Copy button.

- [ ] **Step 6: Commit**

```bash
git add token-generator/
git commit -m "feat: token generator static site with 5-minute TOTP"
```

---

## Chunk 5: React Frontend

### Task 10: Frontend scaffold and types

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/api.ts`

- [ ] **Step 1: Scaffold Vite + React + Tailwind v4**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install react-router-dom react-markdown tailwindcss @tailwindcss/vite
```

Write `frontend/vite.config.ts`:

```typescript
// frontend/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
});
```

Note: Tailwind v4 does NOT use `tailwind.config.js` or `npx tailwindcss init`. Configuration is done entirely through the Vite plugin. Do NOT run `npx tailwindcss init`.

Verify the build works before writing any components:

```bash
npm run build
```

Expected: `dist/` created with no errors.

- [ ] **Step 2: Define types.ts**

```typescript
// frontend/src/types.ts
export interface Post {
  hash: string;
  content_type: "text" | "image" | "video" | "link";
  body: string | null;
  media_path: string | null;
  og_title: string | null;
  og_description: string | null;
  og_image_path: string | null;
  created_at: string;
}
```

- [ ] **Step 3: Implement api.ts**

```typescript
// frontend/src/api.ts
import { Post } from "./types";

const BASE = "/api";

export async function fetchPosts(): Promise<Post[]> {
  const res = await fetch(`${BASE}/posts`);
  if (!res.ok) throw new Error("Failed to fetch posts");
  return res.json();
}

export async function fetchPost(hash: string): Promise<Post> {
  const res = await fetch(`${BASE}/posts/${hash}`);
  if (res.status === 404) throw new Error("Not found");
  if (!res.ok) throw new Error("Failed to fetch post");
  return res.json();
}

export function createEventSource(): EventSource {
  return new EventSource(`${BASE}/stream`);
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "chore: scaffold React frontend with types and API client"
```

---

### Task 11: PostCard component

**Files:**
- Create: `frontend/src/components/PostCard.tsx`

- [ ] **Step 1: Implement PostCard**

```tsx
// frontend/src/components/PostCard.tsx
import React, { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import { Post } from "../types";

interface Props {
  post: Post;
}

function LazyImage({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        ref.current!.src = src;
        observer.disconnect();
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [src]);

  return <img ref={ref} alt={alt} className="w-full rounded" />;
}

function LazyVideo({ src }: { src: string }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        ref.current!.src = src;
        observer.disconnect();
      }
    });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [src]);

  return <video ref={ref} controls autoPlay={false} className="w-full rounded" />;
}

export function PostCard({ post }: Props) {
  function copyLink() {
    navigator.clipboard.writeText(`${window.location.origin}/post/${post.hash}`);
  }

  const mediaUrl = post.media_path
    ? `/media/${post.hash}/${post.content_type === "video" ? "media.mp4" : "media.webp"}`
    : null;

  return (
    <div className="break-inside-avoid mb-4 bg-zinc-900 rounded-lg p-3 text-white">
      {post.content_type === "image" && mediaUrl && (
        <LazyImage src={mediaUrl} alt="post image" />
      )}
      {post.content_type === "video" && mediaUrl && (
        <LazyVideo src={mediaUrl} />
      )}
      {post.content_type === "link" && (
        <a href={post.body ?? "#"} target="_blank" rel="noopener noreferrer"
           className="block border border-zinc-700 rounded p-2 hover:bg-zinc-800">
          {post.og_image_path && (
            <LazyImage src={`/media/${post.hash}/og.webp`} alt="link preview" />
          )}
          {post.og_title && <p className="font-bold mt-1">{post.og_title}</p>}
          {post.og_description && (
            <p className="text-sm text-zinc-400 mt-1">{post.og_description}</p>
          )}
          <p className="text-xs text-zinc-500 mt-1 truncate">{post.body}</p>
        </a>
      )}
      {post.body && post.content_type !== "link" && (
        <div className="prose prose-invert prose-sm mt-2">
          <ReactMarkdown>{post.body}</ReactMarkdown>
        </div>
      )}
      <button onClick={copyLink}
              className="mt-2 text-xs text-zinc-500 hover:text-zinc-300">
        Copy Link
      </button>
    </div>
  );
}
```

- [ ] **Step 2: TypeScript compile check**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PostCard.tsx
git commit -m "feat: PostCard component with lazy loading for images, video, and links"
```

---

### Task 12: Board and SinglePost components, App router

**Files:**
- Create: `frontend/src/components/Board.tsx`
- Create: `frontend/src/components/SinglePost.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`

- [ ] **Step 1: Implement Board.tsx**

```tsx
// frontend/src/components/Board.tsx
import React, { useEffect, useState } from "react";
import { Post } from "../types";
import { fetchPosts, fetchPost, createEventSource } from "../api";
import { PostCard } from "./PostCard";

export function Board() {
  const [posts, setPosts] = useState<Post[]>([]);

  useEffect(() => {
    fetchPosts().then(setPosts).catch(console.error);

    const es = createEventSource();
    es.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.type === "new_post") {
        fetchPost(event.hash)
          .then((post) => setPosts((prev) => [post, ...prev]))
          .catch(console.error);
      } else if (event.type === "delete") {
        setPosts((prev) => prev.filter((p) => p.hash !== event.hash));
      }
    };

    return () => es.close();
  }, []);

  return (
    <div className="masonry p-4">
      {posts.map((post) => (
        <PostCard key={post.hash} post={post} />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Implement SinglePost.tsx**

```tsx
// frontend/src/components/SinglePost.tsx
import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Post } from "../types";
import { fetchPost } from "../api";
import { PostCard } from "./PostCard";

export function SinglePost() {
  const { hash } = useParams<{ hash: string }>();
  const [post, setPost] = useState<Post | null>(null);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!hash) return;
    fetchPost(hash)
      .then(setPost)
      .catch(() => setNotFound(true));
  }, [hash]);

  if (notFound) return <div className="p-8 text-white">Post not found.</div>;
  if (!post) return <div className="p-8 text-white">Loading...</div>;

  return (
    <div className="max-w-xl mx-auto p-8">
      <PostCard post={post} />
    </div>
  );
}
```

- [ ] **Step 3: Implement App.tsx**

```tsx
// frontend/src/App.tsx
import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Board } from "./components/Board";
import { SinglePost } from "./components/SinglePost";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-zinc-950">
        <Routes>
          <Route path="/" element={<Board />} />
          <Route path="/post/:hash" element={<SinglePost />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
```

- [ ] **Step 4: Implement main.tsx**

```tsx
// frontend/src/main.tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] **Step 5: Implement index.css with masonry styles**

```css
/* frontend/src/index.css */
@import "tailwindcss";

.masonry {
  column-count: 4;
  column-gap: 1rem;
}

@media (max-width: 1024px) { .masonry { column-count: 3; } }
@media (max-width: 768px)  { .masonry { column-count: 2; } }
@media (max-width: 480px)  { .masonry { column-count: 1; } }
```

Note: Tailwind v4 uses `@import "tailwindcss"` instead of the v3 `@tailwind` directives.

- [ ] **Step 6: Build to verify no errors**

```bash
cd frontend
npm run build
```

Expected: `dist/` created with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: Board, SinglePost, App router — complete React frontend"
```

---

## Chunk 6: Infrastructure (Nginx, systemd, deploy script)

### Task 13: Nginx configuration

**Files:**
- Create: `nginx/board.conf`
- Create: `nginx/token-generator.conf`

- [ ] **Step 1: Write board.conf**

```nginx
# nginx/board.conf
server {
    listen 443 ssl;
    server_name board.example.com;

    ssl_certificate     /etc/letsencrypt/live/board.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/board.example.com/privkey.pem;
    ssl_protocols TLSv1.3;

    access_log off;
    error_log /var/log/nginx/board_error.log warn;

    # static media (images, videos, OG images)
    location /media/ {
        alias /var/board/media/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # API (FastAPI)
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SSE: disable buffering
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }

    # React frontend (static files)
    location / {
        root /var/www/board;
        try_files $uri $uri/ /index.html;
        expires -1;
    }
}

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name board.example.com;
    return 301 https://$host$request_uri;
}
```

- [ ] **Step 2: Write token-generator.conf**

```nginx
# nginx/token-generator.conf
server {
    listen 443 ssl;
    server_name token.example.com;

    ssl_certificate     /etc/letsencrypt/live/token.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/token.example.com/privkey.pem;
    ssl_protocols TLSv1.3;

    access_log off;
    error_log /var/log/nginx/token_error.log warn;

    location / {
        root /var/www/token-generator;
        try_files $uri $uri/ /index.html;
        expires -1;
    }
}

server {
    listen 80;
    server_name token.example.com;
    return 301 https://$host$request_uri;
}
```

- [ ] **Step 3: Commit**

```bash
git add nginx/
git commit -m "chore: nginx config for board and token generator with TLS 1.3 and access_log off"
```

---

### Task 14: systemd services and deploy script

**Files:**
- Create: `deploy/signal-cli.service`
- Create: `deploy/board.service`
- Create: `deploy/setup.sh`

- [ ] **Step 1: Write signal-cli.service**

```ini
# deploy/signal-cli.service
[Unit]
Description=signal-cli JSON-RPC daemon
After=network.target

[Service]
Type=simple
User=signal
ExecStart=/usr/local/bin/signal-cli --config /var/signal-cli daemon --socket /var/run/signal-cli/socket
Restart=on-failure
RestartSec=5
RuntimeDirectory=signal-cli
RuntimeDirectoryMode=0750

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Write board.service (FastAPI backend)**

```ini
# deploy/board.service
[Unit]
Description=Board FastAPI backend
After=network.target postgresql.service signal-cli.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/board/backend
EnvironmentFile=/etc/board.env
ExecStart=/opt/board/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Note: `/etc/board.env` is a plain `KEY=VALUE` file (no `export`, no quotes). Example:
```
TOTP_SECRET=BASE32SECRETHERE
ADMIN_TOKEN=changeme
DATABASE_URL=postgresql+asyncpg://board:password@localhost/board
MEDIA_DIR=/var/board/media
```

- [ ] **Step 3: Write setup.sh**

```bash
#!/usr/bin/env bash
# deploy/setup.sh — one-shot VPS bootstrap
set -euo pipefail

echo "==> Installing system packages"
apt-get update -qq
apt-get install -y -qq nginx certbot python3-certbot-nginx ffmpeg \
    postgresql python3.12 python3.12-venv default-jre-headless

echo "==> Installing signal-cli"
SIGNAL_CLI_VERSION="0.13.2"
wget -q "https://github.com/AsamK/signal-cli/releases/download/v${SIGNAL_CLI_VERSION}/signal-cli-${SIGNAL_CLI_VERSION}-Linux.tar.gz" \
    -O /tmp/signal-cli.tar.gz
tar -xzf /tmp/signal-cli.tar.gz -C /usr/local/
ln -sf "/usr/local/signal-cli-${SIGNAL_CLI_VERSION}/bin/signal-cli" /usr/local/bin/signal-cli

echo "==> Creating postgres database"
sudo -u postgres createuser board --no-superuser --no-createdb --no-createrole || true
sudo -u postgres createdb board --owner board || true

echo "==> Creating directories"
mkdir -p /var/board/media /var/www/board /var/www/token-generator /opt/board
chown -R www-data:www-data /var/www/ /var/board/

echo "==> Creating signal user and config directory"
useradd --system --no-create-home signal || true
mkdir -p /var/signal-cli
chown signal:signal /var/signal-cli

echo "==> Installing systemd services"
cp deploy/signal-cli.service /etc/systemd/system/
cp deploy/board.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable signal-cli board

echo "==> Copying nginx configs"
cp nginx/board.conf /etc/nginx/sites-enabled/board.conf
cp nginx/token-generator.conf /etc/nginx/sites-enabled/token-generator.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo ""
echo "==> Next steps (run in order):"
echo "1. Register Signal number (as signal user):"
echo "   sudo -u signal signal-cli --config /var/signal-cli -u +1XXXXXXXXXX register"
echo "2. Verify with SMS code:"
echo "   sudo -u signal signal-cli --config /var/signal-cli -u +1XXXXXXXXXX verify <code>"
echo "3. Create /etc/board.env with TOTP_SECRET, ADMIN_TOKEN, DATABASE_URL, MEDIA_DIR"
echo "4. Deploy backend:   cp -r backend/ /opt/board/ && cd /opt/board/backend && python3.12 -m venv /opt/board/venv && /opt/board/venv/bin/pip install -e ."
echo "5. Run migrations:   cd /opt/board/backend && /opt/board/venv/bin/alembic upgrade head"
echo "6. Start services:   systemctl start signal-cli board"
echo "7. Issue TLS certs:  certbot --nginx -d board.example.com -d token.example.com"
echo "8. Deploy frontend:  cp -r frontend/dist/* /var/www/board/"
echo "9. Deploy token-gen: cp -r token-generator/dist/* /var/www/token-generator/"
```

- [ ] **Step 4: Make setup.sh executable and commit**

```bash
chmod +x deploy/setup.sh
git add deploy/
git commit -m "chore: signal-cli and board systemd services, VPS bootstrap script"
```

---

## Chunk 7: End-to-end verification

### Task 15: End-to-end smoke test

This task is done manually on the deployed VPS. There is no automated test for live Signal message delivery.

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 2: Verify signal-cli is receiving messages**

```bash
systemctl status signal-cli
journalctl -u signal-cli -f
```

Send a Signal message from a test phone to the board number. Expected: message appears in journal.

- [ ] **Step 3: Test valid TOTP post (BDD Scenario 1)**

On the Token Generator site, copy the current 6-digit code. Send `<code> hello world` to the board Signal number. Wait up to 10 seconds.

Expected: post appears at the top of the public board at `https://board.example.com` without refreshing.

- [ ] **Step 4: Test expired TOTP (BDD Scenario 2)**

Wait for a code to expire (visible on the Token Generator countdown). Send the expired code.

Expected: no new post appears on the board.

- [ ] **Step 5: Test direct link (BDD Scenario 3)**

Click "Copy Link" on a post. Paste into a new tab.

Expected: `/post/{hash}` renders the post in isolation.

- [ ] **Step 6: Test admin delete**

```bash
curl -X DELETE https://board.example.com/api/admin/posts/<hash> \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

Expected: `{"ok": true}`. Post disappears from board without refresh (SSE delete event).

- [ ] **Step 7: Final commit**

```bash
git add .
git commit -m "chore: end-to-end verification complete"
```
