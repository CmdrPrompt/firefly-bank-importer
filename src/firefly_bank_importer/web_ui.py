from __future__ import annotations

import csv
import io
import json
import threading
from dataclasses import dataclass
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Annotated, Any, TypedDict
from uuid import uuid4

import requests
from fastapi import FastAPI, File, Form, Request, UploadFile
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
        safe_name = Path(upload.filename or "").name
        if not safe_name:
            results.append(
                {
                    "filename": "(saknar namn)",
                    "status": "rejected",
                    "reason": "Filen saknar namn.",
                    "detected_format": None,
                }
            )
            rejected_count += 1
            continue

        if not safe_name.lower().endswith(".csv"):
            results.append(
                {
                    "filename": safe_name,
                    "status": "rejected",
                    "reason": "Endast .csv-filer stöds.",
                    "detected_format": None,
                }
            )
            rejected_count += 1
            continue

        content = upload.file.read()
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError:
            results.append(
                {
                    "filename": safe_name,
                    "status": "rejected",
                    "reason": "Filen kunde inte avkodas som UTF-8.",
                    "detected_format": None,
                }
            )
            rejected_count += 1
            continue

        reader = csv.reader(io.StringIO(decoded), delimiter=";")
        headers = next(reader, None)
        if headers is None:
            results.append(
                {
                    "filename": safe_name,
                    "status": "rejected",
                    "reason": "Filen är tom.",
                    "detected_format": None,
                }
            )
            rejected_count += 1
            continue

        bank_format = resolve_bank_format(headers)
        if bank_format is None:
            results.append(
                {
                    "filename": safe_name,
                    "status": "rejected",
                    "reason": "CSV-header matchar inget stött format.",
                    "detected_format": None,
                }
            )
            rejected_count += 1
            continue

        target_path = folder_path / safe_name
        if target_path.exists():
            results.append(
                {
                    "filename": safe_name,
                    "status": "rejected",
                    "reason": "Fil med samma namn finns redan i målmappen.",
                    "detected_format": bank_format.name,
                }
            )
            rejected_count += 1
            continue

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


