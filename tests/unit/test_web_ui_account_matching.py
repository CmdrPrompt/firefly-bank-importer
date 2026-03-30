"""Tests for web UI account matching (TASK-017)."""

import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from firefly_bank_importer.import_firefly import Account
from firefly_bank_importer.web_ui import create_app


def _write_test_account_cache(accounts: list[Account]) -> Path:
    """Write accounts to a temporary cache file for testing."""
    cache_dir = Path(tempfile.gettempdir())
    cache_file = cache_dir / "accounts_cache.json"

    cache_data = {
        "fetched_at": "2026-03-28T12:00:00",
        "accounts": accounts,
    }
    cache_file.write_text(json.dumps(cache_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache_file


def test_selection_page_shows_account_matching_form(tmp_path: Path) -> None:
    """Test that /selection page shows account matching form with matching candidates."""
    # Create dummy CSV files
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    test_folder = import_folder / "SEB_Lonekonto"
    test_folder.mkdir()
    csv_file = test_folder / "2025-01.csv"
    csv_file.write_text("Bokföringsdata;Transaktionsdata;Belopp;Saldo\n2025-01-01;2025-01-01;100;1000\n")

    # Create mock account cache near the app
    accounts: list[Account] = [
        {"id": 1, "name": "SEB Lönekonto", "type": "asset"},
        {"id": 2, "name": "ICA Matkonto", "type": "asset"},
    ]

    # Monkeypatch load_account_cache by writing to a known location
    import firefly_bank_importer.import_firefly as imf

    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        cache_file = _write_test_account_cache(accounts)
        imf.ACCOUNT_CACHE_FILE = cache_file

        app = create_app(import_folder)
        client = TestClient(app)

        response = client.get("/selection?folder=SEB_Lonekonto")
        assert response.status_code == 200
        assert "Kontomappning" in response.text
        assert "SEB_Lonekonto" in response.text
        assert "SEB Lönekonto" in response.text
        assert "select" in response.text.lower()
        # Should NOT show ICA Matkonto since it doesn't match the folder name
        assert "ICA Matkonto" not in response.text
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path
        cache_file.unlink(missing_ok=True)


def test_selection_page_marks_unresolved_folders(tmp_path: Path) -> None:
    """Test that unresolved (unmatched) folders are marked with warning status."""
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    test_folder = import_folder / "unknown_folder_xyz"
    test_folder.mkdir()
    csv_file = test_folder / "2025-01.csv"
    csv_file.write_text("Bokföringsdata;Transaktionsdata;Belopp;Saldo\n2025-01-01;2025-01-01;100;1000\n")

    accounts: list[Account] = [
        {"id": 1, "name": "SEB Lönekonto", "type": "asset"},
    ]

    import firefly_bank_importer.import_firefly as imf

    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        cache_file = _write_test_account_cache(accounts)
        imf.ACCOUNT_CACHE_FILE = cache_file

        app = create_app(import_folder)
        client = TestClient(app)

        response = client.get("/selection?folder=unknown_folder_xyz")
        assert response.status_code == 200
        # Unresolved folders should have warning class
        assert "unresolved" in response.text or "Ej matchad" in response.text or "diabled" in response.text.lower()
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path
        cache_file.unlink(missing_ok=True)


def test_api_account_candidates_returns_matches(tmp_path: Path) -> None:
    """Test that /api/account-candidates returns matching candidates and best match."""
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    accounts: list[Account] = [
        {"id": 1, "name": "SEB Lönekonto", "type": "asset"},
        {"id": 2, "name": "SEB Sparkonto", "type": "asset"},
        {"id": 3, "name": "ICA Matkonto", "type": "asset"},
    ]

    import firefly_bank_importer.import_firefly as imf

    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        cache_file = _write_test_account_cache(accounts)
        imf.ACCOUNT_CACHE_FILE = cache_file

        app = create_app(import_folder)
        client = TestClient(app)

        response = client.get("/api/account-candidates?folder=kontoutdrag_SEB_Lonekonto")
        assert response.status_code == 200
        data = response.json()

        assert data["folder"] == "kontoutdrag_SEB_Lonekonto"
        assert data["best_match"] == 1  # SEB Lönekonto should be best match
        assert len(data["candidates"]) >= 1
        assert any(c["name"] == "SEB Lönekonto" for c in data["candidates"])
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path
        cache_file.unlink(missing_ok=True)


def test_api_account_candidates_returns_empty_when_no_cache(tmp_path: Path) -> None:
    """Test that /api/account-candidates returns error when no cache exists."""
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    import firefly_bank_importer.import_firefly as imf

    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        # Point to non-existent cache file
        imf.ACCOUNT_CACHE_FILE = tmp_path / "nonexistent_accounts_cache.json"

        app = create_app(import_folder)
        client = TestClient(app)

        response = client.get("/api/account-candidates?folder=some_folder")
        assert response.status_code == 200
        data = response.json()

        assert data["candidates"] == []
        assert "error" in data or data["best_match"] is None
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path


def test_selection_page_shows_error_without_cache(tmp_path: Path) -> None:
    """Test that /selection shows error when no account cache."""
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    test_folder = import_folder / "SEB_Test"
    test_folder.mkdir()
    csv_file = test_folder / "2025-01.csv"
    csv_file.write_text("Bokföringsdata;Transaktionsdata;Belopp;Saldo\n2025-01-01;2025-01-01;100;1000\n")

    import firefly_bank_importer.import_firefly as imf

    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        # Point to non-existent cache
        imf.ACCOUNT_CACHE_FILE = tmp_path / "nonexistent.json"

        app = create_app(import_folder)
        client = TestClient(app)

        response = client.get("/selection?folder=SEB_Test")
        assert response.status_code == 200
        assert "Fel" in response.text or "Kontocache" in response.text
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path


def test_index_page_renders_with_accounts(tmp_path: Path) -> None:
    """Test that / page renders folder selection UI."""
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    test_folder = import_folder / "Test_Folder"
    test_folder.mkdir()
    csv_file = test_folder / "2025-01.csv"
    csv_file.write_text("Bokföringsdata;Transaktionsdata;Belopp;Saldo\n2025-01-01;2025-01-01;100;1000\n")

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Välj importmappar" in response.text
    assert "Test_Folder" in response.text
