def test_health_reports_the_engine_version(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"] == "1.0.0"


def test_unknown_resource_is_404(client):
    assert client.get("/api/v1/recipes/nope").status_code == 404


def test_validation_rejection_is_422_with_the_founder_facing_message(client):
    response = client.post("/api/v1/recipes", json={"name": "empty", "ingredients": []})
    assert response.status_code == 422
    assert "at least one ingredient" in response.json()["detail"].lower()


def test_a_missing_web_build_does_not_break_the_api(client):
    """The API must be usable before the frontend has ever been built."""
    assert client.get("/api/v1/health").status_code == 200


def test_startup_creates_the_database_if_it_is_missing(tmp_path):
    from fastapi.testclient import TestClient

    from foodbrew.api.app import create_app
    from foodbrew.api.settings import Settings

    path = tmp_path / "fresh" / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        assert client.get("/api/v1/enzymes").json()
    assert path.exists()
