# tests/api/test_settings.py
import pytest

from foodbrew.api.settings import load_settings


def test_the_access_password_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("FOODBREW_ACCESS_PASSWORD", raising=False)
    assert load_settings().access_password is None


def test_the_access_password_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("FOODBREW_ACCESS_PASSWORD", "hunter2")
    assert load_settings().access_password == "hunter2"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_password_is_treated_as_unset(monkeypatch, value):
    """An empty secret must not install a gate that accepts an empty password."""
    monkeypatch.setenv("FOODBREW_ACCESS_PASSWORD", value)
    assert load_settings().access_password is None
