import io
import mimetypes
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.routing import Route, Mount, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocketState

from mplbed.utils import SyncWebSocket

import matplotlib as mpl
from mplbed.middleware import lifespan as webagg_lifespan, get_current_app
from mplbed.withshow import (
    FigureManagerWebAggWithShow,
    FigureCollector,
    new_figure_manager_given_figure,
)


def use_backend():
    mpl.use("module://mplbed.withshow")


managers = {}


def get_head_content(core=False, app=None):
    if app is None:
        from mplbed.middleware import get_current_app
        app = get_current_app()
    css_files = []
    if not core:
        css_files.extend(["page", "boilerplate", "fbm"])
    css_files.append("mpl")
    head_bits = []
    for css_file in css_files:
        static_url = app.url_path_for("webagg:static", path=f"css/{css_file}.css")
        head_bits.append(
            f"""
                <link rel="stylesheet" href="{ static_url }" type="text/css">
            """.strip()
        )
    mpl_js_uri = app.url_path_for("webagg:mpl_js")
    head_bits.append(f"""
        <script src="{ mpl_js_uri }"></script>
    """.strip())
    webaggext_js_uri = app.url_path_for("webagg:webaggext_js")
    head_bits.append(f"""
        <script src="{ webaggext_js_uri }"></script>
    """.strip())
    head_bits.append("""
        <style>
        .mpl-toolbar {
            position: relative;
            padding-bottom: 2em;
        }
        .mpl-message {
            position: absolute;
            left: 0;
            bottom: 0;
            white-space: nowrap;
            overflow-x: auto;
            width: 100%;
        }
        .mpl-figure-root {
            display: inline-flex !important;
            flex-direction: column;
        }
        </style>
    """.strip())
    return "\n".join(head_bits)


def add_manager(manager):
    fig_id = manager.num
    managers[fig_id] = manager


def figure_html_from_id(fig_id, target="inline", app=None, on_close="msg_discrete"):
    from json import dumps
    if app is None:
        from mplbed.middleware import get_current_app
        app = get_current_app()
    ws_uri = app.url_path_for("webagg:websocket", fig_id=fig_id)
    ws_uri_str = dumps(ws_uri)
    download_fig_uri = app.url_path_for("webagg:download_fig", fig_id=fig_id, fmt="{fmt}")
    download_fig_uri_str = dumps(download_fig_uri)
    container = ""
    setup_container = ""
    if target == "inline":
        container = "<div></div>"
        target_js = "document.currentScript.previousElementSibling"
    elif target == "body":
        target_js = "document.body"
    elif target == "modal":
        container = (
            """
            <dialog closedby="any" style="padding: 1em; margin: 0 auto;"></dialog>
            """.strip()
        )
        target_js = "document.currentScript.previousElementSibling"
        setup_container = (
            """
            _mpl_webaggext.mk_modal(document.currentScript.previousElementSibling, fig);
            """.strip()
        )
    else:
        raise ValueError(f"Invalid target: {target}")
    if on_close == "remove_dialog":
        on_close = ["remove_parent", "dialog"]
    on_close_js = dumps(on_close)
    create_figure = f"""
    let fig = _mpl_webaggext.new_fig(
        {target_js},
        {fig_id},
        {ws_uri_str},
        {download_fig_uri_str},
        {on_close_js}
    );
    """.strip()
    bits = (
        container,
        """
        <script>
        (function() {
        """.strip(),
        create_figure,
        setup_container,
        """
        })();
        </script>
        """.strip()
    )
    return "\n".join(bits)


def figure_html(figure, target="inline", app=None, on_close="msg_discrete"):
    if app is None:
        from mplbed.middleware import get_current_app
        app = get_current_app()
    manager = new_figure_manager_given_figure(id(figure), figure)
    add_manager(manager)
    return figure_html_from_id(manager.num, target=target, app=app, on_close=on_close)


def get_mpl_js(request):
    js_content = FigureManagerWebAggWithShow.get_javascript()
    images_url = request.url_for("webagg:data", path="images/")
    js_content = js_content.replace("'_images/'", f"'{images_url}'")
    return Response(js_content, media_type="application/javascript")


def get_webaggext_js(request):
    from importlib import resources as impresources
    import mplbed

    js_file = impresources.files(mplbed) / 'webaggext.js'
    with js_file.open() as f:
        contents = f.read()
    return Response(contents, media_type="application/javascript")


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
    from mplbed.middleware import get_current_app
    from mplbed.withshow import consume_figs
    app = get_current_app()
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
            collector = FigureCollector(target="modal", on_close="remove_dialog")
            if message['type'] == 'supports_binary':
                supports_binary = message['value']
            else:
                with collector:
                    manager.handle_json(message)
            for fig in collector.consume_many():
                await websocket.send_json({
                    "type": "newfig",
                    "payload": fig
                })
    finally:
        if websocket.client_state != WebSocketState.DISCONNECTED and websocket.application_state != WebSocketState.DISCONNECTED:
            await websocket.close()
        for fig_id in fig_ids:
            if fig_id is not None and fig_id in managers:
                manager = managers[fig_id]
                manager.remove_web_socket(sync_websocket)
                del managers[fig_id]


def get_app():
    routes = [
        Mount('/_static', app=StaticFiles(directory=FigureManagerWebAggWithShow.get_static_file_path()), name="static"),
        Mount('/_data', app=StaticFiles(directory=mpl.get_data_path()), name="data"),
        Route('/mpl.js', get_mpl_js, name="mpl_js"),
        Route('/webaggext.js', get_webaggext_js, name="webaggext_js"),
        WebSocketRoute('/ws/{fig_id:int}', handle_websocket, name="websocket"),
        Route('/download/{fig_id:int}.{fmt}', download_fig, name="download_fig"),
    ]
    app = Starlette(routes=routes)
    return app
