from matplotlib.figure import Figure
from matplotlib import pyplot as plt

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import Response
from starlette.routing import Route, Mount

from mplbed import get_head_content, get_app as get_webagg_app, figure_html, use_backend
from mplbed.middleware import lifespan as webagg_lifespan
from mplbed.utils import composed_lifespan


def homepage_template(*, head, fig):
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    {head}
    <title>matplotlib</title>
  </head>

  <body>
    <div style="display: flex">
      <div>
        <h2>Figure</h2>
        {fig}
      </div>
    </div>
  </body>
</html>
"""


class PopupDemoMpl:
    def __init__(self):
        from matplotlib.widgets import Button
        import numpy as np
        self.fig = plt.figure()
        self.ax = self.fig.add_subplot()
        self.button = Button(self.ax, "Create popup global")
        self.button.on_clicked(self.create_popup)

    def create_popup(self, event):
        use_backend()
        self.popup_fig = plt.figure()
        ax = self.popup_fig.add_axes((0.01, 0.01, 0.98, 0.98))
        ax.set_axis_off()
        ax.text(0.42, 0.5, "Hello from the popup", ma="left", ha="left")
        self.popup_fig.show()

    def into_html(self, app=None):
        return figure_html(self.fig, app=app)


def homepage(request):
    use_backend()
    demo = PopupDemoMpl()
    return Response(
        homepage_template(
            head=get_head_content(request),
            fig=demo.into_html()
        ),
        media_type='text/html'
    )


app = Starlette(
    debug=True,
    routes=[Route('/', homepage), Mount("/webagg", app=get_webagg_app(), name="webagg")],
    lifespan=webagg_lifespan
)
