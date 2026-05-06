## Install as a library

Currently you can install this package from Github:

    $ uv add TODO

## Run the demos

    $ uv sync -U --all-groups --all-extras
    $ uv run uvicorn --port 8001 --workers 1 demo1:app
    $ uv run uvicorn --port 8001 --workers 1 demo2:app
