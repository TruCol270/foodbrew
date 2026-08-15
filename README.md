## Running the workbench

Local development, two terminals:

    make run     # FastAPI on :8000
    make web     # Vite dev server, proxying /api to :8000

Everything in one container:

    make up      # builds the frontend, serves it from uvicorn on :8000

The database is created on first boot at `FOODBREW_DB_PATH` (default
`data/foodbrew.db`) and is never overwritten afterwards. `make db` forces a
refresh of the reference tables from `seed/*.json` and discards edits to them.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
