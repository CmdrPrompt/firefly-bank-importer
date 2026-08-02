import contextlib
import csv
import json
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from firefly_python_api import FireflyClient, FireflyConnectionError
from tqdm import tqdm

from firefly_bank_importer.config import load_api_token, load_firefly_url
from firefly_bank_importer.service import (
    BLOCK_GUARD_MESSAGE,
    BLOCK_TRANSACTION_POSTS,
    MAX_TRANSFER_DATE_DIFF_DAYS,
    Account,
    OpeningBalanceResult,
    PendingRow,
    TransactionResult,
    TransactionStatus,
    TransferDetectionSummary,
    TransferResult,
    _build_transaction_payload,
    _candidates_for_row,
    _choose_among,
    _choose_candidate,
    _collect_pending_rows,
    _compute_latest_date_floor,
    _description_overlap,
    _filter_csv_files_for_period,
    _find_earliest_balance_row,
    _is_amount_and_date_match,
    _match_transfer_pairs,
    _opening_balance_floor,
    _post_transfer_and_unmatched_events,
    _post_unmatched_rows,
    _resolve_account_name,
    _resolve_column_mapping,
    _resolve_row_choice,
    _run_threaded_import,
    _transaction_type_and_abs,
    _validate_period,
    apply_auto_opening_balance,
    create_transaction,
    fetch_accounts_from_firefly,
    parse_amount,
    post_transfer,
    run_multi_folder_import,
    sanitize_folder_name,
)

__all__ = [
    "MAX_TRANSFER_DATE_DIFF_DAYS",
    "Account",
    "BLOCK_GUARD_MESSAGE",
    "BLOCK_TRANSACTION_POSTS",
    "OpeningBalanceResult",
    "PendingRow",
    "TransactionResult",
    "TransactionStatus",
    "TransferDetectionSummary",
    "TransferResult",
    "_build_transaction_payload",
    "_candidates_for_row",
    "_choose_among",
    "_choose_candidate",
    "_collect_pending_rows",
    "_compute_latest_date_floor",
    "_description_overlap",
    "_filter_csv_files_for_period",
    "_find_earliest_balance_row",
    "_is_amount_and_date_match",
    "_match_transfer_pairs",
    "_opening_balance_floor",
    "_post_transfer_and_unmatched_events",
    "_post_unmatched_rows",
    "_resolve_account_name",
    "_resolve_column_mapping",
    "_resolve_row_choice",
    "_run_threaded_import",
    "_transaction_type_and_abs",
    "_validate_period",
    "apply_auto_opening_balance",
    "create_transaction",
    "fetch_accounts_from_firefly",
    "parse_amount",
    "post_transfer",
    "run_multi_folder_import",
    "sanitize_folder_name",
]

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_CACHE_FILE = _PROJECT_ROOT / "accounts_cache.json"

PendingTransaction = tuple[str, str, str]


def setup_logging() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"import_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def save_account_cache(accounts: list[Account]) -> None:
    cache = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "accounts": accounts,
    }
    Path(ACCOUNT_CACHE_FILE).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"Sparade {len(accounts)} konton i {ACCOUNT_CACHE_FILE}.")


def load_account_cache() -> list[Account] | None:
    cache_path = Path(ACCOUNT_CACHE_FILE)
    if not cache_path.exists():
        return None
    try:
        cache_data = cast(dict[str, Any], json.loads(cache_path.read_text(encoding="utf-8")))
        raw_accounts = cache_data.get("accounts", [])
        if not isinstance(raw_accounts, list):
            logging.error(f"Ogiltig cache-fil {ACCOUNT_CACHE_FILE}: accounts är inte en lista")
            return None

        accounts: list[Account] = []
        for item in raw_accounts:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            raw_name = item.get("name")
            raw_type = item.get("type", "asset")
            if isinstance(raw_id, int) and isinstance(raw_name, str) and isinstance(raw_type, str):
                accounts.append({"id": raw_id, "name": raw_name, "type": raw_type})

        fetched_at = cache_data.get("fetched_at", "okänt")
        logging.info(f"Laddade {len(accounts)} konton från cache ({ACCOUNT_CACHE_FILE}, hämtad {fetched_at}).")
        return accounts
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Ogiltig cache-fil {ACCOUNT_CACHE_FILE}: {e}")
        return None


