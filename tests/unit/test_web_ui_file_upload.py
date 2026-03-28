"""Tests for web UI CSV upload (TASK-020)."""

from pathlib import Path

from fastapi.testclient import TestClient

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
