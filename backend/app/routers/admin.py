import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Header
from app.config import settings
from app.d1_client import d1
from app.sse import broadcaster

router = APIRouter(prefix="/api/admin")


async def require_admin(authorization: str | None = Header(default=None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid admin token")


@router.delete("/posts/{hash}", dependencies=[Depends(require_admin)])
async def delete_post(hash: str):
    query = "SELECT id FROM posts WHERE hash = ?"
    results = await d1.execute(query, [hash])
    if not results:
        raise HTTPException(status_code=404, detail="Post not found")

    media_dir = Path(settings.media_dir) / hash
    if media_dir.exists():
        shutil.rmtree(media_dir)

    update_query = """
        UPDATE posts 
        SET deleted = 1, body = NULL, media_path = NULL, 
            og_title = NULL, og_description = NULL, og_image_path = NULL 
        WHERE hash = ?
    """
    await d1.execute(update_query, [hash])

    await broadcaster.publish({"type": "delete", "hash": hash})
    return {"ok": True}
