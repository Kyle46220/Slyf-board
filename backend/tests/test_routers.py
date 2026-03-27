import anyio
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
    with anyio.move_on_after(2.0):
        async with client.stream("GET", "/api/stream") as resp:
            assert resp.headers["content-type"].startswith("text/event-stream")
            async for line in resp.aiter_lines():
                assert line.startswith(":")
                break
