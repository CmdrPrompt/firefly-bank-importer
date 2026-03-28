"""Tests for web UI live import progress (TASK-019)."""

import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import firefly_bank_importer.web_ui as web_ui
from firefly_bank_importer.web_ui import create_app


class _DummyResponse:
    def __init__(self, status_code: int, text: str = "ok") -> None:
        self.status_code = status_code
        self.text = text


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    lines = [";".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_live_import_start_and_status_completion(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    folder = import_folder / "kontoutdrag_SEB_Lonekonto"
    folder.mkdir()
    _write_csv(
        folder / "2026-04.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-04-01", "Gammal", "Kort", "-100,00"],
            ["2026-04-12", "Ny", "Kort", "-50,00"],
        ],
    )

    monkeypatch.setattr(web_ui, "_load_web_firefly_settings", lambda: ("http://firefly", "token", []))
    monkeypatch.setattr(
        web_ui,
        "load_account_cache",
        lambda: [{"id": 9, "name": "SEB Lonekonto", "type": "asset"}],
    )
    monkeypatch.setattr(web_ui, "get_latest_transaction_date", lambda *_args, **_kwargs: date(2026, 4, 5))

    def _fake_create_transaction(*_args: object, **_kwargs: object) -> tuple[_DummyResponse, str, float]:
        return _DummyResponse(201), "withdrawal", 50.0

    monkeypatch.setattr(web_ui, "create_transaction", _fake_create_transaction)

    app = create_app(import_folder)
    client = TestClient(app)

    start_response = client.post(
        "/api/live-import/start",
        json={"folders": ["kontoutdrag_SEB_Lonekonto"]},
    )
    assert start_response.status_code == 200
    start_data = start_response.json()
    assert start_data["state"] == "queued"
    job_id = start_data["job_id"]

    status_data = {}
    for _ in range(40):
        status_response = client.get("/api/live-import/status", params={"job_id": job_id})
        assert status_response.status_code == 200
        status_data = status_response.json()
        if status_data["state"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert status_data["state"] == "completed"
    assert status_data["summary"]["imported"] == 1
    assert status_data["summary"]["skipped"] == 1
    assert status_data["summary"]["failed"] == 0


def test_live_import_status_unknown_job_returns_error(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    response = client.get("/api/live-import/status", params={"job_id": "does-not-exist"})
    assert response.status_code == 200
    assert "error" in response.json()


def test_live_import_page_contains_realtime_polling(tmp_path: Path) -> None:
    app = create_app(tmp_path)
    client = TestClient(app)

    response = client.get("/live-import", params=[("folder", "kontoutdrag_A")])
    assert response.status_code == 200
    assert "Live import progress" in response.text
    assert "setTimeout(refreshStatus" in response.text
    assert "/api/live-import/start" in response.text


def test_live_import_fails_when_firefly_settings_are_missing(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    monkeypatch.setattr(web_ui, "_load_web_firefly_settings", lambda: (None, None, []))

    app = create_app(import_folder)
    client = TestClient(app)

    start_response = client.post("/api/live-import/start", json={"folders": ["kontoutdrag_Test"]})
    job_id = start_response.json()["job_id"]

    status_data = {}
    for _ in range(40):
        status_response = client.get("/api/live-import/status", params={"job_id": job_id})
        status_data = status_response.json()
        if status_data["state"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert status_data["state"] == "failed"
    assert status_data["error"] == "Firefly-inställningar saknas."


def test_live_import_fails_when_account_cache_is_missing(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    monkeypatch.setattr(web_ui, "_load_web_firefly_settings", lambda: ("http://firefly", "token", []))
    monkeypatch.setattr(web_ui, "load_account_cache", lambda: [])

    app = create_app(import_folder)
    client = TestClient(app)

    start_response = client.post("/api/live-import/start", json={"folders": ["kontoutdrag_Test"]})
    job_id = start_response.json()["job_id"]

    status_data = {}
    for _ in range(40):
        status_response = client.get("/api/live-import/status", params={"job_id": job_id})
        status_data = status_response.json()
        if status_data["state"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert status_data["state"] == "failed"
    assert status_data["error"] == "Kontocache saknas."


def test_live_import_collects_multiple_row_level_failures(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    folder = import_folder / "kontoutdrag_SEB_Lonekonto"
    folder.mkdir()
    _write_csv(
        folder / "2026-05.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-05-01", "TooShort"],
            ["not-a-date", "BadDate", "Kort", "-10,00"],
            ["2026-05-02", "Raise", "Kort", "-10,00"],
            ["2026-05-03", "NoneResult", "Kort", "-10,00"],
            ["2026-05-04", "ApiFail", "Kort", "-10,00"],
            ["2026-05-05", "Success", "Kort", "-10,00"],
        ],
    )

    monkeypatch.setattr(web_ui, "_load_web_firefly_settings", lambda: ("http://firefly", "token", []))
    monkeypatch.setattr(
        web_ui,
        "load_account_cache",
        lambda: [{"id": 9, "name": "SEB Lonekonto", "type": "asset"}],
    )
    monkeypatch.setattr(web_ui, "get_latest_transaction_date", lambda *_args, **_kwargs: None)

    def _fake_create_transaction(
        _session: object,
        _date_value: str,
        description: str,
        _amount: str,
        _account_id: int,
        _firefly_url: str,
        **_kwargs: object,
    ) -> tuple[_DummyResponse, str, float] | None:
        if description == "Raise [Kort]":
            raise ValueError("boom")
        if description == "NoneResult [Kort]":
            return None
        if description == "ApiFail [Kort]":
            return _DummyResponse(500, "api fail"), "withdrawal", 10.0
        return _DummyResponse(201), "withdrawal", 10.0

    monkeypatch.setattr(web_ui, "create_transaction", _fake_create_transaction)

    app = create_app(import_folder)
    client = TestClient(app)

    start_response = client.post("/api/live-import/start", json={"folders": ["kontoutdrag_SEB_Lonekonto"]})
    job_id = start_response.json()["job_id"]

    status_data = {}
    for _ in range(60):
        status_response = client.get("/api/live-import/status", params={"job_id": job_id})
        status_data = status_response.json()
        if status_data["state"] in {"completed", "failed"}:
            break
        time.sleep(0.05)

    assert status_data["state"] == "completed"
    assert status_data["summary"]["imported"] == 1
    assert status_data["summary"]["failed"] == 5
    joined_events = "\n".join(event["message"] for event in status_data["events"])
    assert "rad saknar obligatoriska kolumner" in joined_events
    assert "ogiltigt datum" in joined_events
    assert "Transaktionsfel: boom" in joined_events
    assert "API-fel: 500 api fail" in joined_events
