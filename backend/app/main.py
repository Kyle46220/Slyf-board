import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
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
    post_hash = str(uuid.uuid4())
    media_dir = Path(settings.media_dir) / post_hash
    content_type = parsed["content_type"]
    media_path = None
    og_title = og_description = og_image_path = None

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
