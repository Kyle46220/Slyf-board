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

    media_dir = Path(settings.media_dir) / hash
    if media_dir.exists():
        shutil.rmtree(media_dir)

    post.deleted = True
    post.body = None
    post.media_path = None
    post.og_title = None
    post.og_description = None
    post.og_image_path = None
    await db.commit()

    await broadcaster.publish({"type": "delete", "hash": hash})
    return {"ok": True}