def build_account_map(
    client: FireflyClient,
    refresh: bool = False,
) -> tuple[dict[str, int], list[Account]]:
    accounts: list[Account] | None = None
    if not refresh:
        accounts = load_account_cache()

    if accounts is None:
        logging.info("Hämtar konton från Firefly...")
        try:
            accounts = fetch_accounts_from_firefly(client)
            save_account_cache(accounts)
        except (RuntimeError, FireflyConnectionError) as e:
            logging.error(str(e))
            if not refresh:
                accounts = load_account_cache()
            if accounts is None:
                logging.error(
                    "Ingen cache tillgänglig och Firefly-anrop misslyckades. "
                    "Kör med --refresh-accounts när Firefly är nåbart."
                )
                sys.exit(1)

    return {a["name"]: a["id"] for a in accounts}, accounts


def create_import_folders(base: Path, accounts: list[Account]) -> None:
    created = 0
    for account in accounts:
        folder_name = f"kontoutdrag_{sanitize_folder_name(account['name'])}"
        folder_path = base / folder_name
        if not folder_path.exists():
            folder_path.mkdir(parents=True)
            logging.info(f"  Skapade importmapp: {folder_name}")
            created += 1
    if created:
        logging.info(f"  {created} ny(a) importmapp(ar) skapades i {base}.")
    else:
        logging.info("  Inga nya importmappar behövde skapas.")


def find_account_id(folder_name: str, account_map: dict[str, int]) -> int | None:
    matches: list[tuple[str, int]] = []
    folder_key = folder_name
    if folder_key.startswith("kontoutdrag_"):
        folder_key = folder_key[len("kontoutdrag_") :]
    folder_lower = sanitize_folder_name(folder_key).lower()

    for name, account_id in account_map.items():
        account_lower = sanitize_folder_name(name).lower()
        if account_lower in folder_lower or folder_lower in account_lower:
            matches.append((name, account_id))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0][1]
    matches.sort(key=lambda x: len(x[0]), reverse=True)
    logging.info(f"  Flera kontomatchningar för '{folder_name}': {[m[0] for m in matches]}. Väljer '{matches[0][0]}'.")
    return matches[0][1]


MONTHLY_FILE_RE = re.compile(r"^\d{4}-\d{2}\.csv$")
_KONTOUTDRAG_RE = re.compile(r"konto", re.IGNORECASE)


def split_file_in_place(input_file: Path) -> None:
    months: defaultdict[str, list[list[str]]] = defaultdict(list)

    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            logging.warning(f"  Okänt format i {input_file.name}, hoppar över split.")
            return
        bank_format, mapping = resolved

        datum_idx = mapping.date_idx
        belopp_idx = mapping.amount_idx
        saldo_idx = mapping.balance_idx

        for row in reader:
            with contextlib.suppress(ValueError):
                row[datum_idx] = bank_format.normalise_date(row[datum_idx])
            for idx in (belopp_idx, saldo_idx):
                if idx is None:
                    continue
                with contextlib.suppress(ValueError):
                    row[idx] = f"{parse_amount(row[idx]):.2f}"
            year_month = row[datum_idx][:7]
            months[year_month].append(row)

    for year_month, rows in sorted(months.items()):
        rows.sort(key=lambda row: row[datum_idx])
        output_file = input_file.parent / f"{year_month}.csv"
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerows([headers] + rows)
        logging.info(f"  Splittat: {output_file.name} ({len(rows)} rader)")

    if months:
        input_file.unlink()
        logging.info(f"  Tog bort ursprungsfil: {input_file.name}")


