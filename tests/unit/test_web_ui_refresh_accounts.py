from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import firefly_bank_importer.web_ui as web_ui
from firefly_bank_importer.web_ui import create_app

_ACCOUNTS = [
    {"id": 1, "name": "Lönekonto", "type": "asset"},
    {"id": 2, "name": "Sparkonto", "type": "asset"},
]


def _make_app(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    project_root = tmp_path / "project"
    project_root.mkdir()
    import_base = project_root / "bankImports"
    import_base.mkdir()

    monkeypatch.setattr(web_ui, "_PROJECT_ROOT", project_root)
    app = create_app(import_base)
    return TestClient(app)


def test_api_refresh_accounts_returns_summary(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """POST /api/refresh-accounts returns total_accounts and new_folders counts."""
    client = _make_app(tmp_path, monkeypatch)

    with (
        patch("firefly_bank_importer.web_ui.fetch_accounts_from_firefly", return_value=_ACCOUNTS),
        patch("firefly_bank_importer.web_ui.save_account_cache"),
        patch("firefly_bank_importer.web_ui._load_web_firefly_settings") as mock_settings,
    ):
        mock_settings.return_value = ("http://firefly.test", "tok", [])
        response = client.post("/api/refresh-accounts")

    assert response.status_code == 200
    data = response.json()
    assert data["total_accounts"] == 2
    assert "new_folders" in data
    assert isinstance(data["new_folders"], int)


def test_api_refresh_accounts_creates_import_folders(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """POST /api/refresh-accounts creates missing import folders and reports count."""
    client = _make_app(tmp_path, monkeypatch)
    import_base = web_ui._PROJECT_ROOT / "bankImports"

    with (
        patch("firefly_bank_importer.web_ui.fetch_accounts_from_firefly", return_value=_ACCOUNTS),
        patch("firefly_bank_importer.web_ui.save_account_cache"),
        patch("firefly_bank_importer.web_ui._load_web_firefly_settings") as mock_settings,
    ):
        mock_settings.return_value = ("http://firefly.test", "tok", [])
        response = client.post("/api/refresh-accounts")

    assert response.status_code == 200
    data = response.json()
    assert data["new_folders"] == 2
    assert (import_base / "kontoutdrag_Lonekonto").exists()
    assert (import_base / "kontoutdrag_Sparkonto").exists()


def test_api_refresh_accounts_skips_existing_folders(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """POST /api/refresh-accounts does not report pre-existing folders as new."""
    client = _make_app(tmp_path, monkeypatch)
    import_base = web_ui._PROJECT_ROOT / "bankImports"
    (import_base / "kontoutdrag_Lonekonto").mkdir()

    with (
        patch("firefly_bank_importer.web_ui.fetch_accounts_from_firefly", return_value=_ACCOUNTS),
        patch("firefly_bank_importer.web_ui.save_account_cache"),
        patch("firefly_bank_importer.web_ui._load_web_firefly_settings") as mock_settings,
    ):
        mock_settings.return_value = ("http://firefly.test", "tok", [])
        response = client.post("/api/refresh-accounts")

    assert response.status_code == 200
    assert response.json()["new_folders"] == 1


def test_api_refresh_accounts_returns_error_on_firefly_failure(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """POST /api/refresh-accounts returns 502 when Firefly is unreachable."""
    client = _make_app(tmp_path, monkeypatch)

    with (
        patch(
            "firefly_bank_importer.web_ui.fetch_accounts_from_firefly",
            side_effect=RuntimeError("Connection refused"),
        ),
        patch("firefly_bank_importer.web_ui._load_web_firefly_settings") as mock_settings,
    ):
        mock_settings.return_value = ("http://firefly.test", "tok", [])
        response = client.post("/api/refresh-accounts")

    assert response.status_code == 502
    assert "error" in response.json()["detail"]


def test_refresh_accounts_link_visible_on_index(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """The index page shows a link to the refresh-accounts action."""
    client = _make_app(tmp_path, monkeypatch)

    response = client.get("/")
    assert response.status_code == 200
    assert "refresh" in response.text.lower() or "Uppdatera konton" in response.text
