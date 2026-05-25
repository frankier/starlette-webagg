from matplotlib.figure import Figure

from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Route, Mount

from mplbed import get_head_content, get_app as get_webagg_app, figure_html
from mplbed.utils import composed_lifespan


def homepage_template(*, head, fig1, fig2):
    return f"""<!DOCTYPE html>
<html lang="en">
  <head>
    {head}
    <title>matplotlib</title>
  </head>

  <body>
    <div style="display: flex">
      <div>
        <h2>Figure 1</h2>
        {fig1}
      </div>
      <div>
        <h2>Figure 2</h2>
        {fig2}
      </div>
    </div>
  </body>
</html>
"""


def create_figure():
    import numpy as np
    fig = Figure()
    ax = fig.add_subplot()
    t = np.arange(0.0, 3.0, 0.01)
    s = np.sin(2 * np.pi * t)
    ax.plot(t, s)
    return fig


def homepage(request):
    fig1 = create_figure()
    fig2 = create_figure()
    return Response(
        homepage_template(
            head=get_head_content(request),
            fig1=figure_html(request.app, fig1),
            fig2=figure_html(request.app, fig2),
        ),
        media_type='text/html'
    )


app = Starlette(
    debug=True,
    routes=[Route('/', homepage), Mount("/webagg", app=get_webagg_app(), name="webagg")],
    lifespan=composed_lifespan(),
)