def auto_split_folder(folder: Path) -> None:
    to_split: list[Path] = []
    for f in folder.glob("*.csv"):
        if MONTHLY_FILE_RE.match(f.name):
            continue
        if _KONTOUTDRAG_RE.search(f.name):
            to_split.append(f)
        else:
            logging.warning(f"Okänd filtyp, hoppar över: {f.name}")
    if to_split:
        logging.info(f"  Splittar {len(to_split)} icke-månadssplittad(e) fil(er)...")
        for f in sorted(to_split):
            split_file_in_place(f)


def get_latest_transaction_date(client: FireflyClient, account_id: int) -> date | None:
    try:
        transactions = client.get_transactions_by_type(
            "withdrawal,deposit", start="2000-01-01", end=date.today().isoformat()
        )
    except FireflyConnectionError:
        logging.warning(f"Kunde inte hamta senaste transaktion for konto {account_id}.")
        return None
    account_id_str = str(account_id)
    dates = [
        datetime.strptime(tx["date"], "%Y-%m-%d").date()
        for tx in transactions
        if tx["source_id"] == account_id_str or tx["destination_id"] == account_id_str
    ]
    return max(dates) if dates else None


def _render_opening_balance_result(result: OpeningBalanceResult | None) -> None:
    if result is None:
        return
    if result.dry_run:
        logging.info(
            f"  [DRY RUN] Skulle satta opening balance: {result.balance:.2f} SEK per {result.date} (rad exkluderas)."
        )
    else:
        logging.info(
            f"  Satte opening balance: {result.balance:.2f} SEK per {result.date} (rad exkluderad fran import)."
        )


def _render_transaction_result(result: TransactionResult, dry_run: bool) -> None:
    if result.status == TransactionStatus.ERROR:
        logging.error(f"  [FEL] {result.date} | {result.description}: {result.error_message}")
        return
    transaction_type, amount_abs = _transaction_type_and_abs(result.amount)
    prefix = "[DRY RUN]" if dry_run else "[OK]"
    logging.info(
        f"  {prefix} [{result.account_name}] [{transaction_type}] {amount_abs:.2f} SEK | "
        f"{result.date} | {result.description}"
    )


def _run_dry_run_csv_import(
    client: FireflyClient,
    csv_path: Path,
    pending: list[PendingTransaction],
    account_id: int,
    account_name: str | None,
) -> None:
    with tqdm(total=len(pending), desc=f"{csv_path.name} (dry-run)", unit="rad") as pbar:
        for date, description, amount in pending:
            result = create_transaction(
                client, date, description, amount, account_id, dry_run=True, account_name=account_name
            )
            _render_transaction_result(result, dry_run=True)
            pbar.update(1)
    logging.info(f"  Summa: {len(pending)} transaktioner")


def _run_live_csv_import(
    client: FireflyClient,
    csv_path: Path,
    pending: list[PendingTransaction],
    account_id: int,
    account_name: str | None,
) -> None:
    with tqdm(total=len(pending), desc=csv_path.name, unit="rad") as pbar:
        ok = 0
        errors = 0
        for result in _run_threaded_import(client, pending, account_id, account_name=account_name):
            _render_transaction_result(result, dry_run=False)
            pbar.update(1)
            if result.status == TransactionStatus.OK:
                ok += 1
            else:
                errors += 1
    logging.info(f"  Summa: {ok} ok, {errors} fel")


def process_csv(
    client: FireflyClient,
    csv_path: Path,
    account_id: int,
    dry_run: bool = False,
    latest_date: date | None = None,
    account_name: str | None = None,
) -> int:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            logging.error(f"Okant CSV-format i {csv_path.name}. Hittade headers: {headers}")
            return 0
        csv_format, mapping = resolved

        datum_idx = mapping.date_idx
        text_idx = mapping.description_idx
        belopp_idx = mapping.amount_idx
        type_idx = mapping.transaction_type_idx
        logging.info(f"  Format: {csv_format.name.upper()}")
        if latest_date is not None:
            logging.info(f"  Senaste i Firefly: {latest_date} (hoppar over <= detta datum)")

        pending, skipped = _collect_pending_rows(
            reader, datum_idx, text_idx, belopp_idx, type_idx, latest_date, csv_format.normalise_date
        )

    if dry_run:
        _run_dry_run_csv_import(client, csv_path, pending, account_id, account_name)
    else:
        _run_live_csv_import(client, csv_path, pending, account_id, account_name)

    if skipped:
        logging.info(f"  Hoppade over: {skipped} rader")

    return len(pending)


