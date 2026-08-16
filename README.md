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

## The kitchen trial

From a verdict, "Plan a kitchen trial for this" generates a protocol from that
verdict's own open questions — the rules that could not settle, and the values
that are missing. You never face a blank form.

- **Log a batch** as you make it: size, minutes, difficulty, where the enzyme went
  in the sequence, and an optional measured pH.
- **Room-temperature storage** is offered only for a batch measured below pH 4.6.
  Without that reading the schedule stays refrigerated, and the tool says why.
- **Record what you saw** — taste, using it, what it did to the food, the jar in
  storage. Tick "compared against an undressed portion" or "someone handed it to
  me" when they are true; each makes that one record a little stronger.
- **Log a meal** to capture symptoms. The dose you actually delivered is worked
  out against the evidence threshold as you type, so a null result can be read as
  an under-dose rather than as a failure.
- **Stop a trial** at any point. Everything recorded stays; the report says the
  trial was stopped rather than presenting part of a run as a whole one.

Nothing recorded at home changes a prediction. Observations are stored beside the
verdict they test and shown in a second column, and the report splits them by how
much weight they carry: your taste and usability answers as findings, uncontrolled
texture notes as observations, and symptom results as questions for a food
scientist with the dose arithmetic attached.

A measured batch pH does feed forward: later evaluations of that formulation use
it in place of the estimate, and any earlier evaluation shows the "data changed"
banner until you re-run it.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
    make report EVAL=<evaluation id>   # the markdown export, from a running server
    make trial TRIAL=<trial id>        # the trial as JSON, from a running server
