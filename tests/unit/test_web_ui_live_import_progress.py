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
