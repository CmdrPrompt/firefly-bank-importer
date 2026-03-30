from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

import firefly_bank_importer.web_ui as web_ui
from firefly_bank_importer.web_ui import create_app


def _make_app(tmp_path: Path, monkeypatch: MonkeyPatch) -> TestClient:
    project_root = tmp_path / "project"
    project_root.mkdir()
    logs_dir = project_root / "logs"
    logs_dir.mkdir()
    import_base = project_root / "bankImports"
    import_base.mkdir()

    monkeypatch.setattr(web_ui, "_PROJECT_ROOT", project_root)
    app = create_app(import_base)
    return TestClient(app)


def test_api_import_history_lists_runs_with_status(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _make_app(tmp_path, monkeypatch)
    project_root = web_ui._PROJECT_ROOT

    (project_root / "logs" / "import_20260329_101010.log").write_text(
        "2026-03-29 INFO Start\n2026-03-29 INFO Klar!\n",
        encoding="utf-8",
    )
    (project_root / "logs" / "import_20260328_101010.log").write_text(
        "2026-03-28 ERROR Boom\n",
        encoding="utf-8",
    )

    response = client.get("/api/import-history")
    assert response.status_code == 200
    data = response.json()

    assert len(data["runs"]) == 2
    assert data["runs"][0]["run_id"] == "20260329_101010"
    assert data["runs"][0]["status"] == "completed"
    assert data["runs"][1]["status"] == "failed"


def test_api_import_history_details_returns_log_lines(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _make_app(tmp_path, monkeypatch)
    project_root = web_ui._PROJECT_ROOT

    (project_root / "logs" / "import_20260329_111111.log").write_text(
        "line1\nline2\n",
        encoding="utf-8",
    )

    response = client.get("/api/import-history/20260329_111111")
    assert response.status_code == 200
    data = response.json()

    assert data["run"]["run_id"] == "20260329_111111"
    assert data["run"]["line_count"] == 2
    assert data["lines"] == ["line1", "line2"]


def test_history_pages_render_list_and_details(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _make_app(tmp_path, monkeypatch)
    project_root = web_ui._PROJECT_ROOT

    (project_root / "logs" / "import_20260330_121212.log").write_text(
        "2026-03-30 INFO Klar!\n",
        encoding="utf-8",
    )

    history_response = client.get("/history")
    assert history_response.status_code == 200
    assert "Importhistorik" in history_response.text
    assert "20260330_121212" in history_response.text

    details_response = client.get("/history/20260330_121212")
    assert details_response.status_code == 200
    assert "Detaljerad logg" in details_response.text


def test_import_history_details_404_for_unknown_run(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    client = _make_app(tmp_path, monkeypatch)

    response = client.get("/api/import-history/unknown")
    assert response.status_code == 404
