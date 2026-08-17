import sqlite3

import pytest

from foodbrew.tools.snapshot import main, snapshot


def _seeded(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE observation (id TEXT PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO observation VALUES ('o1', 'clearly softer')")
    conn.commit()
    conn.close()
    return path


def test_the_copy_carries_the_rows(tmp_path):
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "copy.db")
    rows = sqlite3.connect(out).execute("SELECT note FROM observation").fetchall()
    assert rows == [("clearly softer",)]


def test_the_copy_is_a_real_database_not_a_file_copy(tmp_path):
    """VACUUM INTO produces a consistent database even mid-write, which a plain
    shutil.copy of a live file does not.
    """
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "copy.db")
    assert sqlite3.connect(out).execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_an_existing_destination_is_replaced(tmp_path):
    """VACUUM INTO refuses to write to a path that exists, and this job runs
    daily onto the same path.
    """
    src = _seeded(tmp_path / "live.db")
    out = tmp_path / "copy.db"
    out.write_bytes(b"yesterday")
    assert snapshot(src, out).exists()
    assert sqlite3.connect(out).execute("SELECT count(*) FROM observation").fetchone()[0] == 1


def test_the_destination_directory_is_created(tmp_path):
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "nested" / "deeper" / "copy.db")
    assert out.exists()


def test_a_missing_source_is_a_readable_error(tmp_path):
    with pytest.raises(FileNotFoundError) as caught:
        snapshot(tmp_path / "absent.db", tmp_path / "copy.db")
    assert "absent.db" in str(caught.value)


def test_main_prints_the_path_it_wrote(tmp_path, capsys):
    src = _seeded(tmp_path / "live.db")
    out = tmp_path / "copy.db"
    assert main([str(src), str(out)]) == 0
    assert str(out) in capsys.readouterr().out


def test_the_module_imports_nothing_outside_the_standard_library():
    """It runs inside the container with no app context (boundary rule)."""
    import pathlib

    text = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src" / "foodbrew" / "tools" / "snapshot.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("fastapi", "foodbrew.engine", "foodbrew.store", "foodbrew.api", "boto3"):
        assert forbidden not in text, f"snapshot.py imports {forbidden}"
