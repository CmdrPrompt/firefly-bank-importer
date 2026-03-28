from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any, TypedDict

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.import_firefly import find_account_id, load_account_cache, sanitize_folder_name

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_IMPORT_BASE = _PROJECT_ROOT / "bankImports"


class AccountCandidate(TypedDict):
    id: int
    name: str


@dataclass
class FilePreview:
    name: str
    row_count: int
    csv_format: str
    date_from: str | None
    date_to: str | None


@dataclass
class FolderPreview:
    name: str
    file_count: int
    row_count: int
    date_from: str | None
    date_to: str | None
    files: list[FilePreview]


def _update_date_range(
    current_min: datetime | None, current_max: datetime | None, raw_date: str
) -> tuple[datetime | None, datetime | None]:
    try:
        parsed = datetime.strptime(raw_date[:10], "%Y-%m-%d")
    except ValueError:
        return current_min, current_max

    if current_min is None or parsed < current_min:
        current_min = parsed
    if current_max is None or parsed > current_max:
        current_max = parsed
    return current_min, current_max


def _read_file_preview(csv_path: Path) -> FilePreview:
    row_count = 0
    min_date: datetime | None = None
    max_date: datetime | None = None

    with csv_path.open(encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter=";")
        headers = next(reader, None)
        if headers is None:
            return FilePreview(
                name=csv_path.name,
                row_count=0,
                csv_format="unknown",
                date_from=None,
                date_to=None,
            )

        bank_format = resolve_bank_format(headers)
        mapping = bank_format.build_column_mapping(headers) if bank_format is not None else None

        for row in reader:
            row_count += 1
            if mapping is None or mapping.date_idx >= len(row):
                continue
            min_date, max_date = _update_date_range(min_date, max_date, row[mapping.date_idx])

    return FilePreview(
        name=csv_path.name,
        row_count=row_count,
        csv_format=bank_format.name if bank_format is not None else "unknown",
        date_from=min_date.strftime("%Y-%m-%d") if min_date is not None else None,
        date_to=max_date.strftime("%Y-%m-%d") if max_date is not None else None,
    )


def list_import_folders(base_folder: Path) -> list[FolderPreview]:
    folders = sorted([folder for folder in base_folder.iterdir() if folder.is_dir()])
    previews: list[FolderPreview] = []

    for folder in folders:
        files = sorted(folder.glob("*.csv"))
        file_previews = [_read_file_preview(csv_path) for csv_path in files]

        min_date = min((fp.date_from for fp in file_previews if fp.date_from is not None), default=None)
        max_date = max((fp.date_to for fp in file_previews if fp.date_to is not None), default=None)

        previews.append(
            FolderPreview(
                name=folder.name,
                file_count=len(file_previews),
                row_count=sum(fp.row_count for fp in file_previews),
                date_from=min_date,
                date_to=max_date,
                files=file_previews,
            )
        )

    return previews


def _render_folder_table(previews: list[FolderPreview]) -> str:
    rows = []
    for preview in previews:
        rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td><input type='checkbox' name='folder' value='{escape(preview.name)}'></td>",
                    f"<td>{escape(preview.name)}</td>",
                    f"<td>{preview.file_count}</td>",
                    f"<td>{preview.row_count}</td>",
                    f"<td>{escape(preview.date_from or '-')}</td>",
                    f"<td>{escape(preview.date_to or '-')}</td>",
                    "</tr>",
                ]
            )
        )

    if not rows:
        return "<p>Inga importmappar hittades.</p>"

    table = "".join(rows)
    return (
        "<form method='get' action='/selection'>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th>Val</th><th>Mapp</th><th>CSV-filer</th><th>Rader</th>"
        "<th>Datum från</th><th>Datum till</th></tr></thead>"
        f"<tbody>{table}</tbody>"
        "</table>"
        "<p><button type='submit'>Fortsätt med valda mappar</button></p>"
        "</form>"
    )