def process_folder(
    client: FireflyClient,
    folder: Path,
    account_map: dict[str, int],
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
    period: str | None = None,
) -> int:
    account_id = find_account_id(folder.name, account_map)
    if not account_id:
        logging.warning(f"Inget konto hittat för {folder.name}, hoppar över.")
        return 0

    auto_split_folder(folder)

    csv_files = sorted(f for f in folder.glob("*.csv") if MONTHLY_FILE_RE.match(f.name))
    csv_files = _filter_csv_files_for_period(csv_files, period)
    if not csv_files:
        logging.warning(f"Inga CSV-filer i {folder.name}, hoppar över.")
        return 0

    account_name = _resolve_account_name(account_id, account_map)
    opening_balance_result = apply_auto_opening_balance(client, account_id, csv_files, dry_run)
    _render_opening_balance_result(opening_balance_result)
    opening_balance_floor = _opening_balance_floor(opening_balance_result)

    latest_date = None
    if not ignore_latest_date_check:
        latest_date = get_latest_transaction_date(client, account_id)
    if opening_balance_floor is not None and (latest_date is None or opening_balance_floor > latest_date):
        latest_date = opening_balance_floor

    logging.info(f"Konto ID {account_id}: {folder.name}")
    if ignore_latest_date_check:
        logging.info("  Ignorerar senaste datum-kontroll.")
    elif latest_date is None:
        logging.info("  Ingen tidigare transaktion hittades i Firefly.")

    transaction_count = 0
    for csv_path in csv_files:
        logging.info(f"Bearbetar: {csv_path.name}")
        transaction_count += process_csv(client, csv_path, account_id, dry_run, latest_date, account_name=account_name)
    return transaction_count


def _resolve_folder_account_and_files(
    folder: Path, account_map: dict[str, int], period: str | None = None
) -> tuple[int, list[Path]] | None:
    account_id = find_account_id(folder.name, account_map)
    if not account_id:
        logging.warning(f"Inget konto hittat för {folder.name}, hoppar över.")
        return None
    auto_split_folder(folder)
    csv_files = sorted(f for f in folder.glob("*.csv") if MONTHLY_FILE_RE.match(f.name))
    csv_files = _filter_csv_files_for_period(csv_files, period)
    if not csv_files:
        logging.warning(f"Inga CSV-filer i {folder.name}, hoppar över.")
        return None
    return account_id, csv_files


def _collect_csv_pending_rows(
    csv_path: Path, account_id: int, account_name: str, latest_date: date | None
) -> tuple[list[PendingRow], int]:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            logging.error(f"Okant CSV-format i {csv_path.name}. Hittade headers: {headers}")
            return [], 0
        bank_format, mapping = resolved
        logging.info(f"  Format: {bank_format.name.upper()}")
        pending, skipped = _collect_pending_rows(
            reader,
            mapping.date_idx,
            mapping.description_idx,
            mapping.amount_idx,
            mapping.transaction_type_idx,
            latest_date,
            bank_format.normalise_date,
        )
    rows = [
        PendingRow(account_id, account_name, d, desc, amt, bank_format.name, datetime.strptime(d, "%Y-%m-%d").date())
        for d, desc, amt in pending
    ]
    return rows, skipped


