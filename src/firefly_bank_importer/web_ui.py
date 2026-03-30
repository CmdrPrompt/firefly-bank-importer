from __future__ import annotations

import contextlib
import csv
import io
import json
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any, TypedDict, cast
from uuid import uuid4

import requests
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.config import (
    CONFIG_FILE,
    SECRETS_FILE,
    TOKEN_FILE,
    validate_firefly_url,
)
from firefly_bank_importer.import_firefly import (
    create_transaction,
    fetch_accounts_from_firefly,
    find_account_id,
    get_latest_transaction_date,
    load_account_cache,
    sanitize_folder_name,
    save_account_cache,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_IMPORT_BASE = _PROJECT_ROOT / "bankImports"
_IMPORT_LOG_RE = re.compile(r"^import_(\d{8}_\d{6})\.log$")


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


class LiveImportSummary(TypedDict):
    imported: int
    skipped: int
    failed: int


class LiveImportEvent(TypedDict):
    timestamp: str
    level: str
    message: str


class LiveImportJob(TypedDict):
    job_id: str
    state: str
    current_folder: str | None
    current_file: str | None
    summary: LiveImportSummary
    events: list[LiveImportEvent]
    error: str | None


class UploadResult(TypedDict):
    filename: str
    status: str
    reason: str | None
    detected_format: str | None


class SettingsRead(TypedDict):
    firefly_url: str | None
    token_exists: bool


class SettingsSaveResult(TypedDict):
    success: bool
    error: str | None


class RefreshAccountsResult(TypedDict):
    total_accounts: int
    new_folders: int


class ImportHistoryRun(TypedDict):
    run_id: str
    filename: str
    timestamp: str
    status: str
    line_count: int


class ImportHistoryDetails(TypedDict):
    run: ImportHistoryRun
    lines: list[str]


UploadFolderForm = Annotated[str, Form(...)]
UploadFilesForm = Annotated[list[UploadFile], File(...)]


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


def _new_folder_summary(
    *,
    folder_name: str,
    account_id: int | None,
    account_names_by_id: dict[int, str],
    file_count: int,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> FolderDryRunSummary:
    return {
        "folder": folder_name,
        "account_id": account_id,
        "account_name": account_names_by_id.get(account_id) if account_id is not None else None,
        "file_count": file_count,
        "candidate_transactions": 0,
        "duplicate_skips": 0,
        "date_from": None,
        "date_to": None,
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _collect_initial_previews(
    selected_folders: list[str],
    import_base: Path,
    account_map: dict[str, int],
    account_names_by_id: dict[int, str],
) -> tuple[list[FolderDryRunSummary], set[int]]:
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
                _new_folder_summary(
                    folder_name=folder_name,
                    account_id=account_id,
                    account_names_by_id=account_names_by_id,
                    file_count=0,
                    warnings=folder_warnings,
                    errors=folder_errors,
                )
            )
            continue

        previews.append(
            _new_folder_summary(
                folder_name=folder_name,
                account_id=account_id,
                account_names_by_id=account_names_by_id,
                file_count=len(list(folder_path.glob("*.csv"))),
                warnings=folder_warnings,
                errors=folder_errors,
            )
        )

    return previews, account_ids_to_lookup


def _process_preview_row(
    *,
    row: list[str],
    mapping: Any,
    csv_name: str,
    preview: FolderDryRunSummary,
    latest_for_account: date | None,
    min_date: datetime | None,
    max_date: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    if mapping.date_idx >= len(row):
        preview["warnings"].append(f"{csv_name}: rad saknar datumkolumn.")
        return min_date, max_date

    raw_date = row[mapping.date_idx]
    try:
        row_dt = datetime.strptime(raw_date, "%Y-%m-%d")
    except ValueError:
        preview["warnings"].append(f"{csv_name}: ogiltigt datum '{raw_date}'.")
        return min_date, max_date

    if latest_for_account is not None and row_dt.date() <= latest_for_account:
        preview["duplicate_skips"] += 1
        return min_date, max_date

    preview["candidate_transactions"] += 1
    if min_date is None or row_dt < min_date:
        min_date = row_dt
    if max_date is None or row_dt > max_date:
        max_date = row_dt
    return min_date, max_date


def _process_preview_csv(
    *,
    csv_path: Path,
    preview: FolderDryRunSummary,
    latest_for_account: date | None,
    min_date: datetime | None,
    max_date: datetime | None,
) -> tuple[datetime | None, datetime | None]:
    with csv_path.open(encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter=";")
        headers = next(reader, None)
        if headers is None:
            preview["warnings"].append(f"{csv_path.name}: filen är tom.")
            return min_date, max_date

        bank_format = resolve_bank_format(headers)
        if bank_format is None:
            preview["errors"].append(f"{csv_path.name}: okänt CSV-format.")
            return min_date, max_date

        mapping = bank_format.build_column_mapping(headers)
        for row in reader:
            min_date, max_date = _process_preview_row(
                row=row,
                mapping=mapping,
                csv_name=csv_path.name,
                preview=preview,
                latest_for_account=latest_for_account,
                min_date=min_date,
                max_date=max_date,
            )

    return min_date, max_date


def _summarize_preview_folder(
    *,
    preview: FolderDryRunSummary,
    import_base: Path,
    latest_dates: dict[int, date],
    global_warnings: list[str],
) -> None:
    folder_path = import_base / preview["folder"]
    if not folder_path.exists() or not folder_path.is_dir():
        return

    min_date: datetime | None = None
    max_date: datetime | None = None
    latest_for_account = latest_dates.get(preview["account_id"]) if preview["account_id"] is not None else None

    for csv_path in sorted(folder_path.glob("*.csv")):
        min_date, max_date = _process_preview_csv(
            csv_path=csv_path,
            preview=preview,
            latest_for_account=latest_for_account,
            min_date=min_date,
            max_date=max_date,
        )

    preview["date_from"] = min_date.strftime("%Y-%m-%d") if min_date is not None else None
    preview["date_to"] = max_date.strftime("%Y-%m-%d") if max_date is not None else None

    if global_warnings:
        preview["warnings"].extend(global_warnings)


def _build_dry_run_summary(selected_folders: list[str], import_base: Path) -> DryRunSummary:
    accounts = load_account_cache()
    account_map = {a["name"]: a["id"] for a in accounts} if accounts else {}
    account_names_by_id = {a["id"]: a["name"] for a in accounts} if accounts else {}

    previews, account_ids_to_lookup = _collect_initial_previews(
        selected_folders,
        import_base,
        account_map,
        account_names_by_id,
    )

    latest_dates, global_warnings = _fetch_latest_dates(account_ids_to_lookup)

    for preview in previews:
        _summarize_preview_folder(
            preview=preview,
            import_base=import_base,
            latest_dates=latest_dates,
            global_warnings=global_warnings,
        )

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


def _render_live_import_page(folders: list[str]) -> str:
    folders_json = json.dumps(folders, ensure_ascii=False)
    return (
        "<html><head><meta charset='utf-8'><title>Live import progress</title></head><body>"
        "<h1>Live import progress</h1>"
        "<p>Startar importjobb och uppdaterar status automatiskt.</p>"
        "<p id='job-state'>Jobbstatus: väntar...</p>"
        "<p id='job-summary'>Importerade: 0 | Hoppade över: 0 | Fel: 0</p>"
        "<h2>Logg</h2>"
        "<div id='job-log' style='max-height:320px;overflow:auto;border:1px solid #ddd;padding:8px;'></div>"
        "<script>"
        f"const selectedFolders = {folders_json};"
        "let activeJobId = null;"
        "async function startJob() {"
        "  const res = await fetch('/api/live-import/start', {"
        "    method: 'POST',"
        "    headers: {'Content-Type': 'application/json'},"
        "    body: JSON.stringify({folders: selectedFolders})"
        "  });"
        "  const data = await res.json();"
        "  activeJobId = data.job_id;"
        "  if (!activeJobId) {"
        "    document.getElementById('job-state').textContent = 'Jobbstatus: kunde inte starta';"
        "    return;"
        "  }"
        "  setTimeout(refreshStatus, 200);"
        "}"
        "async function refreshStatus() {"
        "  if (!activeJobId) return;"
        "  const res = await fetch(`/api/live-import/status?job_id=${encodeURIComponent(activeJobId)}`);"
        "  const data = await res.json();"
        "  if (data.error) {"
        "    document.getElementById('job-state').textContent = `Jobbstatus: ${data.error}`;"
        "    return;"
        "  }"
        "  document.getElementById('job-state').textContent = `Jobbstatus: ${data.state}`;"
        "  document.getElementById('job-summary').textContent ="
        "    `Importerade: ${data.summary.imported} | "
        "Hoppade över: ${data.summary.skipped} | "
        "Fel: ${data.summary.failed}`;"
        "  const logHtml = data.events.map(e => `${e.timestamp} [${e.level}] ${e.message}`).join('<br>');"
        "  document.getElementById('job-log').innerHTML = logHtml || '-';"
        "  if (data.state === 'completed' || data.state === 'failed') return;"
        "  setTimeout(refreshStatus, 700);"
        "}"
        "startJob();"
        "</script>"
        "<p><a href='/'>Tillbaka</a></p>"
        "</body></html>"
    )


def _append_rejected_upload(
    results: list[UploadResult],
    *,
    filename: str,
    reason: str,
    detected_format: str | None = None,
) -> None:
    results.append(
        {
            "filename": filename,
            "status": "rejected",
            "reason": reason,
            "detected_format": detected_format,
        }
    )


def _validate_upload_file(
    upload: UploadFile,
    folder_path: Path,
    results: list[UploadResult],
) -> tuple[str, bytes, Any] | None:
    safe_name = Path(upload.filename or "").name
    if not safe_name:
        _append_rejected_upload(results, filename="(saknar namn)", reason="Filen saknar namn.")
        return None

    if not safe_name.lower().endswith(".csv"):
        _append_rejected_upload(results, filename=safe_name, reason="Endast .csv-filer stöds.")
        return None

    content = upload.file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        _append_rejected_upload(results, filename=safe_name, reason="Filen kunde inte avkodas som UTF-8.")
        return None

    reader = csv.reader(io.StringIO(decoded), delimiter=";")
    headers = next(reader, None)
    if headers is None:
        _append_rejected_upload(results, filename=safe_name, reason="Filen är tom.")
        return None

    bank_format = resolve_bank_format(headers)
    if bank_format is None:
        _append_rejected_upload(
            results,
            filename=safe_name,
            reason="CSV-header matchar inget stött format.",
        )
        return None

    if (folder_path / safe_name).exists():
        _append_rejected_upload(
            results,
            filename=safe_name,
            reason="Fil med samma namn finns redan i målmappen.",
            detected_format=bank_format.name,
        )
        return None

    return safe_name, content, bank_format


def _handle_csv_upload(import_base: Path, folder: str, files: list[UploadFile]) -> dict[str, Any]:
    folder_path = import_base / folder
    if not folder_path.exists() or not folder_path.is_dir():
        return {
            "folder": folder,
            "results": [],
            "saved_count": 0,
            "rejected_count": len(files),
            "error": "Vald importmapp finns inte.",
        }

    results: list[UploadResult] = []
    saved_count = 0
    rejected_count = 0

    for upload in files:
        validated = _validate_upload_file(upload, folder_path, results)
        if validated is None:
            rejected_count += 1
            continue

        safe_name, content, bank_format = validated
        target_path = folder_path / safe_name
        target_path.write_bytes(content)
        results.append(
            {
                "filename": safe_name,
                "status": "saved",
                "reason": None,
                "detected_format": bank_format.name,
            }
        )
        saved_count += 1

    return {
        "folder": folder,
        "results": results,
        "saved_count": saved_count,
        "rejected_count": rejected_count,
    }


def _render_upload_form(previews: list[FolderPreview], message: str | None = None) -> str:
    options = "".join(f"<option value='{escape(preview.name)}'>{escape(preview.name)}</option>" for preview in previews)
    return (
        "<h1>Ladda upp CSV-filer</h1>"
        + (f"<p>{escape(message)}</p>" if message else "")
        + "<form method='post' action='/upload' enctype='multipart/form-data'>"
        + "<p><label>Målmapp: <select name='folder'>"
        + options
        + "</select></label></p>"
        + "<p><input type='file' name='files' accept='.csv' multiple></p>"
        + "<p><button type='submit'>Ladda upp</button></p>"
        + "</form>"
    )


def _render_upload_results(result: dict[str, Any]) -> str:
    rows = "".join(
        "".join(
            [
                "<tr>",
                f"<td>{escape(str(item.get('filename', '-')))}</td>",
                f"<td>{escape(str(item.get('status', '-')))}</td>",
                f"<td>{escape(str(item.get('detected_format') or '-'))}</td>",
                f"<td>{escape(str(item.get('reason') or '-'))}</td>",
                "</tr>",
            ]
        )
        for item in result.get("results", [])
    )
    error_html = f"<p style='color:red;'>{escape(str(result['error']))}</p>" if "error" in result else ""
    return (
        "<h1>Upload-resultat</h1>"
        + error_html
        + f"<p>Sparade filer: {result.get('saved_count', 0)}</p>"
        + f"<p>Avvisade filer: {result.get('rejected_count', 0)}</p>"
        + "<table border='1' cellpadding='6' cellspacing='0'>"
        + "<thead><tr><th>Fil</th><th>Status</th><th>Format</th><th>Orsak</th></tr></thead>"
        + f"<tbody>{rows}</tbody>"
        + "</table>"
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


def _iter_import_log_paths() -> list[Path]:
    candidates: list[Path] = []
    for base in (_PROJECT_ROOT / "logs", _PROJECT_ROOT):
        if not base.exists() or not base.is_dir():
            continue
        candidates.extend(path for path in base.glob("import_*.log") if path.is_file())

    # Deduplicate by absolute path in case files appear in both scans.
    deduped = {path.resolve(): path for path in candidates}
    return list(deduped.values())


def _extract_run_id(path: Path) -> str:
    match = _IMPORT_LOG_RE.match(path.name)
    if match is None:
        return path.stem
    return match.group(1)


def _format_run_timestamp(path: Path) -> str:
    match = _IMPORT_LOG_RE.match(path.name)
    if match is None:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    parsed = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def _infer_run_status(lines: list[str]) -> str:
    joined = "\n".join(lines)
    if "Klar!" in joined:
        return "completed"
    if "ERROR" in joined or "[FEL]" in joined:
        return "failed"
    return "unknown"


def _read_import_history_run(path: Path) -> ImportHistoryRun:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "run_id": _extract_run_id(path),
        "filename": path.name,
        "timestamp": _format_run_timestamp(path),
        "status": _infer_run_status(lines),
        "line_count": len(lines),
    }


def _list_import_history_runs() -> list[ImportHistoryRun]:
    runs = [_read_import_history_run(path) for path in _iter_import_log_paths()]
    runs.sort(key=lambda run: run["timestamp"], reverse=True)
    return runs


def _get_import_history_details(run_id: str) -> ImportHistoryDetails | None:
    for path in _iter_import_log_paths():
        if _extract_run_id(path) != run_id:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        run: ImportHistoryRun = {
            "run_id": run_id,
            "filename": path.name,
            "timestamp": _format_run_timestamp(path),
            "status": _infer_run_status(lines),
            "line_count": len(lines),
        }
        return {"run": run, "lines": lines}
    return None


def _render_import_history_page(runs: list[ImportHistoryRun]) -> str:
    if not runs:
        return "<h1>Importhistorik</h1><p>Inga importloggar hittades ännu.</p><p><a href='/'>Tillbaka</a></p>"

    rows = "".join(
        "".join(
            [
                "<tr>",
                f"<td><a href='/history/{escape(run['run_id'])}'>{escape(run['run_id'])}</a></td>",
                f"<td>{escape(run['timestamp'])}</td>",
                f"<td>{escape(run['status'])}</td>",
                f"<td>{run['line_count']}</td>",
                f"<td>{escape(run['filename'])}</td>",
                "</tr>",
            ]
        )
        for run in runs
    )
    return (
        "<h1>Importhistorik</h1>"
        "<table border='1' cellpadding='6' cellspacing='0'>"
        "<thead><tr><th>Run ID</th><th>Tid</th><th>Status</th><th>Rader</th><th>Fil</th></tr></thead>"
        f"<tbody>{rows}</tbody>"
        "</table>"
        "<p><a href='/'>Tillbaka</a></p>"
    )


def _render_import_history_details_page(details: ImportHistoryDetails) -> str:
    run = details["run"]
    log_text = "\n".join(details["lines"])
    return (
        "<h1>Importlogg</h1>"
        f"<p><strong>Run ID:</strong> {escape(run['run_id'])}</p>"
        f"<p><strong>Tid:</strong> {escape(run['timestamp'])}</p>"
        f"<p><strong>Status:</strong> {escape(run['status'])}</p>"
        f"<p><strong>Fil:</strong> {escape(run['filename'])}</p>"
        "<h2>Detaljerad logg</h2>"
        "<pre style='white-space:pre-wrap;border:1px solid #ddd;padding:10px;background:#fafafa;'>"
        f"{escape(log_text)}"
        "</pre>"
        "<p><a href='/history'>Tillbaka till historik</a></p>"
    )


def _add_live_import_event(job: LiveImportJob, level: str, message: str) -> None:
    job["events"].append(
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
        }
    )


def _fail_live_import_job(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    *,
    error: str,
    event_message: str,
) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job["state"] = "failed"
        job["error"] = error
        _add_live_import_event(job, "error", event_message)


def _update_live_import_folder_context(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    folder_name: str,
) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job["current_folder"] = folder_name
        _add_live_import_event(job, "info", f"Bearbetar mapp: {folder_name}")


def _update_live_import_file_context(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    file_name: str,
) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job["current_file"] = file_name
        _add_live_import_event(job, "info", f"Bearbetar fil: {file_name}")


def _record_live_import_error(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    message: str,
) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job["summary"]["failed"] += 1
        _add_live_import_event(job, "error", message)


def _record_live_import_warning(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    message: str,
) -> None:
    with jobs_lock:
        _add_live_import_event(jobs[job_id], "warning", message)


def _record_live_import_skip(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
) -> None:
    with jobs_lock:
        jobs[job_id]["summary"]["skipped"] += 1


def _record_live_import_result(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
    response: requests.Response,
) -> None:
    with jobs_lock:
        job = jobs[job_id]
        if response.status_code in (200, 201):
            job["summary"]["imported"] += 1
            return

        job["summary"]["failed"] += 1
        _add_live_import_event(job, "error", f"API-fel: {response.status_code} {response.text[:80]}")


def _build_live_import_description(row: list[str], mapping: Any) -> str:
    description_idx = cast(int, mapping.description_idx)
    transaction_type_idx = cast(int | None, mapping.transaction_type_idx)
    description = row[description_idx].strip()
    if transaction_type_idx is None or transaction_type_idx >= len(row):
        return description
    return f"{description} [{row[transaction_type_idx].strip()}]"


def _handle_live_import_row(
    *,
    row: list[str],
    mapping: Any,
    latest_date: date | None,
    csv_name: str,
    session: requests.Session,
    firefly_url: str,
    account_id: int,
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
) -> None:
    if mapping.date_idx >= len(row) or mapping.description_idx >= len(row) or mapping.amount_idx >= len(row):
        _record_live_import_error(jobs, jobs_lock, job_id, f"{csv_name}: rad saknar obligatoriska kolumner.")
        return

    row_raw_date = row[mapping.date_idx]
    try:
        row_date = datetime.strptime(row_raw_date, "%Y-%m-%d").date()
    except ValueError:
        _record_live_import_error(jobs, jobs_lock, job_id, f"{csv_name}: ogiltigt datum {row_raw_date}.")
        return

    if latest_date is not None and row_date <= latest_date:
        _record_live_import_skip(jobs, jobs_lock, job_id)
        return

    description = _build_live_import_description(row, mapping)
    try:
        result = create_transaction(
            session,
            row_raw_date,
            description,
            row[mapping.amount_idx],
            account_id,
            firefly_url,
            dry_run=False,
            log=False,
        )
    except (RuntimeError, ValueError, requests.RequestException) as exc:
        _record_live_import_error(jobs, jobs_lock, job_id, f"Transaktionsfel: {exc}")
        return

    if result is None:
        with jobs_lock:
            jobs[job_id]["summary"]["failed"] += 1
        return

    response, _transaction_type, _amount_abs = result
    _record_live_import_result(jobs, jobs_lock, job_id, response)


def _process_live_import_csv(
    *,
    csv_path: Path,
    latest_date: date | None,
    session: requests.Session,
    firefly_url: str,
    account_id: int,
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
) -> None:
    _update_live_import_file_context(jobs, jobs_lock, job_id, csv_path.name)

    with csv_path.open(encoding="utf-8-sig") as handle:
        reader = csv.reader(handle, delimiter=";")
        headers = next(reader, None)
        if headers is None:
            _record_live_import_warning(jobs, jobs_lock, job_id, f"{csv_path.name}: tom fil.")
            return

        bank_format = resolve_bank_format(headers)
        if bank_format is None:
            _record_live_import_error(jobs, jobs_lock, job_id, f"{csv_path.name}: okänt CSV-format.")
            return

        mapping = bank_format.build_column_mapping(headers)
        for row in reader:
            _handle_live_import_row(
                row=row,
                mapping=mapping,
                latest_date=latest_date,
                csv_name=csv_path.name,
                session=session,
                firefly_url=firefly_url,
                account_id=account_id,
                jobs=jobs,
                jobs_lock=jobs_lock,
                job_id=job_id,
            )


def _process_live_import_folder(
    *,
    folder_name: str,
    import_base: Path,
    account_map: dict[str, int],
    session: requests.Session,
    firefly_url: str,
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
) -> None:
    _update_live_import_folder_context(jobs, jobs_lock, job_id, folder_name)

    folder_path = import_base / folder_name
    account_id = find_account_id(folder_name, account_map)
    if account_id is None:
        _record_live_import_error(jobs, jobs_lock, job_id, f"Ingen kontomatchning för mapp {folder_name}.")
        return

    if not folder_path.exists() or not folder_path.is_dir():
        _record_live_import_error(jobs, jobs_lock, job_id, f"Mappen {folder_name} finns inte.")
        return

    latest_date = get_latest_transaction_date(session, account_id, firefly_url)
    for csv_path in sorted(folder_path.glob("*.csv")):
        _process_live_import_csv(
            csv_path=csv_path,
            latest_date=latest_date,
            session=session,
            firefly_url=firefly_url,
            account_id=account_id,
            jobs=jobs,
            jobs_lock=jobs_lock,
            job_id=job_id,
        )


def _prepare_live_import_context(
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
    job_id: str,
) -> tuple[str, dict[str, int], requests.Session] | None:
    firefly_url, api_token, settings_warnings = _load_web_firefly_settings()
    with jobs_lock:
        job = jobs[job_id]
        for warning in settings_warnings:
            _add_live_import_event(job, "warning", warning)

    if firefly_url is None or api_token is None:
        _fail_live_import_job(
            jobs,
            jobs_lock,
            job_id,
            error="Firefly-inställningar saknas.",
            event_message="Avbryter: saknar URL eller token.",
        )
        return None

    accounts = load_account_cache()
    if not accounts:
        _fail_live_import_job(
            jobs,
            jobs_lock,
            job_id,
            error="Kontocache saknas.",
            event_message="Avbryter: kontocache saknas.",
        )
        return None

    account_map = {a["name"]: a["id"] for a in accounts}
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {api_token}", "Accept": "application/json"})
    return firefly_url, account_map, session


def _run_live_import_job(
    job_id: str,
    folders: list[str],
    import_base: Path,
    jobs: dict[str, LiveImportJob],
    jobs_lock: threading.Lock,
) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return
        job["state"] = "running"
        _add_live_import_event(job, "info", f"Startar live import för {len(folders)} mappar.")

    try:
        context = _prepare_live_import_context(jobs, jobs_lock, job_id)
        if context is None:
            return

        firefly_url, account_map, session = context
        for folder_name in folders:
            _process_live_import_folder(
                folder_name=folder_name,
                import_base=import_base,
                account_map=account_map,
                session=session,
                firefly_url=firefly_url,
                jobs=jobs,
                jobs_lock=jobs_lock,
                job_id=job_id,
            )

        with jobs_lock:
            job = jobs[job_id]
            job["state"] = "completed"
            _add_live_import_event(job, "info", "Live import slutförd.")
    except Exception as exc:  # pragma: no cover
        _fail_live_import_job(
            jobs,
            jobs_lock,
            job_id,
            error=str(exc),
            event_message=f"Jobbet avbröts: {exc}",
        )


def _get_account_candidates(folder: str, account_map: dict[str, int]) -> list[AccountCandidate]:
    candidates: list[AccountCandidate] = []
    folder_key = folder
    if folder_key.startswith("kontoutdrag_"):
        folder_key = folder_key[len("kontoutdrag_") :]
    folder_lower = sanitize_folder_name(folder_key).lower()

    for account_name, account_id in account_map.items():
        account_lower = sanitize_folder_name(account_name).lower()
        if account_lower in folder_lower or folder_lower in account_lower:
            candidates.append({"id": account_id, "name": account_name})

    return candidates


def _build_selection_button_html(all_resolved: bool) -> str:
    if all_resolved:
        return "<p><button type='submit' name='action' value='select'>Fortsätt med denna mappning</button></p>"

    return (
        "<p><button type='submit' name='action' value='select' disabled>"
        "Alla mappar måste mappas innan fortsättning</button></p>"
        "<p style='color:red;'>Obs: Alla mappar måste ha en vald Firefly-konto.<br/>"
        "Se över automatisk matchning och gör handvalda korrigeringar om behövligt.</p>"
    )


def _build_selection_rows(selected: list[str], account_map: dict[str, int]) -> tuple[str, bool]:
    account_rows: list[str] = []
    all_resolved = True

    for folder in selected:
        best_match_id = find_account_id(folder, account_map)
        candidates = _get_account_candidates(folder, account_map)
        if best_match_id is None:
            all_resolved = False

        selected_id = best_match_id or (candidates[0]["id"] if candidates else None)
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

    return "".join(account_rows), all_resolved


def _read_settings() -> SettingsRead:
    firefly_url: str | None = None
    if CONFIG_FILE.exists():
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            raw = str(data.get("firefly_url", "")).strip()
            firefly_url = raw or None

    token_exists = False
    if SECRETS_FILE.exists():
        with contextlib.suppress(json.JSONDecodeError):
            data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
            token_exists = bool(str(data.get("api_token", "")).strip())
    elif TOKEN_FILE.exists():
        token_exists = bool(TOKEN_FILE.read_text(encoding="utf-8").strip())

    return {"firefly_url": firefly_url, "token_exists": token_exists}


def _save_settings(url: str, token: str) -> SettingsSaveResult:
    config: dict[str, object] = {}
    if CONFIG_FILE.exists():
        with contextlib.suppress(json.JSONDecodeError):
            config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    config["firefly_url"] = url
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    secrets: dict[str, object] = {}
    if SECRETS_FILE.exists():
        with contextlib.suppress(json.JSONDecodeError):
            secrets = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
    secrets["api_token"] = token
    SECRETS_FILE.write_text(json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"success": True, "error": None}


def _get_import_base(request: Request) -> Path:
    return cast(Path, request.app.state.import_base)


def _get_job_store(request: Request) -> tuple[dict[str, LiveImportJob], threading.Lock]:
    jobs = cast(dict[str, LiveImportJob], request.app.state.jobs)
    jobs_lock = cast(threading.Lock, request.app.state.jobs_lock)
    return jobs, jobs_lock


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> str:
    import_base = _get_import_base(request)
    previews = list_import_folders(import_base)
    return (
        "<html><head><meta charset='utf-8'><title>Firefly Import</title></head><body>"
        "<h1>Välj importmappar</h1>"
        f"<p>Basmapp: {escape(str(import_base))}</p>"
        f"{_render_folder_table(previews)}"
        "<p><a href='/upload'>Ladda upp CSV-filer</a></p>"
        "<p><a href='/history'>Importhistorik &amp; loggar</a></p>"
        "<p><form method='post' action='/api/refresh-accounts' style='display:inline'>"
        "<button type='submit'>Uppdatera konton</button></form></p>"
        "<p><a href='/settings'>Inställningar (Firefly URL &amp; token)</a></p>"
        "</body></html>"
    )


@router.get("/history", response_class=HTMLResponse)
def history_page() -> str:
    runs = _list_import_history_runs()
    return (
        "<html><head><meta charset='utf-8'><title>Importhistorik</title></head><body>"
        f"{_render_import_history_page(runs)}"
        "</body></html>"
    )


@router.get("/history/{run_id}", response_class=HTMLResponse)
def history_details_page(run_id: str) -> str:
    details = _get_import_history_details(run_id)
    if details is None:
        raise HTTPException(status_code=404, detail={"error": "Importkörning hittades inte."})
    return (
        "<html><head><meta charset='utf-8'><title>Importlogg</title></head><body>"
        f"{_render_import_history_details_page(details)}"
        "</body></html>"
    )


@router.get("/api/import-history")
def api_import_history() -> dict[str, Any]:
    return {"runs": _list_import_history_runs()}


@router.get("/api/import-history/{run_id}")
def api_import_history_details(run_id: str) -> dict[str, Any]:
    details = _get_import_history_details(run_id)
    if details is None:
        raise HTTPException(status_code=404, detail={"error": "Importkörning hittades inte."})
    return dict(details)


def _perform_refresh_accounts(import_base: Path) -> RefreshAccountsResult:
    firefly_url, api_token, _ = _load_web_firefly_settings()
    if not firefly_url or not api_token:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail={"error": "Firefly URL och API-token måste konfigureras innan kontoinhämtning."},
        )
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {api_token}"
    accounts = fetch_accounts_from_firefly(session, firefly_url)
    save_account_cache(accounts)
    new_folders = 0
    for account in accounts:
        folder_name = f"kontoutdrag_{sanitize_folder_name(account['name'])}"
        folder_path = import_base / folder_name
        if not folder_path.exists():
            folder_path.mkdir(parents=True)
            new_folders += 1
    return {"total_accounts": len(accounts), "new_folders": new_folders}


@router.post("/api/refresh-accounts")
def api_refresh_accounts(request: Request) -> dict[str, Any]:
    import_base = _get_import_base(request)
    try:
        return dict(_perform_refresh_accounts(import_base))
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(
            status_code=HTTPStatus.BAD_GATEWAY,
            detail={"error": str(exc)},
        ) from exc


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> str:
    previews = list_import_folders(_get_import_base(request))
    return (
        "<html><head><meta charset='utf-8'><title>CSV-upload</title></head><body>"
        f"{_render_upload_form(previews)}"
        "<p><a href='/'>Tillbaka</a></p>"
        "</body></html>"
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_page_submit(request: Request, folder: UploadFolderForm, files: UploadFilesForm) -> str:
    import_base = _get_import_base(request)
    result = _handle_csv_upload(import_base, folder, files)
    previews = list_import_folders(import_base)
    return (
        "<html><head><meta charset='utf-8'><title>CSV-upload resultat</title></head><body>"
        f"{_render_upload_results(result)}"
        f"{_render_upload_form(previews, message='Du kan ladda upp fler filer direkt.')}"
        "<p><a href='/'>Tillbaka</a></p>"
        "</body></html>"
    )


@router.get("/selection", response_class=HTMLResponse)
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
    accounts_html, all_resolved = _build_selection_rows(selected, account_map)
    button_html = _build_selection_button_html(all_resolved)
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


@router.get("/api/folders")
def api_folders(request: Request) -> dict[str, Any]:
    import_base = _get_import_base(request)
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


@router.get("/api/account-candidates")
def api_account_candidates(folder: str) -> dict[str, Any]:
    accounts = load_account_cache()
    if not accounts:
        return {"folder": folder, "candidates": [], "error": "Ingen kontocache tillgänglig"}

    account_map = {a["name"]: a["id"] for a in accounts}
    best_match_id = find_account_id(folder, account_map)
    candidates = _get_account_candidates(folder, account_map)
    return {"folder": folder, "best_match": best_match_id, "candidates": candidates}


@router.post("/api/upload-csv")
async def api_upload_csv(request: Request, folder: UploadFolderForm, files: UploadFilesForm) -> dict[str, Any]:
    return _handle_csv_upload(_get_import_base(request), folder, files)


@router.get("/api/dry-run-preview")
def api_dry_run_preview(request: Request) -> dict[str, Any]:
    folders = request.query_params.getlist("folder")
    summary = _build_dry_run_summary(folders, _get_import_base(request))
    return {
        "folders": summary["folders"],
        "totals": summary["totals"],
        "can_continue": summary["can_continue"],
    }


@router.get("/preview", response_class=HTMLResponse)
def preview_page(request: Request) -> str:
    folders = request.query_params.getlist("folder")
    summary = _build_dry_run_summary(folders, _get_import_base(request))
    hidden_inputs = "".join(f"<input type='hidden' name='folder' value='{escape(folder)}'>" for folder in folders)
    live_button = (
        "<p><button type='submit'>Starta live import</button></p>"
        if summary["can_continue"]
        else "<p><button type='submit' disabled>Starta live import</button></p>"
    )
    return (
        "<html><head><meta charset='utf-8'><title>Dry-run preview</title></head><body>"
        f"{_render_dry_run_preview(summary)}"
        "<form method='get' action='/live-import'>"
        f"{hidden_inputs}"
        f"{live_button}"
        "</form>"
        "<p><a href='/'>Tillbaka</a></p>"
        "</body></html>"
    )


@router.get("/live-import", response_class=HTMLResponse)
def live_import_page(request: Request) -> str:
    folders = request.query_params.getlist("folder")
    return _render_live_import_page(folders)


@router.post("/api/live-import/start")
async def api_live_import_start(request: Request) -> dict[str, Any]:
    body = await request.json()
    raw_folders = body.get("folders", []) if isinstance(body, dict) else []
    folders = [str(item) for item in raw_folders if isinstance(item, str)]

    job_id = str(uuid4())
    job: LiveImportJob = {
        "job_id": job_id,
        "state": "queued",
        "current_folder": None,
        "current_file": None,
        "summary": {"imported": 0, "skipped": 0, "failed": 0},
        "events": [],
        "error": None,
    }

    import_base = _get_import_base(request)
    jobs, jobs_lock = _get_job_store(request)
    with jobs_lock:
        jobs[job_id] = job

    threading.Thread(
        target=_run_live_import_job,
        args=(job_id, folders, import_base, jobs, jobs_lock),
        daemon=True,
    ).start()
    return {"job_id": job_id, "state": "queued"}


@router.get("/api/live-import/status")
def api_live_import_status(request: Request, job_id: str) -> dict[str, Any]:
    jobs, jobs_lock = _get_job_store(request)
    with jobs_lock:
        job = jobs.get(job_id)
        if job is None:
            return {"error": "Okänt jobb-id."}
        return {
            "job_id": job["job_id"],
            "state": job["state"],
            "current_folder": job["current_folder"],
            "current_file": job["current_file"],
            "summary": job["summary"],
            "events": job["events"],
            "error": job["error"],
        }


@router.get("/settings")
def api_settings_read() -> dict[str, Any]:
    return dict(_read_settings())


def _raise_validation_error(message: str) -> None:
    raise HTTPException(
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        detail={"success": False, "error": message},
    )


@router.post("/api/settings")
async def api_settings_save(request: Request) -> dict[str, Any]:
    body = await request.json()
    url = str(body.get("firefly_url", "")).strip().rstrip("/") if isinstance(body, dict) else ""
    token = str(body.get("api_token", "")).strip() if isinstance(body, dict) else ""

    if not url:
        _raise_validation_error("Firefly URL får inte vara tom.")
    if not token:
        _raise_validation_error("API-token får inte vara tom.")
    if not validate_firefly_url(url):
        _raise_validation_error(f"URL-validering misslyckades: {url} svarade inte med HTTP 200.")

    return dict(_save_settings(url, token))


def create_app(base_folder: Path | None = None) -> FastAPI:
    app = FastAPI(title="Firefly Import Web UI", version="0.1.0")
    app.state.import_base = base_folder or _DEFAULT_IMPORT_BASE
    app.state.jobs = {}
    app.state.jobs_lock = threading.Lock()
    app.include_router(router)
    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("firefly_bank_importer.web_ui:app", host="127.0.0.1", port=8000, reload=False)
