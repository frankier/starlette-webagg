import contextlib
from contextvars import ContextVar


_app = None


def set_current_app(app):
    global _app
    _app = app


def get_current_app():
    return _app


@contextlib.asynccontextmanager
async def lifespan(app):
    global _app
    _app = app
    yield
    _app = None