def _gather_folder_pending(
    client: FireflyClient,
    folder: Path,
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
    period: str | None = None,
) -> list[PendingRow]:
    resolved = _resolve_folder_account_and_files(folder, account_map, period)
    if resolved is None:
        return []
    account_id, csv_files = resolved
    account_name = _resolve_account_name(account_id, account_map)

    opening_balance_result = apply_auto_opening_balance(client, account_id, csv_files, dry_run)
    _render_opening_balance_result(opening_balance_result)
    opening_balance_floor = _opening_balance_floor(opening_balance_result)

    latest_date = None
    if not ignore_latest_date_check:
        latest_date = get_latest_transaction_date(client, account_id)
    if opening_balance_floor is not None and (latest_date is None or opening_balance_floor > latest_date):
        latest_date = opening_balance_floor

    logging.info(f"Konto ID {account_id}: {folder.name}")
    if ignore_latest_date_check:
        logging.info("  Ignorerar senaste datum-kontroll.")
    elif latest_date is None:
        logging.info("  Ingen tidigare transaktion hittades i Firefly.")

    all_rows: list[PendingRow] = []
    total_skipped = 0
    for csv_path in csv_files:
        logging.info(f"Bearbetar: {csv_path.name}")
        rows, skipped = _collect_csv_pending_rows(csv_path, account_id, account_name, latest_date)
        all_rows.extend(rows)
        total_skipped += skipped
    if total_skipped:
        logging.info(f"  Hoppade over: {total_skipped} rader")
    return all_rows


def _render_transfer_result(result: TransferResult, dry_run: bool) -> None:
    if result.status == TransactionStatus.ERROR:
        logging.error(f"  [FEL] transfer {result.date}: {result.error_message}")
        return
    summary = (
        f"{result.amount:.2f} SEK | {result.date} | "
        f"{result.source_account_name} -> {result.destination_account_name} | {result.description}"
    )
    prefix = "[DRY RUN]" if dry_run else "[OK]"
    logging.info(f"  {prefix} [transfer] {summary}")


class _UnmatchedGroupRenderer:
    """Groups consecutive `TransactionResult` events by account and logs a
    per-account summary line whenever the account changes, matching the
    pre-TASK-067 CLI output for unmatched (non-transfer) rows (FR-72)."""

    def __init__(self, dry_run: bool) -> None:
        self._dry_run = dry_run
        self._account_id: int | None = None
        self._account_name = ""
        self._ok = 0
        self._errors = 0
        self._count = 0

    def handle(self, event: TransactionResult) -> None:
        if self._account_id is not None and event.account_id != self._account_id:
            self.flush()
        self._account_id = event.account_id
        self._account_name = event.account_name
        self._count += 1
        if event.status == TransactionStatus.OK:
            self._ok += 1
        else:
            self._errors += 1
        _render_transaction_result(event, self._dry_run)

    def flush(self) -> None:
        if self._account_id is None:
            return
        if self._dry_run:
            logging.info(f"  Konto {self._account_name}: {self._count} transaktioner")
        else:
            logging.info(f"  Summa: {self._ok} ok, {self._errors} fel")
        self._account_id = None
        self._account_name = ""
        self._ok = self._errors = self._count = 0


def _render_multi_folder_import(
    client: FireflyClient,
    folders: list[Path],
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
    period: str | None = None,
) -> int:
    """CLI adapter: gathers pending rows per folder via `_gather_folder_pending`
    (rendering its own per-folder log lines, unchanged from pre-TASK-067),
    then consumes the shared service-layer `_post_transfer_and_unmatched_events`
    event stream for transfer detection and posting, owning the single
    shared tqdm progress bar and rendering each event to the log identically
    to the pre-TASK-067 behavior (FR-72)."""
    all_rows: list[PendingRow] = []
    for folder in folders:
        all_rows.extend(_gather_folder_pending(client, folder, account_map, dry_run, ignore_latest_date_check, period))

    events = _post_transfer_and_unmatched_events(client, all_rows, dry_run)
    summary = cast(TransferDetectionSummary, next(events))
    logging.info(f"Detekterade {summary.pairs_count} overforing(ar) mellan konton.")

    with tqdm(total=summary.total, desc="Import", unit="rad") as pbar:
        unmatched_renderer = _UnmatchedGroupRenderer(dry_run)
        for event in events:
            if isinstance(event, TransferResult):
                _render_transfer_result(event, dry_run)
            elif isinstance(event, TransactionResult):
                unmatched_renderer.handle(event)
            pbar.update(1)
        unmatched_renderer.flush()

    return summary.total