def create_app(base_folder: Path | None = None) -> FastAPI:
    app = FastAPI(title="Firefly Import Web UI", version="0.1.0")
    import_base = base_folder or _DEFAULT_IMPORT_BASE

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        previews = list_import_folders(import_base)
        return (
            "<html><head><meta charset='utf-8'><title>Firefly Import</title></head><body>"
            "<h1>Välj importmappar</h1>"
            f"<p>Basmapp: {escape(str(import_base))}</p>"
            f"{_render_folder_table(previews)}"
            "</body></html>"
        )

    @app.get("/selection", response_class=HTMLResponse)
    def selection(request: Request) -> str:
        selected = request.query_params.getlist("folder")

        accounts = load_account_cache()
        if not accounts:
            return (
                "<html><head><meta charset='utf-8'><title>Valda mappar</title></head><body>"
                "<h1>Fel</h1>"
                "<p>Kontocache hittades inte. Läs in eller uppdatera konton först.</p>"
                "<p><a href='/'>Tillbaka</a></p>"
                "</body></html>"
            )

        account_map = {a["name"]: a["id"] for a in accounts}

        # Build account candidates for each selected folder
        account_rows = []
        all_resolved = True
        for folder in selected:
            best_match_id = find_account_id(folder, account_map)
            candidates: list[AccountCandidate] = []

            # Get all possible candidates using same logic as find_account
            folder_key = folder
            if folder_key.startswith("kontoutdrag_"):
                folder_key = folder_key[len("kontoutdrag_") :]
            folder_lower = sanitize_folder_name(folder_key).lower()

            for account_name, account_id in account_map.items():
                account_lower = sanitize_folder_name(account_name).lower()
                if account_lower in folder_lower or folder_lower in account_lower:
                    candidates.append({"id": account_id, "name": account_name})

            if best_match_id is None:
                all_resolved = False

            selected_id = best_match_id or (candidates[0]["id"] if candidates else None)

            # Build dropdown options
            options = "".join(
                f'<option value="{c["id"]}" {"selected" if c["id"] == selected_id else ""}>{escape(c["name"])}</option>'
                for c in candidates
            )

            status_class = "resolved" if best_match_id is not None else "unresolved"
            status_text = "✓ Matchad" if best_match_id is not None else "⚠ Ej matchad"

            account_rows.append(
                f"<tr class='{status_class}'>"
                f"<td>{escape(folder)}</td>"
                f"<td>{status_text}</td>"
                f"<td><select name='{escape(folder)}'>{options}</select></td>"
                f"</tr>"
            )

        accounts_html = "".join(account_rows)
        disabled_msg = (
            "<p><button type='submit' name='action' value='select' disabled>"
            "Alla mappar måste mappas innan fortsättning</button></p>"
            "<p style='color:red;'>Obs: Alla mappar måste ha en vald "
            "Firefly-konto.<br/>"
        )
        button_html = (
            ("<p><button type='submit' name='action' value='select'>Fortsätt med denna mappning</button></p>")
            if all_resolved
            else (disabled_msg + "Se över automatisk matchning och gör handvalda" + " korrigeringar om behövligt.</p>")
        )

        return (
            "<html><head><meta charset='utf-8'><title>Kontomappning</title>"
            "<style>"
            "table { border-collapse: collapse; width: 100%; }"
            "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }"
            "th { background-color: #f0f0f0; }"
            ".resolved { background-color: #e8f5e9; }"
            ".unresolved { background-color: #ffebee; }"
            "</style>"
            "</head><body>"
            "<h1>Kontomappning</h1>"
            "<p>Välj Firefly-konto för varje importmapp:</p>"
            "<form method='post' action='/account-mapping'>"
            "<table><thead><tr><th>Mapp</th><th>Status</th><th>Firefly-konto</th></tr></thead>"
            f"<tbody>{accounts_html}</tbody>"
            "</table>"
            f"{button_html}"
            "<p><a href='/'>Tillbaka</a></p>"
            "</form>"
            "</body></html>"
        )

    @app.get("/api/folders")
    def api_folders() -> dict[str, Any]:
        previews = list_import_folders(import_base)
        return {
            "base_folder": str(import_base),
            "folders": [
                {
                    "name": preview.name,
                    "file_count": preview.file_count,
                    "row_count": preview.row_count,
                    "date_from": preview.date_from,
                    "date_to": preview.date_to,
                    "files": [
                        {
                            "name": file_preview.name,
                            "row_count": file_preview.row_count,
                            "format": file_preview.csv_format,
                            "date_from": file_preview.date_from,
                            "date_to": file_preview.date_to,
                        }
                        for file_preview in preview.files
                    ],
                }
                for preview in previews
            ],
        }

    @app.get("/api/account-candidates")
    def api_account_candidates(folder: str) -> dict[str, Any]:
        """Get account candidates for a given folder."""
        accounts = load_account_cache()
        if not accounts:
            return {"folder": folder, "candidates": [], "error": "Ingen kontocache tillgänglig"}

        account_map = {a["name"]: a["id"] for a in accounts}

        # Get best match
        best_match_id = find_account_id(folder, account_map)

        # Get all candidates using same logic as find_account_id
        candidates: list[AccountCandidate] = []
        folder_key = folder
        if folder_key.startswith("kontoutdrag_"):
            folder_key = folder_key[len("kontoutdrag_") :]
        folder_lower = sanitize_folder_name(folder_key).lower()

        for account_name, account_id in account_map.items():
            account_lower = sanitize_folder_name(account_name).lower()
            if account_lower in folder_lower or folder_lower in account_lower:
                candidates.append({"id": account_id, "name": account_name})

        return {
            "folder": folder,
            "best_match": best_match_id,
            "candidates": candidates,
        }

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("firefly_bank_importer.web_ui:app", host="127.0.0.1", port=8000, reload=False)
