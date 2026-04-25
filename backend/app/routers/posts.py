from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from app.database import get_db
from app.models import Post
from app.schemas import PostOut
from app.sse import broadcaster

router = APIRouter(prefix="/api")

# Create limiter with proper key function
def get_remote_address(request: Request):
    """Get client IP address for rate limiting."""
    if request.client:
        return request.client.host
    return "unknown"

limiter = Limiter(key_func=get_remote_address)


@router.get("/posts", response_model=list[PostOut])
@limiter.limit("1000/hour")
async def list_posts(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Post).where(Post.deleted == False).order_by(Post.id.desc())
    )
    return result.scalars().all()


@router.get("/posts/{hash}", response_model=PostOut)
@limiter.limit("100/hour")
async def get_post(hash: str, request: Request, db: AsyncSession = Depends(get_db)):
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
        background=None,
    )