def create_app(base_folder: Path | None = None) -> FastAPI:
    app = FastAPI(title="Firefly Import Web UI", version="0.1.0")
    import_base = base_folder or _DEFAULT_IMPORT_BASE
    jobs: dict[str, LiveImportJob] = {}
    jobs_lock = threading.Lock()

    def add_event(job: LiveImportJob, level: str, message: str) -> None:
        job["events"].append(
            {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "level": level,
                "message": message,
            }
        )

    def run_live_import_job(job_id: str, folders: list[str]) -> None:
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                return
            job["state"] = "running"
            add_event(job, "info", f"Startar live import för {len(folders)} mappar.")

        try:
            firefly_url, api_token, settings_warnings = _load_web_firefly_settings()
            with jobs_lock:
                job = jobs[job_id]
                for warning in settings_warnings:
                    add_event(job, "warning", warning)

            if firefly_url is None or api_token is None:
                with jobs_lock:
                    job = jobs[job_id]
                    job["state"] = "failed"
                    job["error"] = "Firefly-inställningar saknas."
                    add_event(job, "error", "Avbryter: saknar URL eller token.")
                return

            accounts = load_account_cache()
            if not accounts:
                with jobs_lock:
                    job = jobs[job_id]
                    job["state"] = "failed"
                    job["error"] = "Kontocache saknas."
                    add_event(job, "error", "Avbryter: kontocache saknas.")
                return

            account_map = {a["name"]: a["id"] for a in accounts}
            session = requests.Session()
            session.headers.update({"Authorization": f"Bearer {api_token}", "Accept": "application/json"})

            for folder_name in folders:
                with jobs_lock:
                    job = jobs[job_id]
                    job["current_folder"] = folder_name
                    add_event(job, "info", f"Bearbetar mapp: {folder_name}")

                folder_path = import_base / folder_name
                account_id = find_account_id(folder_name, account_map)
                if account_id is None:
                    with jobs_lock:
                        job = jobs[job_id]
                        job["summary"]["failed"] += 1
                        add_event(job, "error", f"Ingen kontomatchning för mapp {folder_name}.")
                    continue

                if not folder_path.exists() or not folder_path.is_dir():
                    with jobs_lock:
                        job = jobs[job_id]
                        job["summary"]["failed"] += 1
                        add_event(job, "error", f"Mappen {folder_name} finns inte.")
                    continue

                latest_date = get_latest_transaction_date(session, account_id, firefly_url)

                for csv_path in sorted(folder_path.glob("*.csv")):
                    with jobs_lock:
                        job = jobs[job_id]
                        job["current_file"] = csv_path.name
                        add_event(job, "info", f"Bearbetar fil: {csv_path.name}")

                    with csv_path.open(encoding="utf-8-sig") as handle:
                        reader = csv.reader(handle, delimiter=";")
                        headers = next(reader, None)
                        if headers is None:
                            with jobs_lock:
                                job = jobs[job_id]
                                add_event(job, "warning", f"{csv_path.name}: tom fil.")
                            continue

                        bank_format = resolve_bank_format(headers)
                        if bank_format is None:
                            with jobs_lock:
                                job = jobs[job_id]
                                job["summary"]["failed"] += 1
                                add_event(job, "error", f"{csv_path.name}: okänt CSV-format.")
                            continue

                        mapping = bank_format.build_column_mapping(headers)
                        for row in reader:
                            if (
                                mapping.date_idx >= len(row)
                                or mapping.description_idx >= len(row)
                                or mapping.amount_idx >= len(row)
                            ):
                                with jobs_lock:
                                    job = jobs[job_id]
                                    job["summary"]["failed"] += 1
                                    add_event(job, "error", f"{csv_path.name}: rad saknar obligatoriska kolumner.")
                                continue

                            try:
                                row_date = datetime.strptime(row[mapping.date_idx], "%Y-%m-%d").date()
                            except ValueError:
                                with jobs_lock:
                                    job = jobs[job_id]
                                    job["summary"]["failed"] += 1
                                    add_event(job, "error", f"{csv_path.name}: ogiltigt datum {row[mapping.date_idx]}.")
                                continue

                            if latest_date is not None and row_date <= latest_date:
                                with jobs_lock:
                                    job = jobs[job_id]
                                    job["summary"]["skipped"] += 1
                                continue

                            description = row[mapping.description_idx].strip()
                            if mapping.transaction_type_idx is not None and mapping.transaction_type_idx < len(row):
                                description = f"{description} [{row[mapping.transaction_type_idx].strip()}]"

                            try:
                                result = create_transaction(
                                    session,
                                    row[mapping.date_idx],
                                    description,
                                    row[mapping.amount_idx],
                                    account_id,
                                    firefly_url,
                                    dry_run=False,
                                    log=False,
                                )
                            except (RuntimeError, ValueError, requests.RequestException) as exc:
                                with jobs_lock:
                                    job = jobs[job_id]
                                    job["summary"]["failed"] += 1
                                    add_event(job, "error", f"Transaktionsfel: {exc}")
                                continue

                            if result is None:
                                with jobs_lock:
                                    job = jobs[job_id]
                                    job["summary"]["failed"] += 1
                                continue

                            response, _transaction_type, _amount_abs = result
                            with jobs_lock:
                                job = jobs[job_id]
                                if response.status_code in (200, 201):
                                    job["summary"]["imported"] += 1
                                else:
                                    job["summary"]["failed"] += 1
                                    add_event(job, "error", f"API-fel: {response.status_code} {response.text[:80]}")

            with jobs_lock:
                job = jobs[job_id]
                job["state"] = "completed"
                add_event(job, "info", "Live import slutförd.")
        except Exception as exc:  # pragma: no cover
            with jobs_lock:
                job = jobs[job_id]
                job["state"] = "failed"
                job["error"] = str(exc)
                add_event(job, "error", f"Jobbet avbröts: {exc}")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        previews = list_import_folders(import_base)
        return (
            "<html><head><meta charset='utf-8'><title>Firefly Import</title></head><body>"
            "<h1>Välj importmappar</h1>"
            f"<p>Basmapp: {escape(str(import_base))}</p>"
            f"{_render_folder_table(previews)}"
            "<p><a href='/upload'>Ladda upp CSV-filer</a></p>"
            "<p><a href='/settings'>Inställningar (Firefly URL &amp; token)</a></p>"
            "</body></html>"
        )

    @app.get("/upload", response_class=HTMLResponse)
    def upload_page() -> str:
        previews = list_import_folders(import_base)
        return (
            "<html><head><meta charset='utf-8'><title>CSV-upload</title></head><body>"
            f"{_render_upload_form(previews)}"
            "<p><a href='/'>Tillbaka</a></p>"
            "</body></html>"
        )

    @app.post("/upload", response_class=HTMLResponse)
    async def upload_page_submit(folder: UploadFolderForm, files: UploadFilesForm) -> str:
        result = _handle_csv_upload(import_base, folder, files)
        previews = list_import_folders(import_base)
        return (
            "<html><head><meta charset='utf-8'><title>CSV-upload resultat</title></head><body>"
            f"{_render_upload_results(result)}"
            f"{_render_upload_form(previews, message='Du kan ladda upp fler filer direkt.')}"
            "<p><a href='/'>Tillbaka</a></p>"
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

    @app.post("/api/upload-csv")
    async def api_upload_csv(folder: UploadFolderForm, files: UploadFilesForm) -> dict[str, Any]:
        return _handle_csv_upload(import_base, folder, files)

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

    @app.get("/live-import", response_class=HTMLResponse)
    def live_import_page(request: Request) -> str:
        folders = request.query_params.getlist("folder")
        return _render_live_import_page(folders)

    @app.post("/api/live-import/start")
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
        with jobs_lock:
            jobs[job_id] = job

        threading.Thread(target=run_live_import_job, args=(job_id, folders), daemon=True).start()
        return {"job_id": job_id, "state": "queued"}

    @app.get("/api/live-import/status")
    def api_live_import_status(job_id: str) -> dict[str, Any]:
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

    @app.get("/settings")
    def api_settings_read() -> dict[str, Any]:
        firefly_url: str | None = None
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                raw = str(data.get("firefly_url", "")).strip()
                firefly_url = raw or None
            except json.JSONDecodeError:
                pass

        token_exists = False
        if SECRETS_FILE.exists():
            try:
                data = json.loads(SECRETS_FILE.read_text(encoding="utf-8"))
                token_exists = bool(str(data.get("api_token", "")).strip())
            except json.JSONDecodeError:
                pass
        elif TOKEN_FILE.exists():
            token_exists = bool(TOKEN_FILE.read_text(encoding="utf-8").strip())

        return {"firefly_url": firefly_url, "token_exists": token_exists}

    @app.post("/api/settings")
    async def api_settings_save(request: Request) -> dict[str, Any]:
        import contextlib  # noqa: PLC0415
        from http import HTTPStatus  # noqa: PLC0415

        from fastapi import HTTPException  # noqa: PLC0415

        body = await request.json()
        url = str(body.get("firefly_url", "")).strip().rstrip("/") if isinstance(body, dict) else ""
        token = str(body.get("api_token", "")).strip() if isinstance(body, dict) else ""

        if not url:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={"success": False, "error": "Firefly URL får inte vara tom."},
            )
        if not token:
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={"success": False, "error": "API-token får inte vara tom."},
            )

        if not validate_firefly_url(url):
            raise HTTPException(
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
                detail={"success": False, "error": f"URL-validering misslyckades: {url} svarade inte med HTTP 200."},
            )

        # Persist — read-modify-write to keep other keys intact

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

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("firefly_bank_importer.web_ui:app", host="127.0.0.1", port=8000, reload=False)
