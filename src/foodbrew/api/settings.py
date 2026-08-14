"""Runtime configuration, all environment-driven with local-dev defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    web_dist: Path


def load_settings() -> Settings:
    return Settings(
        db_path=Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db")),
        web_dist=Path(os.environ.get("FOODBREW_WEB_DIST", "web/dist")),
    )
