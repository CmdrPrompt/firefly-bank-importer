import json
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import firefly_bank_importer.import_firefly as imf
from firefly_bank_importer.import_firefly import Account
from firefly_bank_importer.web_ui import create_app, list_import_folders


def _write_csv(path: Path, rows: list[list[str]]) -> None:
    lines = [";".join(row) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_list_import_folders_returns_counts_and_ranges(tmp_path: Path) -> None:
    folder = tmp_path / "kontoutdrag_Testkonto"
    folder.mkdir()

    _write_csv(
        folder / "2026-01.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-01-03", "Mat", "Kort", "-120,50"],
            ["2026-01-07", "Lön", "Insättning", "12000,00"],
        ],
    )

    previews = list_import_folders(tmp_path)

    assert len(previews) == 1
    assert previews[0].name == "kontoutdrag_Testkonto"
    assert previews[0].file_count == 1
    assert previews[0].row_count == 2
    assert previews[0].date_from == "2026-01-03"
    assert previews[0].date_to == "2026-01-07"
    assert previews[0].files[0].csv_format == "ica"


def _write_account_cache(accounts: list[Account]) -> Path:
    cache_file = Path(tempfile.gettempdir()) / "accounts_cache.json"
    cache_file.write_text(
        json.dumps({"fetched_at": "2026-01-01T00:00:00", "accounts": accounts}, ensure_ascii=False),
        encoding="utf-8",
    )
    return cache_file


def test_index_renders_folder_table_and_selection_works(tmp_path: Path) -> None:
    folder = tmp_path / "kontoutdrag_A"
    folder.mkdir()

    _write_csv(
        folder / "2026-02.csv",
        [
            ["Bokforingsdatum", "Text", "Belopp"],
            ["2026-02-01", "Hyra", "-9000,00"],
        ],
    )

    accounts: list[Account] = [{"id": 1, "name": "kontoutdrag A", "type": "asset"}]
    orig_cache_path = imf.ACCOUNT_CACHE_FILE
    try:
        cache_file = _write_account_cache(accounts)
        imf.ACCOUNT_CACHE_FILE = cache_file

        app = create_app(tmp_path)
        client = TestClient(app)

        index_response = client.get("/")
        assert index_response.status_code == 200
        assert "Välj importmappar" in index_response.text
        assert "kontoutdrag_A" in index_response.text

        selection_response = client.get("/selection", params=[("folder", "kontoutdrag_A")])
        assert selection_response.status_code == 200
        assert "Kontomappning" in selection_response.text
        assert "kontoutdrag_A" in selection_response.text
    finally:
        imf.ACCOUNT_CACHE_FILE = orig_cache_path
        cache_file.unlink(missing_ok=True)


def test_api_folders_returns_folder_metadata(tmp_path: Path) -> None:
    folder = tmp_path / "kontoutdrag_B"
    folder.mkdir()

    _write_csv(
        folder / "2026-03.csv",
        [
            ["Datum", "Text", "Typ", "Belopp"],
            ["2026-03-05", "Butik", "Kort", "-10,00"],
        ],
    )

    app = create_app(tmp_path)
    client = TestClient(app)

    response = client.get("/api/folders")
    assert response.status_code == 200

    data = response.json()
    assert data["base_folder"] == str(tmp_path)
    assert len(data["folders"]) == 1
    assert data["folders"][0]["name"] == "kontoutdrag_B"
    assert data["folders"][0]["file_count"] == 1
    assert data["folders"][0]["row_count"] == 1
