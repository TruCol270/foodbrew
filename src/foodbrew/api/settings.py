"""Runtime configuration, all environment-driven with local-dev defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    web_dist: Path
    #: The one shared password for the hosted single instance (M6 decision #1).
    #: None means no gate is installed at all, which is what local development
    #: and the test suite want. A blank or whitespace-only value is treated as
    #: None rather than as a password that anything could match.
    access_password: str | None = None


def load_settings() -> Settings:
    supplied = os.environ.get("FOODBREW_ACCESS_PASSWORD", "").strip()
    return Settings(
        db_path=Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db")),
        web_dist=Path(os.environ.get("FOODBREW_WEB_DIST", "web/dist")),
        access_password=supplied or None,
    )
