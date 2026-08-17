# tests/api/test_contracts_m6.py
"""Cheap global guards for the hosted deploy, in the style of test_contracts.py."""

import pathlib

from fastapi.testclient import TestClient

from foodbrew.api.access import OPEN_PATHS
from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "foodbrew"


def test_the_gate_is_installed_whenever_a_password_is_configured(tmp_path):
    """The one thing that must never silently stop being true in production."""
    app = create_app(
        Settings(db_path=tmp_path / "db.sqlite", web_dist=tmp_path / "none", access_password="pw")
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/enzymes").status_code == 401


def test_every_open_path_returns_no_founder_data(tmp_path):
    """OPEN_PATHS is the attack surface. Anything added to it must be inert."""
    app = create_app(
        Settings(db_path=tmp_path / "db.sqlite", web_dist=tmp_path / "none", access_password="pw")
    )
    with TestClient(app) as client:
        for path in OPEN_PATHS:
            body = client.get(path).text.lower()
            for leak in ("vinaigrette", "lactase", "recipe", "formulation", "trial"):
                assert leak not in body, f"{path} leaks '{leak}'"


def test_the_open_path_set_is_small_and_explicit():
    assert OPEN_PATHS == {"/api/v1/health", "/robots.txt"}


def test_the_access_gate_reads_no_database():
    text = (SRC / "api" / "access.py").read_text(encoding="utf-8")
    for forbidden in ("sqlite3", "foodbrew.store", "foodbrew.engine", "connect("):
        assert forbidden not in text, f"access.py touches {forbidden}"


def test_the_gate_compares_in_constant_time():
    """A `==` here leaks the shared prefix length to a timing attack."""
    text = (SRC / "api" / "access.py").read_text(encoding="utf-8")
    code_lines = "\n".join(
        line for line in text.splitlines() if not line.strip().startswith("#")
    )
    assert "compare_digest" in code_lines


def test_no_tracked_file_contains_an_obvious_secret():
    for name in ("fly.toml", "docker-compose.yml", "Dockerfile", "README.md"):
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "foodbrew_access_password=" not in text
        assert "foodbrew_access_password:" not in text


def test_the_image_gained_no_python_dependency_for_the_deploy():
    """Decision #5: the S3 client lives in CI, never in the image."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for forbidden in ("boto3", "botocore", "litestream", "s3fs"):
        assert forbidden not in pyproject, f"{forbidden} crept into the image"
