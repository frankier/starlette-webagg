from contextvars import ContextVar
from typing import Tuple, Any, Optional


from matplotlib import _api
from matplotlib.backends.backend_webagg_core import FigureCanvasWebAggCore, FigureManagerWebAgg, NavigationToolbar2WebAgg
from matplotlib.backend_bases import _Backend


_new_figs: ContextVar[Optional[Tuple[Any, Any]]] = ContextVar("request_var", default=None)


def add_fig(html):
    _new_figs.set((html, _new_figs.get()))


def consume_figs():
    cur = _new_figs.get()
    while cur is not None:
        assert isinstance(cur, tuple)
        html, cur = cur
        yield html
    _new_figs.set(None)


class FigureManagerWebAggWithShow(FigureManagerWebAgg):
    _toolbar2_class = NavigationToolbar2WebAgg

    def show(self):
        from starlette_webagg.middleware import get_current_app
        from starlette_webagg.starlette_app import add_manager, figure_html_from_id
        app = get_current_app()
        add_manager(self)
        html = figure_html_from_id(self.num, target="modal", app=app)
        add_fig(html)


class FigureCanvasWebAggWithShow(FigureCanvasWebAggCore):
    manager_class = _api.classproperty(lambda cls: FigureManagerWebAggWithShow)


@_Backend.export
class _BackendWebAggWithShow(_Backend):
    FigureCanvas = FigureCanvasWebAggWithShow
    FigureManager = FigureManagerWebAggWithShow
