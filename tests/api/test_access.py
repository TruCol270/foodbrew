import base64

import pytest
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings

PASSWORD = "correct horse battery staple"


def _auth(password: str, user: str = "founder") -> dict:
    raw = f"{user}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


@pytest.fixture
def gated(tmp_path):
    app = create_app(
        Settings(
            db_path=tmp_path / "foodbrew.db",
            web_dist=tmp_path / "no-dist",
            access_password=PASSWORD,
        )
    )
    with TestClient(app) as client:
        yield client


def test_an_unauthenticated_request_is_refused(gated):
    response = gated.get("/api/v1/enzymes")
    assert response.status_code == 401


def test_the_refusal_asks_the_browser_to_prompt(gated):
    """Without this header a phone shows a bare error instead of a login box."""
    header = gated.get("/api/v1/enzymes").headers["www-authenticate"]
    assert header.lower().startswith("basic")
    assert "foodbrew" in header.lower()


def test_the_refusal_is_plain_english_and_leaks_nothing(gated):
    body = gated.get("/api/v1/enzymes").json()
    assert "private" in body["detail"].lower()
    assert PASSWORD not in body["detail"]


def test_the_right_password_gets_in(gated):
    response = gated.get("/api/v1/enzymes", headers=_auth(PASSWORD))
    assert response.status_code == 200
    assert response.json()


def test_the_username_is_ignored_on_purpose(gated):
    """One credential, not one account (decision #2)."""
    assert gated.get("/api/v1/enzymes", headers=_auth(PASSWORD, "anything")).status_code == 200


def test_a_wrong_password_is_refused(gated):
    assert gated.get("/api/v1/enzymes", headers=_auth("nope")).status_code == 401


def test_a_password_that_is_a_prefix_of_the_real_one_is_refused(gated):
    assert gated.get("/api/v1/enzymes", headers=_auth(PASSWORD[:-1])).status_code == 401


@pytest.mark.parametrize(
    "header",
    [
        "",
        "Bearer abc",
        "Basic",
        "Basic !!!not-base64!!!",
        "Basic " + base64.b64encode(b"\xff\xfe").decode(),
    ],
)
def test_a_malformed_authorization_header_is_refused_not_crashed(gated, header):
    """A bad header must be a 401, never a 500 — this endpoint is on the internet."""
    response = gated.get("/api/v1/enzymes", headers={"Authorization": header} if header else {})
    assert response.status_code == 401


def test_a_write_is_refused_too(gated):
    """The gate is not a read-only curtain; POST is the dangerous verb."""
    response = gated.post("/api/v1/recipes", json={"name": "x", "ingredients": []})
    assert response.status_code == 401


def test_the_health_check_needs_no_password(gated):
    """Fly's HTTP check has no credentials (decision #3)."""
    assert gated.get("/api/v1/health").status_code == 200


def test_the_health_check_leaks_no_founder_data(gated):
    body = gated.get("/api/v1/health").json()
    assert set(body) <= {"status", "engine_version", "database"}


def test_robots_needs_no_password(gated):
    assert gated.get("/robots.txt").status_code == 200


def test_no_gate_is_installed_when_no_password_is_set(client):
    """The existing suite and local dev must be untouched (decision #12)."""
    assert client.get("/api/v1/enzymes").status_code == 200


def test_the_noindex_header_is_on_a_refusal(gated):
    assert "noindex" in gated.get("/api/v1/enzymes").headers["x-robots-tag"]


def test_the_noindex_header_is_on_a_success(gated):
    response = gated.get("/api/v1/enzymes", headers=_auth(PASSWORD))
    assert "noindex" in response.headers["x-robots-tag"]


def test_robots_disallows_everything(gated):
    assert "Disallow: /" in gated.get("/robots.txt").text
