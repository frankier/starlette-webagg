## Install as a library

Currently you can install this package from Github:

    $ uv add git+https://github.com/frankier/mplbed

## Run the examples

The documentation is currently limited to example code.

You can run the examples with the following commands:

    $ uv sync -U --all-groups --all-extras
    $ cd examples/starlette && uv run uvicorn --port 8001 --workers 1 one_fig:app
    $ cd examples/starlette && uv run uvicorn --port 8001 --workers 1 demo_popup:app
