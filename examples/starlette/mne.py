from matplotlib.figure import Figure
from matplotlib import pyplot as plt

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import Response
from starlette.routing import Route, Mount

from mplbed import get_head_content, get_app as get_webagg_app, figure_html, use_backend
from mplbed.middleware import lifespan as webagg_lifespan
from mplbed.utils import composed_lifespan

import mne


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


def homepage(request):
    use_backend()

    sample_data_folder = mne.datasets.sample.data_path()
    sample_data_raw_file = (
        sample_data_folder / "MEG" / "sample" / "sample_audvis_filt-0-40_raw.fif"
    )
    raw = mne.io.read_raw_fif(sample_data_raw_file)
    fig = raw.plot(show=False)

    return Response(
        homepage_template(
            head=get_head_content(request),
            fig=figure_html(fig, on_close="msg_disable")
        ),
        media_type='text/html'
    )


app = Starlette(
    debug=True,
    routes=[Route('/', homepage), Mount("/webagg", app=get_webagg_app(), name="webagg")],
    lifespan=webagg_lifespan
)
