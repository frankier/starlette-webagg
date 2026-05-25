import asyncio
from contextlib import asynccontextmanager, AsyncExitStack

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.websockets import WebSocket


def composed_lifespan(*lifespans):
    @asynccontextmanager
    async def lifespan(app):
        async with AsyncExitStack() as stack:
            for inner_lifespan in lifespans:
                await stack.enter_async_context(inner_lifespan(app))
            for route in app.routes:
                if isinstance(route, Mount) and isinstance(route.app, Starlette):
                    await stack.enter_async_context(
                        route.app.router.lifespan_context(route.app),
                    )
            yield
    return lifespan


class SyncWebSocket:
    def __init__(self, websocket: WebSocket, loop: asyncio.AbstractEventLoop | None = None):
        self.websocket = websocket
        # If loop is not provided, use the running event loop
        self.loop = loop or asyncio.get_event_loop()

    def send_json(self, data):
        """Send JSON data synchronously"""
        return asyncio.ensure_future(
            self.websocket.send_json(data), loop=self.loop
        )

    def send_binary(self, data: bytes):
        """Send binary data synchronously"""
        return asyncio.ensure_future(
            self.websocket.send_bytes(data), loop=self.loop
        )
