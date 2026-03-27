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
