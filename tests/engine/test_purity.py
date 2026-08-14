import ast
import pathlib

ENGINE_DIR = pathlib.Path("src/foodbrew/engine")
FORBIDDEN = {"json", "sqlite3", "pathlib", "os", "foodbrew.db", "foodbrew.seedload"}


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_engine_never_imports_io_or_persistence():
    """Spec §4 dependency rule — engine/ is a pure functional core."""
    offenders = []
    for path in ENGINE_DIR.rglob("*.py"):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if module in FORBIDDEN or root in FORBIDDEN:
                offenders.append(f"{path}: imports {module}")
    assert offenders == [], "\n".join(offenders)
