import asyncio
import json
from typing import AsyncGenerator


class SSEBroadcaster:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []
        self._queue_status: dict[asyncio.Queue, bool] = {}

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._queues.append(q)
        self._queue_status[q] = True
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            if q in self._queues:
                self._queues.remove(q)
                self._queue_status.pop(q, None)
        except ValueError:
            pass

    def is_queue_active(self, q: asyncio.Queue) -> bool:
        return self._queue_status.get(q, False)

    async def publish(self, event: dict):
        # Only publish to active queues
        for q in list(self._queues):
            if self.is_queue_active(q):
                try:
                    await q.put(event)
                except asyncio.CancelledError:
                    # Queue was cancelled, mark as inactive
                    self._queue_status[q] = False
                except Exception as e:
                    print(f"Error publishing to queue: {e}")
                    self._queue_status[q] = False

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        yield ": connected\n\n"  # immediate flush so headers are sent
        try:
            while self.is_queue_active(q):
                try:
                    # Add timeout to prevent hanging on stale connections
                    event = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive ping to prevent connection timeout
                    yield ": keep-alive\n\n"
                    continue
                except asyncio.CancelledError:
                    break
        finally:
            self.unsubscribe(q)


broadcaster = SSEBroadcaster()
