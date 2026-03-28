from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any, TypedDict

import requests
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.config import CONFIG_FILE, SECRETS_FILE, TOKEN_FILE
from firefly_bank_importer.import_firefly import (
    find_account_id,
    get_latest_transaction_date,
    load_account_cache,
    sanitize_folder_name,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_IMPORT_BASE = _PROJECT_ROOT / "bankImports"


class AccountCandidate(TypedDict):
    id: int
    name: str


class FolderDryRunSummary(TypedDict):
    folder: str
    account_id: int | None
    account_name: str | None
    file_count: int
    candidate_transactions: int
    duplicate_skips: int
    date_from: str | None
    date_to: str | None
    warnings: list[str]
    errors: list[str]


class DryRunSummary(TypedDict):
    folders: list[FolderDryRunSummary]
    totals: dict[str, int]
    can_continue: bool


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


def _load_web_firefly_settings() -> tuple[str | None, str | None, list[str]]:
    warnings: list[str] = []
    firefly_url: str | None = None
    api_token: str | None = None

    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            raw_url = str(data.get("firefly_url", "")).strip()
            firefly_url = raw_url or None
        except json.JSONDecodeError:
            warnings.append("Kunde inte läsa config.json.")
    else:
        warnings.append("config.json saknas; latest-date-kontroll hoppas över.")

    if SECRETS_FILE.exists():
        try:
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
            raw_token = str(data.get("api_token", "")).strip()
            api_token = raw_token or None
        except json.JSONDecodeError:
            warnings.append("Kunde inte läsa secrets.json.")
    elif TOKEN_FILE.exists():
        raw_token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        api_token = raw_token or None
    else:
        warnings.append("Ingen API-token hittades; latest-date-kontroll hoppas över.")

    if firefly_url is None or api_token is None:
        warnings.append("Kunde inte läsa Firefly-inställningar; duplicate-skip uppskattas som 0.")

    return firefly_url, api_token, warnings


def _fetch_latest_dates(account_ids: set[int]) -> tuple[dict[int, date], list[str]]:
    if not account_ids:
        return {}, []

    firefly_url, api_token, warnings = _load_web_firefly_settings()
    if firefly_url is None or api_token is None:
        return {}, warnings

    latest_dates: dict[int, date] = {}
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_token}", "Accept": "application/json"})

    for account_id in account_ids:
        try:
            latest = get_latest_transaction_date(session, account_id, firefly_url)
            if latest is not None:
                latest_dates[account_id] = latest
        except (requests.RequestException, ValueError):
            warnings.append(f"Kunde inte hämta senaste transaktionsdatum för konto {account_id}.")

    return latest_dates, warnings


def _build_dry_run_summary(selected_folders: list[str], import_base: Path) -> DryRunSummary:
    accounts = load_account_cache()
    account_map = {a["name"]: a["id"] for a in accounts} if accounts else {}
    account_names_by_id = {a["id"]: a["name"] for a in accounts} if accounts else {}

    previews: list[FolderDryRunSummary] = []
    account_ids_to_lookup: set[int] = set()

    for folder_name in selected_folders:
        folder_errors: list[str] = []
        folder_warnings: list[str] = []
        folder_path = import_base / folder_name

        account_id = find_account_id(folder_name, account_map) if account_map else None
        if account_id is not None:
            account_ids_to_lookup.add(account_id)
        else:
            folder_errors.append("Ingen kontomatchning hittades för mappen.")

        if not folder_path.exists() or not folder_path.is_dir():
            folder_errors.append("Mappen finns inte.")
            previews.append(
                {
                    "folder": folder_name,
                    "account_id": account_id,
                    "account_name": account_names_by_id.get(account_id) if account_id is not None else None,
                    "file_count": 0,
                    "candidate_transactions": 0,
                    "duplicate_skips": 0,
                    "date_from": None,
                    "date_to": None,
                    "warnings": folder_warnings,
                    "errors": folder_errors,
                }
            )
            continue

        previews.append(
            {
                "folder": folder_name,
                "account_id": account_id,
                "account_name": account_names_by_id.get(account_id) if account_id is not None else None,
                "file_count": len(list(folder_path.glob("*.csv"))),
                "candidate_transactions": 0,
                "duplicate_skips": 0,
                "date_from": None,
                "date_to": None,
                "warnings": folder_warnings,
                "errors": folder_errors,
            }
        )

    latest_dates, global_warnings = _fetch_latest_dates(account_ids_to_lookup)

    for preview in previews:
        folder_path = import_base / preview["folder"]
        if not folder_path.exists() or not folder_path.is_dir():
            continue

        min_date: datetime | None = None
        max_date: datetime | None = None

        for csv_path in sorted(folder_path.glob("*.csv")):
            with csv_path.open(encoding="utf-8-sig") as handle:
                reader = csv.reader(handle, delimiter=";")
                headers = next(reader, None)
                if headers is None:
                    preview["warnings"].append(f"{csv_path.name}: filen är tom.")
                    continue

                bank_format = resolve_bank_format(headers)
                if bank_format is None:
                    preview["errors"].append(f"{csv_path.name}: okänt CSV-format.")
                    continue

                mapping = bank_format.build_column_mapping(headers)
                latest_for_account = (
                    latest_dates.get(preview["account_id"]) if preview["account_id"] is not None else None
                )

                for row in reader:
                    if mapping.date_idx >= len(row):
                        preview["warnings"].append(f"{csv_path.name}: rad saknar datumkolumn.")
                        continue

                    try:
                        row_dt = datetime.strptime(row[mapping.date_idx], "%Y-%m-%d")
                    except ValueError:
                        preview["warnings"].append(f"{csv_path.name}: ogiltigt datum '{row[mapping.date_idx]}'.")
                        continue

                    if latest_for_account is not None and row_dt.date() <= latest_for_account:
                        preview["duplicate_skips"] += 1
                        continue

                    preview["candidate_transactions"] += 1
                    if min_date is None or row_dt < min_date:
                        min_date = row_dt
                    if max_date is None or row_dt > max_date:
                        max_date = row_dt

        preview["date_from"] = min_date.strftime("%Y-%m-%d") if min_date is not None else None
        preview["date_to"] = max_date.strftime("%Y-%m-%d") if max_date is not None else None

        if global_warnings:
            preview["warnings"].extend(global_warnings)

    totals = {
        "candidate_transactions": sum(item["candidate_transactions"] for item in previews),
        "duplicate_skips": sum(item["duplicate_skips"] for item in previews),
        "warnings": sum(len(item["warnings"]) for item in previews),
        "errors": sum(len(item["errors"]) for item in previews),
    }

    can_continue = totals["errors"] == 0
    return {
        "folders": previews,
        "totals": totals,
        "can_continue": can_continue,
    }


