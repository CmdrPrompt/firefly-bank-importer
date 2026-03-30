"""Tests for web UI dry-run preview (TASK-018)."""

from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import firefly_bank_importer.web_ui as web_ui
from firefly_bank_importer.web_ui import create_app


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    lines = [";".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_api_dry_run_preview_returns_counts_dates_and_duplicates(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    folder = import_folder / "kontoutdrag_SEB_Lonekonto"
    folder.mkdir()
    _write_csv(
        folder / "2026-01.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-01-01", "Hyra", "Kort", "-1000,00"],
            ["2026-01-10", "Lön", "Insättning", "20000,00"],
        ],
    )

    monkeypatch.setattr(
        web_ui,
        "load_account_cache",
        lambda: [{"id": 42, "name": "SEB Lonekonto", "type": "asset"}],
    )
    monkeypatch.setattr(web_ui, "_fetch_latest_dates", lambda _ids: ({42: date(2026, 1, 5)}, []))

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.get("/api/dry-run-preview", params=[("folder", "kontoutdrag_SEB_Lonekonto")])
    assert response.status_code == 200

    data = response.json()
    assert data["can_continue"] is True
    assert data["totals"]["candidate_transactions"] == 1
    assert data["totals"]["duplicate_skips"] == 1

    folder_summary = data["folders"][0]
    assert folder_summary["folder"] == "kontoutdrag_SEB_Lonekonto"
    assert folder_summary["account_id"] == 42
    assert folder_summary["candidate_transactions"] == 1
    assert folder_summary["duplicate_skips"] == 1
    assert folder_summary["date_from"] == "2026-01-10"
    assert folder_summary["date_to"] == "2026-01-10"


def test_api_dry_run_preview_reports_errors_and_blocks_continue(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    folder = import_folder / "kontoutdrag_Unknown"
    folder.mkdir()
    _write_csv(
        folder / "2026-01.csv",
        [
            ["Unknown", "Header"],
            ["a", "b"],
        ],
    )

    monkeypatch.setattr(web_ui, "load_account_cache", lambda: [])
    monkeypatch.setattr(web_ui, "_fetch_latest_dates", lambda _ids: ({}, []))

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.get("/api/dry-run-preview", params=[("folder", "kontoutdrag_Unknown")])
    assert response.status_code == 200

    data = response.json()
    assert data["can_continue"] is False
    assert data["totals"]["errors"] >= 1


def test_preview_page_shows_summary_content(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    folder = import_folder / "kontoutdrag_SEB_Sparkonto"
    folder.mkdir()
    _write_csv(
        folder / "2026-02.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-02-05", "Butik", "Kort", "-50,00"],
        ],
    )

    monkeypatch.setattr(
        web_ui,
        "load_account_cache",
        lambda: [{"id": 7, "name": "SEB Sparkonto", "type": "asset"}],
    )
    monkeypatch.setattr(web_ui, "_fetch_latest_dates", lambda _ids: ({}, []))

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.get("/preview", params=[("folder", "kontoutdrag_SEB_Sparkonto")])
    assert response.status_code == 200
    assert "Dry-run preview" in response.text
    assert "Totalt kandidater" in response.text
    assert "Duplicate-skips" in response.text
