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

mpl.figure.prototype._root_extra_style = function (_canvas_div) {
    _canvas_div.classList.add("mpl-figure-root");
}

window._mpl_webaggext = (function() {
    function download_callback(template) {
        return function(fig, fmt) {
            var uri = template.replace("{fmt}", fmt);
            window.open(uri, '_blank');
        };
    }

    function new_fig(target, fig_id, ws_uri_str, download_fig_uri_str, on_close = "msg_discrete") {
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
        let close_cb;
        if (on_close == "msg_discrete") {
            close_cb = function(event) {
                const template = document.createElement('template');
                template.innerHTML = (
                    "<div style='color: red; font-size: smaller; cursor: pointer'>" +
                    "Connection closed, this figure will no longer update. " +
                    "Click to refresh the page." +
                    "</div>"
                );
                let disconnected_msg = template.content.firstElementChild;
                disconnected_msg.addEventListener("click", function() {
                    location.reload();
                });
                target.getElementsByClassName("mpl-toolbar")[0].prepend(disconnected_msg);
            };
        } else if (on_close == "msg_disable") {
            close_cb = function(event) {
                console.log("websocket close")
                const template = document.createElement('template');
                template.innerHTML = `
                    <div style="
                        position: absolute;
                        top: 0;
                        left: 0;
                        height: 100%;
                        width: 100%;
                        text-align: center;
                        background: rgba(255, 255, 255, 0.5);
                        font-size: 24pt;
                        line-height: 2;
                        padding: 1em;
                        padding-top: 20%;
                        cursor: pointer;">
                        Connection closed, this figure will no longer update.<br>
                        Click to refresh the page.
                    </div>`
                let disconnected_msg = template.content.firstElementChild;
                console.log("disconnected");
                console.log(disconnected_msg);
                disconnected_msg.addEventListener("click", function() {
                    location.reload();
                });
                fig.canvas_div.append(disconnected_msg);
            };
        } else if (on_close == "remove") {
            close_cb = function(event) {
                fig.root.remove();
            };
        } else if (Array.isArray(on_close) && on_close[0] == "remove_parent") {
            let selector = on_close[1];
            close_cb = function(event) {
                fig.root.closest(selector).remove();
            };
        }
        websocket.addEventListener("close", close_cb);
        return {
            figure: fig,
            websocket: websocket,
        }
    }

    function mk_modal(modal, fig) {
        modal.showModal();
        let start = Date.now();
        modal.addEventListener("cancel", (event) => {
            console.log("cancel event")
            let delay = Date.now() - start;
            // It's possible to for the mouseup event from the same click that opened the modal to close it without this delay
            if (delay < 1000) {
                event.preventDefault();
            }
        });
        modal.addEventListener("close", (e) => {
            console.log("close event");
            if (!fig.websocket) {
                return;
            }
            fig.websocket.close();
            delete fig.websocket;
            delete fig.figure;
        });
    }

    window._mpl_webagg_websocket_type = mpl.get_websocket_type();

    return {
        new_fig: new_fig,
        mk_modal: mk_modal
    };
})();
