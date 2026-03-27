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
