## Running the workbench

Local development, two terminals:

    make run     # FastAPI on :8000
    make web     # Vite dev server, proxying /api to :8000

Everything in one container:

    make up      # builds the frontend, serves it from uvicorn on :8000

The database is created on first boot at `FOODBREW_DB_PATH` (default
`data/foodbrew.db`) and is never overwritten afterwards. `make db` forces a
refresh of the reference tables from `seed/*.json` and discards edits to them.

## Working a verdict

From a verdict screen you can:

- **Apply a suggested change.** Each one copies the formulation, makes the change,
  and runs every rule again. Nothing is pre-cleared — you land in the comparison
  with both versions side by side.
- **Compare variants** at `/compare?ids=…`, up to six at a time. A row present on
  one side and absent on another says so rather than disappearing.
- **Print the report** or download the same content as Markdown from
  `/api/v1/export/<evaluation id>.md`.

## The database screen

`/database` edits any enzyme or food field. Anything you type is stored as your
own value and labelled that way. A value becomes *confirmed* only through the
proposals inbox on the same screen, where it arrives with a source citation —
that citation is what the label means.

Editing a record never changes an evaluation that has already run. Those runs
show a banner naming what changed and offering a re-run. "Reset to the shipped
values" restores one record from `seed/*.json`; the reset on the whole
reference set discards every edit to every enzyme and food.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
    make report EVAL=<evaluation id>   # the markdown export, from a running server
