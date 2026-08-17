# tests/test_fly_config.py
"""fly.toml holds settings whose failure mode is silent (M6 decision #8).

Fly volumes are 1:1 with machines, so two machines cannot corrupt one file —
Fly refuses to attach a volume twice. The hazard is a SECOND machine with its
OWN volume, which forks the SQLite database into two unsynchronised copies with
no error and no visible symptom. Nothing at runtime detects that, so the config
is asserted here instead.
"""

import pathlib
import tomllib

CONFIG = pathlib.Path(__file__).resolve().parents[1] / "fly.toml"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_fly_config_exists_and_parses():
    assert CONFIG.is_file()
    assert _config()["app"]


def test_the_volume_is_mounted_where_the_app_expects_the_database():
    config = _config()
    mount = config["mounts"][0] if isinstance(config["mounts"], list) else config["mounts"]
    assert mount["destination"] == "/data"
    assert config["env"]["FOODBREW_DB_PATH"].startswith("/data/")


def test_exactly_one_mount_is_declared():
    mounts = _config()["mounts"]
    assert len(mounts if isinstance(mounts, list) else [mounts]) == 1


def test_the_deploy_strategy_is_one_fly_allows_with_a_volume():
    """canary and bluegreen are refused outright for volume-backed apps, and
    both would mean two machines holding one database if they were not.
    """
    assert _config()["deploy"]["strategy"] in {"rolling", "immediate"}


def test_the_machine_is_never_stopped_out_from_under_her():
    """Decision #10: autostop has a documented report of firing below
    min_machines_running, and a cold start reads as a broken app on a phone.
    """
    service = _config()["http_service"]
    assert service["auto_stop_machines"] == "off"
    assert service["min_machines_running"] == 1


def test_the_service_points_at_the_port_the_app_listens_on():
    assert _config()["http_service"]["internal_port"] == 8000


def test_https_is_forced():
    assert _config()["http_service"]["force_https"] is True


def test_the_health_check_targets_the_real_endpoint():
    checks = _config()["http_service"]["checks"]
    assert any(check["path"] == "/api/v1/health" for check in checks)


def test_no_secret_is_written_into_the_config():
    """The password belongs in `fly secrets set`, never in a tracked file."""
    text = CONFIG.read_text(encoding="utf-8").lower()
    assert "foodbrew_access_password" not in text
    for leaky in ("password =", "secret =", "token ="):
        assert leaky not in text


def test_the_backup_workflow_reads_every_credential_from_secrets():
    workflow = (
        pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "backup.yml"
    ).read_text(encoding="utf-8")
    for name in (
        "FLY_API_TOKEN",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
        "R2_ENDPOINT",
    ):
        assert f"secrets.{name}" in workflow, f"{name} is not read from secrets"


def test_the_backup_verifies_the_copy_before_uploading_it():
    """An unverified backup is not a backup."""
    workflow = (
        pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "backup.yml"
    ).read_text(encoding="utf-8")
    assert "integrity_check" in workflow
    assert workflow.index("integrity_check") < workflow.index("aws s3 cp")