def _parse_cli_args(argv: list[str]) -> tuple[str, bool, bool, bool, bool, str | None]:
    if len(argv) < 2:
        raise ValueError(
            "Användning: python3 import_firefly.py <sökväg> "
            "[--dry-run] [--ignore-latest-date-check] [--refresh-accounts] [--configure] [--period ÅÅÅÅ-MM]\n"
            "  Stödda filtyper i importmappen:\n"
            "    kontoutdrag-fil — filnamn innehåller 'konto' (t.ex. kontoutdrag_seb.csv, kontoutdrag 20260505.csv)\n"
            "    månadsfil       — filnamn matchar YYYY-MM.csv (t.ex. 2026-01.csv)"
        )

    dry_run = "--dry-run" in argv
    ignore_latest_date_check = "--ignore-latest-date-check" in argv
    refresh_accounts = "--refresh-accounts" in argv
    configure = "--configure" in argv

    remaining = list(argv[1:])
    period: str | None = None
    if "--period" in remaining:
        idx = remaining.index("--period")
        try:
            period = remaining[idx + 1]
        except IndexError as exc:
            raise ValueError("--period kräver ett värde i formatet ÅÅÅÅ-MM.") from exc
        _validate_period(period)
        del remaining[idx : idx + 2]

    try:
        folder = next(arg for arg in remaining if not arg.startswith("--"))
    except StopIteration as exc:
        raise ValueError("Sökväg saknas. Ange en mapp före eller efter flaggor.") from exc

    return folder, dry_run, ignore_latest_date_check, refresh_accounts, configure, period


def main(
    base_folder: str | None = None,
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
    refresh_accounts: bool = False,
    configure: bool = False,
    period: str | None = None,
) -> int:
    global BLOCK_TRANSACTION_POSTS

    if base_folder is None:
        try:
            (
                base_folder,
                dry_run,
                ignore_latest_date_check,
                refresh_accounts,
                configure,
                period,
            ) = _parse_cli_args(sys.argv)
        except ValueError as exc:
            print(str(exc))
            return 1

    # BLOCK_TRANSACTION_POSTS is a test-safety guard read by
    # create_transaction()/post_transfer(), which now live in
    # firefly_bank_importer.service and resolve the name in that module's
    # own globals. Setting it here to `dry_run` is a no-op in practice
    # (both functions already short-circuit on their own `dry_run` check
    # before this guard is ever consulted); this module's re-exported copy
    # is kept in sync for introspection/test compatibility only -- the
    # service module's own global is never mutated by production code,
    # only by test fixtures via monkeypatch (see `service` import above).
    BLOCK_TRANSACTION_POSTS = dry_run
    start_time = time.monotonic()

    log_file = setup_logging()

    token = load_api_token(force=configure)
    firefly_url = load_firefly_url(force=configure)

    client = FireflyClient(firefly_url, token)

    base = Path(base_folder)
    account_map, accounts = build_account_map(client, refresh=refresh_accounts)

    if any(base.glob("*.csv")):
        folders = [base]
    else:
        logging.info("Säkerställer importmappar för alla konton...")
        create_import_folders(base, accounts)
        folders = sorted([f for f in base.iterdir() if f.is_dir()])

    if not folders:
        logging.error("Inga mappar hittades.")
        return 1

    if dry_run:
        logging.info("=== DRY RUN -- inga transaktioner skapas ===")

    logging.info(f"Hittade {len(folders)} kontomapp(ar).")
    logging.info(f"Loggar till: {log_file}")

    if len(folders) > 1:
        transaction_count = _render_multi_folder_import(
            client, folders, account_map, dry_run, ignore_latest_date_check, period
        )
    else:
        transaction_count = 0
        for folder in folders:
            transaction_count += process_folder(client, folder, account_map, dry_run, ignore_latest_date_check, period)

    elapsed_seconds = time.monotonic() - start_time
    logging.info("Klar!")
    logging.info(f"Total tid: {timedelta(seconds=round(elapsed_seconds))}")
    if transaction_count:
        logging.info(f"{elapsed_seconds / transaction_count:.2f}s/transaktion")
    return 0


if __name__ == "__main__":
    sys.exit(main())
