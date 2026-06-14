"""
Backend API tests.

Uses FastAPI's TestClient (backed by httpx) so tests run entirely in-process
against a real SQLite database placed in a temporary directory (configured by
conftest.py before any app modules are imported).

Heavy external dependencies (git, Docker, file-system watcher) are either
naturally no-ops when no repo is initialised or are patched for the test scope.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Shared client fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Start the app once per module; the lifespan runs init_db, scheduler,
    and watcher against the temp directories set up in conftest.py."""
    from app.main import app

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# /healthz
# ---------------------------------------------------------------------------

def test_healthz(client: TestClient):
    """Health-check returns 200 with plain-text 'ok'."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.text == "ok"


# ---------------------------------------------------------------------------
# /version
# ---------------------------------------------------------------------------

def test_version_returns_json(client: TestClient):
    """Version endpoint returns a JSON object with a 'version' key."""
    resp = client.get("/version")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    # Must be a non-empty string; exact value depends on the VERSION file.
    assert isinstance(body["version"], str)
    assert body["version"] != ""


def test_version_matches_file(client: TestClient):
    """Returned version matches the VERSION file at the repo root."""
    from pathlib import Path

    # Locate the VERSION file relative to the backend package.
    version_file = Path(__file__).parent.parent.parent / "VERSION"
    if version_file.is_file():
        expected = version_file.read_text().strip()
        resp = client.get("/version")
        assert resp.json()["version"] == expected


# ---------------------------------------------------------------------------
# /api/logs
# ---------------------------------------------------------------------------

def test_api_logs_returns_list(client: TestClient):
    """Log endpoint returns a JSON array (may be empty on a fresh instance)."""
    resp = client.get("/api/logs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# /api/settings  (GET + PUT round-trip)
# ---------------------------------------------------------------------------

def test_api_settings_get(client: TestClient):
    """GET /api/settings returns the default SettingsOut schema."""
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    body = resp.json()
    # Required fields from SettingsOut
    for field in ("repo_url", "branch", "sync_mode", "auto_push", "initialized"):
        assert field in body, f"Missing field: {field}"
    assert body["initialized"] is False  # fresh DB


def test_api_settings_put(client: TestClient):
    """PUT /api/settings persists a field change and echoes it back."""
    resp = client.put(
        "/api/settings",
        json={"git_author_name": "Test Author", "git_author_email": "test@example.com"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["git_author_name"] == "Test Author"
    assert body["git_author_email"] == "test@example.com"


# ---------------------------------------------------------------------------
# /api/status
# ---------------------------------------------------------------------------

def test_api_status_uninitialized(client: TestClient):
    """Status returns a valid payload even when no git repo is set up."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured"] is False
    assert "activity" in body
    assert "docker_available" in body


# ---------------------------------------------------------------------------
# /api/services/toggle  and  /api/excludes/toggle
# ---------------------------------------------------------------------------

def test_api_services_toggle(client: TestClient):
    """Toggling a service stores the setting and returns ok."""
    resp = client.post(
        "/api/services/toggle",
        json={"name": "my-service", "enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # Toggle it back on
    resp = client.post(
        "/api/services/toggle",
        json={"name": "my-service", "enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_api_excludes_toggle(client: TestClient):
    """Toggling an exclusion rule stores the setting and returns ok."""
    resp = client.post(
        "/api/excludes/toggle",
        json={"path": "my-service/data", "enabled": True},
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# /api/services  (list – empty on fresh DB with empty services dir)
# ---------------------------------------------------------------------------

def test_api_services_list(client: TestClient):
    """Service list returns an array (empty when services_dir has no subdirs)."""
    resp = client.get("/api/services")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# /api/compose-projects
# ---------------------------------------------------------------------------

def test_api_compose_projects_no_docker(client: TestClient):
    """compose-projects endpoint returns an empty list when Docker is unavailable."""
    with patch("app.core.docker_client.available", return_value=False):
        resp = client.get("/api/compose-projects")
    assert resp.status_code == 200
    assert resp.json() == []
