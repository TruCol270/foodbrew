"""Spec §10 — prohibited words, extended to the frontend the founder reads.

Kept in pytest rather than a JS linter so one command checks the whole product
and the rule cannot be skipped by not running the web toolchain.
"""

import pathlib

import pytest

from foodbrew.engine.language import PROHIBITED_WORDS as PROHIBITED
from foodbrew.engine.language import contains_prohibited

WEB_SRC = pathlib.Path(__file__).resolve().parent.parent / "web" / "src"


def _source_files():
    return sorted(p for p in WEB_SRC.rglob("*.tsx")) + sorted(WEB_SRC.rglob("*.ts"))


@pytest.mark.skipif(not WEB_SRC.is_dir(), reason="frontend not present in this checkout")
@pytest.mark.parametrize("word", PROHIBITED)
def test_no_prohibited_word_appears_in_frontend_source(word):
    offenders = [
        path.relative_to(WEB_SRC)
        for path in _source_files()
        if word in contains_prohibited(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"'{word}' appears in: {', '.join(map(str, offenders))}"


@pytest.mark.skipif(not WEB_SRC.is_dir(), reason="frontend not present in this checkout")
def test_the_disclaimer_is_in_the_layout_not_a_single_screen():
    """§10 screen 8's footer must be unskippable — no route may render without it."""
    app = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    assert "Not a safety, efficacy, or regulatory determination." in app
