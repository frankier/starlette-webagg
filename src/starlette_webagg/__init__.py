from contextlib import asynccontextmanager


import io
import mimetypes
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket

from starlette_webagg.utils import SyncWebSocket

import matplotlib as mpl
from matplotlib.backends.backend_webagg import (
    FigureManagerWebAgg, new_figure_manager_given_figure)


managers = {}


def get_head_content(request):
    from json import dumps
    head_bits = []
    for css_file in ["page", "boilerplate", "fbm", "mpl"]:
        static_url = request.url_for("webagg:static", path=f"css/{css_file}.css")
        head_bits.append(
            f"""
                <link rel="stylesheet" href="{ static_url }" type="text/css">
            """.strip()
        )
    mpl_js_uri = request.url_for("webagg:mpl_js")
    head_bits.append(f"""
        <script src="{ mpl_js_uri }"></script>
    """.strip())
    head_bits.append("""
        <script>
        function download_callback(template) {
            return function(fig, fmt) {
                var uri = template.replace("{fmt}", fmt);
                window.open(uri, '_blank');
            };
        }

        window._mpl_webagg_websocket_type = mpl.get_websocket_type();
        </script>
    """.strip())
    return "\n".join(head_bits)


def figure_html_from_id(app, fig_id):
    from json import dumps
    ws_uri = app.url_path_for("webagg:websocket", fig_id=fig_id)
    ws_uri_str = dumps(ws_uri)
    download_fig_uri = app.url_path_for("webagg:download_fig", fig_id=fig_id, fmt="{fmt}")
    download_fig_uri_str = dumps(download_fig_uri)
    return f"""
    <div></div>
    <script>
    // mpl.figure creates a new figure on the webpage.
    new mpl.figure(
        // A unique numeric identifier for the figure
        {fig_id},
        // A websocket object (or something that behaves like one)
        new window._mpl_webagg_websocket_type({ws_uri_str}),
        // A function called when a file type is selected for download
        download_callback({download_fig_uri_str}),
        // The HTML element in which to place the figure
        document.currentScript.previousElementSibling
    );
    </script>
    """


def figure_html(app, figure):
    manager = new_figure_manager_given_figure(id(figure), figure)
    fig_id = manager.num
    managers[fig_id] = manager
    return figure_html_from_id(app, fig_id)


def get_mpl_js(request):
    js_content = FigureManagerWebAgg.get_javascript()
    images_url = request.url_for("webagg:data", path="images/")
    js_content = js_content.replace("'_images/'", f"'{images_url}'")
    return Response(js_content, media_type="application/javascript")


async def download_fig(request):
    fig_id = request.path_params["fig_id"]
    fmt = request.path_params["fmt"]
    app = request.app
    if fig_id not in managers:
        raise HTTPException(status_code=404, detail="Figure not found; It may have expired.")
    manager = managers[fig_id]
    buff = io.BytesIO()
    manager.canvas.figure.savefig(buff, format=fmt)
    resp_text = buff.getvalue()
    media_type = mimetypes.types_map.get(fmt, 'binary')
    return Response(resp_text, media_type=media_type)


async def handle_websocket(websocket):
    fig_id = websocket.path_params["fig_id"]
    supports_binary = True
    added = False
    fig_ids = []
    sync_websocket = SyncWebSocket(websocket)
    try:
        await websocket.accept()
        async for message in websocket.iter_json():
            msg_fig_id = message["figure_id"]
            if msg_fig_id != fig_id:
                continue
            fig_ids.append(fig_id)
            manager = managers[fig_id]
            if not added:
                manager.add_web_socket(sync_websocket)
                added = True
            if message['type'] == 'supports_binary':
                supports_binary = message['value']
            else:
                manager.handle_json(message)
    finally:
        await websocket.close()
        for fig_id in fig_ids:
            if fig_id is not None and fig_id in managers:
                manager = managers[fig_id]
                manager.remove_web_socket(sync_websocket)
                del managers[fig_id]


def get_app():
    routes = [
        Mount('/_static', app=StaticFiles(directory=FigureManagerWebAgg.get_static_file_path()), name="static"),
        Mount('/_data', app=StaticFiles(directory=mpl.get_data_path()), name="data"),
        Route('/mpl.js', get_mpl_js, name="mpl_js"),
        WebSocketRoute('/ws/{fig_id:int}', handle_websocket, name="websocket"),
        Route('/download/{fig_id:int}.{fmt}', download_fig, name="download_fig"),
    ]
    app = Starlette(routes=routes)
    return app
