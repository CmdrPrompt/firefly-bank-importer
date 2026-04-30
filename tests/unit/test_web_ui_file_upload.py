"""Tests for web UI CSV upload (TASK-020)."""

import io
from datetime import date
from pathlib import Path

from fastapi import UploadFile
from fastapi.testclient import TestClient
from firefly_python_api import FireflyConnectionError
from pytest import MonkeyPatch

import firefly_bank_importer.web_ui as web_ui
from firefly_bank_importer.web_ui import create_app


def test_upload_page_renders_form(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    (import_folder / "kontoutdrag_Test").mkdir()

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.get("/upload")
    assert response.status_code == 200
    assert "Ladda upp CSV-filer" in response.text
    assert "kontoutdrag_Test" in response.text


def test_api_upload_csv_saves_supported_file(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    target_folder = import_folder / "kontoutdrag_Test"
    target_folder.mkdir()

    app = create_app(import_folder)
    client = TestClient(app)

    csv_content = b"Datum;Text;Typ;Belopp\n2026-03-01;Mat;Kort;-50,00\n"

    response = client.post(
        "/api/upload-csv",
        data={"folder": "kontoutdrag_Test"},
        files=[("files", ("2026-03.csv", csv_content, "text/csv"))],
    )
    assert response.status_code == 200

    data = response.json()
    assert data["saved_count"] == 1
    assert data["rejected_count"] == 0
    assert data["results"][0]["status"] == "saved"
    assert data["results"][0]["detected_format"] == "ica"
    assert (target_folder / "2026-03.csv").exists()


def test_api_upload_csv_rejects_unsupported_format(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    (import_folder / "kontoutdrag_Test").mkdir()

    app = create_app(import_folder)
    client = TestClient(app)

    csv_content = b"A;B;C\n1;2;3\n"

    response = client.post(
        "/api/upload-csv",
        data={"folder": "kontoutdrag_Test"},
        files=[("files", ("bad.csv", csv_content, "text/csv"))],
    )
    assert response.status_code == 200

    data = response.json()
    assert data["saved_count"] == 0
    assert data["rejected_count"] == 1
    assert data["results"][0]["status"] == "rejected"
    assert "stött format" in data["results"][0]["reason"]


def test_upload_post_returns_feedback_html(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    (import_folder / "kontoutdrag_Test").mkdir()

    app = create_app(import_folder)
    client = TestClient(app)

    csv_content = b"Datum;Text;Typ;Belopp\n2026-04-01;Hyra;Kort;-9000,00\n"

    response = client.post(
        "/upload",
        data={"folder": "kontoutdrag_Test"},
        files=[("files", ("2026-04.csv", csv_content, "text/csv"))],
    )
    assert response.status_code == 200
    assert "Upload-resultat" in response.text
    assert "Sparade filer: 1" in response.text
    assert "2026-04.csv" in response.text


def test_load_web_firefly_settings_uses_token_fallback_on_invalid_config(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    config_file = tmp_path / "config.json"
    token_file = tmp_path / "token"
    secrets_file = tmp_path / "secrets.json"

    config_file.write_text("{invalid json", encoding="utf-8")
    token_file.write_text("fallback-token\n", encoding="utf-8")

    monkeypatch.setattr(web_ui, "CONFIG_FILE", config_file)
    monkeypatch.setattr(web_ui, "SECRETS_FILE", secrets_file)
    monkeypatch.setattr(web_ui, "TOKEN_FILE", token_file)

    firefly_url, api_token, warnings = web_ui._load_web_firefly_settings()

    assert firefly_url is None
    assert api_token == "fallback-token"
    assert "Kunde inte läsa config.json." in warnings
    assert "Firefly-URL saknas eller är tom; duplicate-skip hoppas över." in warnings


def test_load_web_firefly_settings_reads_valid_config_and_secrets(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    config_file = tmp_path / "config.json"
    token_file = tmp_path / "token"
    secrets_file = tmp_path / "secrets.json"

    config_file.write_text('{"firefly_url": "http://firefly.local"}', encoding="utf-8")
    secrets_file.write_text('{"api_token": "abc123"}', encoding="utf-8")

    monkeypatch.setattr(web_ui, "CONFIG_FILE", config_file)
    monkeypatch.setattr(web_ui, "SECRETS_FILE", secrets_file)
    monkeypatch.setattr(web_ui, "TOKEN_FILE", token_file)

    firefly_url, api_token, warnings = web_ui._load_web_firefly_settings()

    assert firefly_url == "http://firefly.local"
    assert api_token == "abc123"
    assert warnings == []


def test_fetch_latest_dates_returns_partial_results_and_warning(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(web_ui, "_load_web_firefly_settings", lambda: ("http://firefly", "token", []))

    def _fake_get_latest_transaction_date(_client: object, account_id: int) -> object:
        if account_id == 1:
            return date(2026, 3, 10)
        raise FireflyConnectionError("network")

    monkeypatch.setattr(web_ui, "get_latest_transaction_date", _fake_get_latest_transaction_date)

    latest_dates, warnings = web_ui._fetch_latest_dates({1, 2})

    assert latest_dates == {1: date(2026, 3, 10)}
    assert warnings == ["Kunde inte hämta senaste transaktionsdatum för konto 2."]


def test_api_upload_csv_rejects_missing_target_folder(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.post(
        "/api/upload-csv",
        data={"folder": "kontoutdrag_Saknas"},
        files=[("files", ("2026-03.csv", b"Datum;Text;Typ;Belopp\n", "text/csv"))],
    )
    assert response.status_code == 200

    data = response.json()
    assert data["saved_count"] == 0
    assert data["rejected_count"] == 1
    assert data["error"] == "Vald importmapp finns inte."


def test_api_upload_csv_rejects_multiple_invalid_inputs(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    target_folder = import_folder / "kontoutdrag_Test"
    target_folder.mkdir()
    (target_folder / "duplicate.csv").write_text("existing", encoding="utf-8")

    app = create_app(import_folder)
    client = TestClient(app)

    response = client.post(
        "/api/upload-csv",
        data={"folder": "kontoutdrag_Test"},
        files=[
            ("files", ("notes.txt", b"not csv", "text/plain")),
            ("files", ("bad-utf8.csv", b"\xff\xfe\x00", "text/csv")),
            ("files", ("empty.csv", b"", "text/csv")),
            (
                "files",
                (
                    "duplicate.csv",
                    b"Datum;Text;Typ;Belopp\n2026-03-01;Mat;Kort;-50,00\n",
                    "text/csv",
                ),
            ),
        ],
    )
    assert response.status_code == 200

    data = response.json()
    assert data["saved_count"] == 0
    assert data["rejected_count"] == 4
    reasons = {item["filename"]: item["reason"] for item in data["results"]}
    assert reasons["notes.txt"] == "Endast .csv-filer stöds."
    assert reasons["bad-utf8.csv"] == "Filen kunde inte avkodas som UTF-8."
    assert reasons["empty.csv"] == "Filen är tom."
    assert reasons["duplicate.csv"] == "Fil med samma namn finns redan i målmappen."


def test_handle_csv_upload_rejects_missing_filename(tmp_path: Path) -> None:
    import_folder = tmp_path / "bankImports"
    import_folder.mkdir()
    (import_folder / "kontoutdrag_Test").mkdir()

    upload = UploadFile(filename="", file=io.BytesIO(b"Datum;Text;Typ;Belopp\n"))

    result = web_ui._handle_csv_upload(import_folder, "kontoutdrag_Test", [upload])

    assert result["saved_count"] == 0
    assert result["rejected_count"] == 1
    assert result["results"][0]["filename"] == "(saknar namn)"
    assert result["results"][0]["reason"] == "Filen saknar namn."