def _render_dry_run_preview(summary: DryRunSummary) -> str:
    rows: list[str] = []
    for folder in summary["folders"]:
        warnings_html = "<br>".join(escape(w) for w in folder["warnings"]) or "-"
        errors_html = "<br>".join(escape(e) for e in folder["errors"]) or "-"
        rows.append(
            "".join(
                [
                    "<tr>",
                    f"<td>{escape(folder['folder'])}</td>",
                    f"<td>{escape(folder['account_name'] or '-')}</td>",
                    f"<td>{folder['candidate_transactions']}</td>",
                    f"<td>{folder['duplicate_skips']}</td>",
                    f"<td>{escape(folder['date_from'] or '-')}</td>",
                    f"<td>{escape(folder['date_to'] or '-')}</td>",
                    f"<td>{warnings_html}</td>",
                    f"<td>{errors_html}</td>",
                    "</tr>",
                ]
            )
        )

    guard_text = (
        "<p style='color:green;'>Dry-run klar: inga blockerande fel upptäcktes.</p>"
        if summary["can_continue"]
        else "<p style='color:red;'>Live import blockerad: åtgärda fel innan du fortsätter.</p>"
    )

    return (
        "<h1>Dry-run preview</h1>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th>Mapp</th><th>Konto</th><th>Kandidater</th><th>Duplicate-skips</th>"
        "<th>Datum från</th><th>Datum till</th><th>Varningar</th><th>Fel</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
        f"<p>Totalt kandidater: {summary['totals']['candidate_transactions']}</p>"
        f"<p>Totalt duplicate-skips: {summary['totals']['duplicate_skips']}</p>"
        f"<p>Totalt varningar: {summary['totals']['warnings']}</p>"
        f"<p>Totalt fel: {summary['totals']['errors']}</p>"
        f"{guard_text}"
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

    @app.get("/api/dry-run-preview")
    def api_dry_run_preview(request: Request) -> dict[str, Any]:
        folders = request.query_params.getlist("folder")
        summary = _build_dry_run_summary(folders, import_base)
        return {
            "folders": summary["folders"],
            "totals": summary["totals"],
            "can_continue": summary["can_continue"],
        }

    @app.get("/preview", response_class=HTMLResponse)
    def preview_page(request: Request) -> str:
        folders = request.query_params.getlist("folder")
        summary = _build_dry_run_summary(folders, import_base)
        return (
            "<html><head><meta charset='utf-8'><title>Dry-run preview</title></head><body>"
            f"{_render_dry_run_preview(summary)}"
            "<p><a href='/'>Tillbaka</a></p>"
            "</body></html>"
        )

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("firefly_bank_importer.web_ui:app", host="127.0.0.1", port=8000, reload=False)
