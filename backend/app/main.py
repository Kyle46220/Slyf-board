import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.database import SessionLocal
from app.models import Post
from app.routers import posts, admin
from app.signal_listener import listen
from app.media import process_image, process_video, scrape_og
from app.sse import broadcaster
from app.security import SecurityHeadersMiddleware
from app.validators import validate_text_length

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)
app_state = {"limiter": limiter}


async def handle_message(parsed: dict):
    """Ingest a validated, metadata-stripped Signal message into the DB."""
    # Validate text length
    body = parsed.get("body")
    if not validate_text_length(body):
        logger.warning(f"Post rejected: text length exceeds limit")
        return

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
                logger.warning(f"Image processing failed for post {post_hash}. Falling back to text.")
                content_type = "text"

    elif content_type == "video" and parsed.get("attachments"):
        src = Path(parsed["attachments"][0].get("filename", ""))
        if src.exists():
            out = process_video(src, media_dir)
            media_path = str(out) if out else None
            if not media_path:
                logger.warning(f"Video processing failed for post {post_hash}. Falling back to text.")
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
            body=body,
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


app = FastAPI(lifespan=lifespan, state=app_state)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.include_router(posts.router)
app.include_router(admin.router)
