"""Live kiosk camera, relayed through the API.

The kiosk's laptop pushes full-quality JPEG frames over a WebSocket. Logged-in admins and operators
watch them as an MJPEG stream. Frames live only in memory: nothing is recorded. This works because
the API runs as a single process (no uvicorn --workers).
"""
import asyncio
import inspect
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import FastAPI, WebSocket

from app.core.db import get_db

MAX_FRAME = 2 * 1024 * 1024  # one full-resolution JPEG
LIVE_FOR = 3.0               # seconds without a frame before the fps reads 0
BOUNDARY = "frame"


@dataclass
class LiveFeed:
    device_id: int
    code: str
    jpeg: bytes = b""
    det: dict | None = None
    w: int = 0
    h: int = 0
    fps: float = 0.0
    count: int = 0                     # frames received; viewers wait for it to change
    last_at: float = 0.0               # time.monotonic() of the last frame
    last_frame_at: datetime | None = None
    viewers: int = 0
    bridge: WebSocket | None = None
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)

    @property
    def live(self) -> bool:
        """The laptop is connected. It only sends frames once someone watches, so a viewer must be able
        to open the stream before the first frame arrives."""
        return self.bridge is not None

    @property
    def fps_now(self) -> float:
        return self.fps if self.count and time.monotonic() - self.last_at < LIVE_FOR else 0.0

    async def put_frame(self, jpeg: bytes) -> None:
        now = time.monotonic()
        if self.last_at:
            self.fps = 0.9 * self.fps + 0.1 / max(now - self.last_at, 1e-3)
        self.jpeg, self.last_at, self.last_frame_at = jpeg, now, datetime.now(UTC)
        async with self.cond:
            self.count += 1
            self.cond.notify_all()

    async def wake_viewers(self) -> None:
        async with self.cond:
            self.cond.notify_all()

    async def tell_bridge(self) -> None:
        """The laptop only encodes frames while someone is watching."""
        if self.bridge is not None:
            try:
                await self.bridge.send_json({"viewers": self.viewers})
            except Exception:  # the bridge just went away; its own loop cleans up
                pass


feeds: dict[int, LiveFeed] = {}


@contextmanager
def short_db(app: FastAPI):
    """A DB session only for the auth check, so a long stream doesn't hold a pooled connection.
    Goes through get_db (and any test override of it)."""
    got = app.dependency_overrides.get(get_db, get_db)()
    if inspect.isgenerator(got):
        try:
            yield next(got)
        finally:
            got.close()
    else:
        yield got


def parse_meta(text: str) -> dict:
    meta = json.loads(text)
    return meta if isinstance(meta, dict) else {}


async def mjpeg(feed: LiveFeed):
    """Newest frame only: a slow viewer skips frames instead of falling behind. Ends when the bridge leaves."""
    seen = feed.count - 1 if feed.count else 0
    feed.viewers += 1
    await feed.tell_bridge()
    try:
        while True:
            async with feed.cond:
                while feed.count == seen and feed.bridge is not None:
                    await feed.cond.wait()
            if feed.count == seen:  # no new frame and the bridge is gone
                return
            seen, jpeg = feed.count, feed.jpeg
            yield (f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\n\r\n").encode() + jpeg + b"\r\n"
    finally:
        feed.viewers -= 1
        await feed.tell_bridge()
