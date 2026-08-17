from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings


def test_health_reports_the_database_is_readable(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"] == "1.0.0"
    assert body["database"] == "ok"


def test_health_is_503_when_the_database_cannot_be_read(tmp_path):
    """Decision #7: a machine serving 200 while every write fails is the blind
    spot this closes. Fly's HTTP check restarts on a non-200, so the status code
    is the load-bearing part, not the body.
    """
    path = tmp_path / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        # Replace the file with something that is not a database at all, which is
        # what a truncated or half-restored volume looks like.
        path.write_bytes(b"this is not a sqlite file")
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"


def test_the_failure_names_the_sqlite_error_for_the_operator(tmp_path):
    """So the cause is readable in `fly logs` without opening a shell."""
    path = tmp_path / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        client.get("/api/v1/health")
        path.write_bytes(b"not a database")
        detail = client.get("/api/v1/health").json()["database"]
        assert "ok" != detail
        assert detail
