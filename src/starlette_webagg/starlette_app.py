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
from starlette_webagg.middleware import lifespan as webagg_lifespan, get_current_app
from starlette_webagg.withshow import (
    FigureManagerWebAggWithShow,
    new_figure_manager_given_figure,
)


def use_backend():
    mpl.use("module://starlette_webagg.withshow")


managers = {}


def get_head_content(core=False, app=None):
    if app is None:
        from starlette_webagg.middleware import get_current_app
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
    head_bits.append("""
        <script>
        mpl.figure.prototype.handle_newfig = function (fig, msg) {
            const template = document.createElement('template');
            template.innerHTML = msg.payload;
            const children = template.content.childNodes;
            Array.from(children).map(script => {
                if (script.tagName !== "SCRIPT") {
                    return script;
                }
                const new_script = document.createElement("script");
                
                for (attr of script.attributes) {
                    new_script.setAttribute(attr.name, attr.value) 
                }
                const script_text = document.createTextNode(script.innerHTML);
                new_script.appendChild(script_text);
                
                script.parentNode.replaceChild(new_script, script);
            });
            fig.root.append(...template.content.childNodes);
        };

        window._mpl_webaggext = (function() {
            function download_callback(template) {
                return function(fig, fmt) {
                    var uri = template.replace("{fmt}", fmt);
                    window.open(uri, '_blank');
                };
            }

            function new_fig(target, fig_id, ws_uri_str, download_fig_uri_str) {
                let websocket = new window._mpl_webagg_websocket_type(ws_uri_str);
                let fig = new mpl.figure(
                    // A unique numeric identifier for the figure
                    fig_id,
                    // A websocket object (or something that behaves like one)
                    websocket,
                    // A function called when a file type is selected for download
                    download_callback(download_fig_uri_str),
                    // The HTML element in which to place the figure
                    target
                );
                fig.focus_on_mouseover = true;
                websocket.addEventListener("close", function(event) {
                    console.log("Websocket closed", event);
                    const template = document.createElement('template');
                    template.innerHTML = (
                        "<div style='color: red; font-size: smaller; cursor: pointer'>" +
                        "Connection closed, this figure will no longer update. " +
                        "Click to refresh the page." +
                        "</div>"
                    );
                    let disconnected_msg = template.content.firstChild;
                    disconnected_msg.addEventListener("click", function() {
                        location.reload();
                    });
                    target.getElementsByClassName("mpl-toolbar")[0].prepend(disconnected_msg);
                });
            }

            window._mpl_webagg_websocket_type = mpl.get_websocket_type();
            return {
                new_fig: new_fig
            }
        })();
        </script>
    """.strip())
    return "\n".join(head_bits)


def add_manager(manager):
    fig_id = manager.num
    managers[fig_id] = manager


def figure_html_from_id(fig_id, target="inline", app=None):
    if app is None:
        from starlette_webagg.middleware import get_current_app
        app = get_current_app()
    ws_uri = app.url_path_for("webagg:websocket", fig_id=fig_id)
    from json import dumps
    ws_uri_str = dumps(ws_uri)
    download_fig_uri = app.url_path_for("webagg:download_fig", fig_id=fig_id, fmt="{fmt}")
    download_fig_uri_str = dumps(download_fig_uri)
    bits = []
    show_modal = ""
    if target == "inline":
        bits.append("<div></div>")
        target_js = "document.currentScript.previousElementSibling"
    elif target == "body":
        target_js = "document.body"
    elif target == "modal":
        bits.append(
            """
                <dialog closedby="any" style="padding: 1em; margin: 0 auto;"></dialog>
            """.strip()
        )
        target_js = "document.currentScript.previousElementSibling"
        show_modal = "document.currentScript.previousElementSibling.showModal();"
    else:
        raise ValueError(f"Invalid target: {target}")
    bits.append(
        f"""
        <script>
        {show_modal}
        _mpl_webaggext.new_fig(
            {target_js},
            {fig_id},
            {ws_uri_str},
            {download_fig_uri_str}
        );
        </script>
        """.strip()
    )
    return "\n".join(bits)


def figure_html(figure, target="inline", app=None):
    if app is None:
        from starlette_webagg.middleware import get_current_app
        app = get_current_app()
    manager = new_figure_manager_given_figure(id(figure), figure)
    add_manager(manager)
    return figure_html_from_id(manager.num, target=target, app=app)


def get_mpl_js(request):
    js_content = FigureManagerWebAggWithShow.get_javascript()
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
    from starlette_webagg.middleware import get_current_app
    from starlette_webagg.withshow import consume_figs
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
            if message['type'] == 'supports_binary':
                supports_binary = message['value']
            else:
                manager.handle_json(message)
            for fig in consume_figs():
                await websocket.send_json({
                    "type": "newfig",
                    "payload": fig
                })
    finally:
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
        WebSocketRoute('/ws/{fig_id:int}', handle_websocket, name="websocket"),
        Route('/download/{fig_id:int}.{fmt}', download_fig, name="download_fig"),
    ]
    app = Starlette(routes=routes, lifespan=webagg_lifespan)
    return app
