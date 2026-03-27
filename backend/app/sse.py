import asyncio
import json
from typing import AsyncGenerator


class SSEBroadcaster:
    def __init__(self):
        self._queues: list[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()
        self._queues.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def publish(self, event: dict):
        for q in list(self._queues):
            await q.put(event)

    async def stream(self, q: asyncio.Queue) -> AsyncGenerator[str, None]:
        try:
            while True:
                event = await q.get()
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            self.unsubscribe(q)


broadcaster = SSEBroadcaster()
