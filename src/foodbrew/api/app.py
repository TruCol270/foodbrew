"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from foodbrew import ENGINE_VERSION
from foodbrew.api.routers import catalog, evaluations, formulations, recipes
from foodbrew.api.settings import Settings, load_settings
from foodbrew.db import ensure_database
from foodbrew.engine import ValidationRejection


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ensure_database, not create_database: a restart must never revert the
        # founder's edits to reference rows (plan decision #1).
        ensure_database(app.state.settings.db_path)
        yield

    app = FastAPI(title="FoodBrew", version=ENGINE_VERSION, lifespan=lifespan)
    app.state.settings = settings

    @app.exception_handler(ValidationRejection)
    async def _rejection(_: Request, exc: ValidationRejection) -> JSONResponse:
        # Spec §6.7 / §6.2 R14: degenerate input is refused, and the message is
        # the founder-facing one the rule wrote — not a stack trace.
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok", "engine_version": ENGINE_VERSION}

    for router in (catalog.router, recipes.router, formulations.router, evaluations.router):
        app.include_router(router, prefix="/api/v1")

    _mount_web(app, settings)
    return app


def _mount_web(app: FastAPI, settings: Settings) -> None:
    """Serve the built React app, if there is one.

    Absent (a fresh checkout, or the test suite) the API still works — the
    frontend is a client of this server, not a prerequisite for it.
    """
    dist = settings.web_dist
    if not dist.is_dir():
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Client-side routes fall through to index.html; /api never does,
        # because its routes are registered first and match first.
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
