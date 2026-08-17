"""Take a consistent copy of the live database without stopping the app.

`VACUUM INTO` is SQLite's own supported way to copy a database that is being
written to: it runs inside a read transaction, so the result is a complete
database as of one instant rather than a smear of pages, which is what a plain
file copy of a live database gives you.

Deliberately stdlib only (M6 boundary rule). This runs via `python -m` inside
the deployed container, where there is no FastAPI app and no settings object,
and it must never be the reason the image needs another package.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_OUT = Path("/tmp/foodbrew-snapshot.db")


def snapshot(db_path: Path | str, out_path: Path | str) -> Path:
    """Write a consistent copy of `db_path` to `out_path` and return the path."""
    db_path, out_path = Path(db_path), Path(out_path)
    if not db_path.exists():
        raise FileNotFoundError(f"no database at {db_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # VACUUM INTO refuses a destination that already exists, and this job runs
    # on a schedule onto the same path every day.
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM INTO ?", (str(out_path),))
    finally:
        conn.close()
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    db = Path(args[0]) if args else Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db"))
    out = Path(args[1]) if len(args) > 1 else DEFAULT_OUT
    print(snapshot(db, out))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by the CI backup job
    raise SystemExit(main())
