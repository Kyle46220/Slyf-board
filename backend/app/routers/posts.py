from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from app.d1_client import d1
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
async def list_posts(request: Request):
    query = "SELECT * FROM posts WHERE deleted = 0 ORDER BY id DESC"
    results = await d1.execute(query)
    return results


@router.get("/posts/{hash}", response_model=PostOut)
@limiter.limit("100/hour")
async def get_post(hash: str, request: Request):
    query = "SELECT * FROM posts WHERE hash = ? AND deleted = 0"
    results = await d1.execute(query, [hash])
    if not results:
        raise HTTPException(status_code=404, detail="Post not found")
    return results[0]


@router.get("/stream")
async def stream_events():
    q = broadcaster.subscribe()
    return StreamingResponse(
        broadcaster.stream(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        background=None,
    )
