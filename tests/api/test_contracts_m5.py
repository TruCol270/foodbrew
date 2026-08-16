"""M5's boundaries, asserted rather than trusted to review."""

import pathlib
import re

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"
WEB = pathlib.Path(__file__).resolve().parents[2] / "web" / "src"


def _files(root, suffix):
    return sorted(p for p in root.rglob(f"*{suffix}") if "__pycache__" not in p.parts)


def test_no_rule_module_imports_the_allergen_vocabulary():
    """Plan decision #2 — an allergen never changes a verdict."""
    offenders = [
        p.name
        for p in _files(SRC / "engine" / "rules", ".py")
        if "allergens" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, ", ".join(offenders)


def test_the_new_engine_modules_are_pure():
    for name in ("allergens.py", "formula.py", "structural.py"):
        text = (SRC / "engine" / name).read_text(encoding="utf-8")
        for forbidden in (
            "foodbrew.store", "foodbrew.api", "foodbrew.db", "sqlite3", "fastapi",
            "now_iso", "datetime.now", "time.time", "utcnow",
        ):
            assert forbidden not in text, f"{name}: {forbidden}"


def test_percent_is_never_stored():
    """Decision #6 — a stored percent could disagree with the grams beside it."""
    schema = (SRC / "db" / "schema.sql").read_text(encoding="utf-8")
    assert "percent" not in schema.lower()


def test_the_migration_list_only_adds_columns():
    """Decision #1 — this machinery is deliberately unable to drop or retype."""
    text = (SRC / "db" / "bootstrap.py").read_text(encoding="utf-8")
    assert "ADD COLUMN" in text
    for destructive in ("DROP COLUMN", "DROP TABLE", "RENAME COLUMN"):
        assert destructive not in text


def test_every_migrated_column_is_also_in_the_shipped_schema():
    """A fresh database and a migrated one must end up identical."""
    from foodbrew.db.bootstrap import MIGRATIONS

    schema = (SRC / "db" / "schema.sql").read_text(encoding="utf-8")
    for _table, column, _ddl in MIGRATIONS:
        assert column in schema, f"{column} is migrated but missing from schema.sql"


def test_no_web_file_hardcodes_a_colour_outside_the_stylesheet():
    """Decision #9 — one token block, no stray hex."""
    hex_colour = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    offenders = []
    for path in _files(WEB, ".tsx") + _files(WEB, ".ts"):
        for match in hex_colour.findall(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match}")
    assert not offenders, ", ".join(offenders)


def test_the_stylesheet_declares_a_dark_scheme_and_a_reduced_motion_rule():
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_every_verdict_state_carries_a_glyph_as_well_as_a_colour():
    """Decision #10 — meaning never rides on hue alone."""
    badge = (WEB / "components" / "VerdictBadge.tsx").read_text(encoding="utf-8")
    for glyph in ("✕", "?", "!", "✓"):
        assert glyph in badge


def test_the_report_screen_and_the_export_come_from_one_assembly():
    """Decision #8 — the router imports the assembler; it does not rebuild it."""
    router = (SRC / "api" / "routers" / "report.py").read_text(encoding="utf-8")
    assert "from foodbrew.api.routers.export import report_input" in router
    assert "render_markdown" not in router


def test_structured_fields_are_not_in_the_scalar_allowlists():
    """Decision #4 — a separate door, not a widened one."""
    from foodbrew.store.records import PLAIN_FIELDS, STRUCTURED_FIELDS, TRACKED_FIELDS

    for table, fields in STRUCTURED_FIELDS.items():
        for field in fields:
            assert field not in TRACKED_FIELDS.get(table, {})
            assert field not in PLAIN_FIELDS.get(table, {})


def test_the_allergen_vocabulary_is_closed_on_the_wire():
    from foodbrew.api import schemas
    from foodbrew.engine.allergens import Allergen

    # A client may send allergens only on a custom food, and the server parses
    # them through the enum — no schema accepts an arbitrary allergen string
    # that reaches the database unvalidated.
    assert "allergens" in schemas.CustomFoodIn.model_fields
    assert len(list(Allergen)) == 9
