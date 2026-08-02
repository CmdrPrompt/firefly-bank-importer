import contextlib
import csv
import json
import logging
import re
import sys
import time
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict, cast

from firefly_python_api import FireflyClient, FireflyConnectionError
from tqdm import tqdm

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.bank_formats.base import BankFormat, ColumnMapping
from firefly_bank_importer.config import load_api_token, load_firefly_url
from firefly_bank_importer.service import (
    MAX_TRANSFER_DATE_DIFF_DAYS,
    OpeningBalanceResult,
    PendingRow,
    TransactionResult,
    TransactionStatus,
    TransferDetectionSummary,
    TransferResult,
    _candidates_for_row,
    _choose_among,
    _choose_candidate,
    _description_overlap,
    _is_amount_and_date_match,
    _match_transfer_pairs,
    _resolve_row_choice,
    parse_amount,
)

__all__ = [
    "MAX_TRANSFER_DATE_DIFF_DAYS",
    "OpeningBalanceResult",
    "PendingRow",
    "TransactionResult",
    "TransactionStatus",
    "TransferDetectionSummary",
    "TransferResult",
    "_candidates_for_row",
    "_choose_among",
    "_choose_candidate",
    "_description_overlap",
    "_is_amount_and_date_match",
    "_match_transfer_pairs",
    "_resolve_row_choice",
    "parse_amount",
]

BLOCK_GUARD_MESSAGE = "POST av transaktion blockerad eftersom dry-run-skydd är aktivt."

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_CACHE_FILE = _PROJECT_ROOT / "accounts_cache.json"

MAX_WORKERS = 5
BLOCK_TRANSACTION_POSTS = False


class Account(TypedDict):
    id: int
    name: str
    type: str


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


def fetch_accounts_from_firefly(client: FireflyClient) -> list[Account]:
    raw = client.get_asset_accounts()
    return [{"id": int(a["id"]), "name": a["name"], "type": "asset"} for a in raw]


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


def sanitize_folder_name(name: str) -> str:
    name = name.replace("å", "a").replace("Å", "A")
    name = name.replace("ä", "a").replace("Ä", "A")
    name = name.replace("ö", "o").replace("Ö", "O")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.replace(" ", "_")
    return name.strip("_")


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


def _resolve_account_name(account_id: int, account_map: dict[str, int]) -> str:
    for name, aid in account_map.items():
        if aid == account_id:
            return name
    return str(account_id)


MONTHLY_FILE_RE = re.compile(r"^\d{4}-\d{2}\.csv$")
_KONTOUTDRAG_RE = re.compile(r"konto", re.IGNORECASE)
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_period(period: str) -> None:
    if not PERIOD_RE.match(period):
        raise ValueError(f"Ogiltigt --period-varde: '{period}'. Ange formatet ÅÅÅÅ-MM (t.ex. 2025-06).")


def _resolve_column_mapping(headers: list[str]) -> tuple[BankFormat, ColumnMapping] | None:
    bank_format = resolve_bank_format(headers)
    if bank_format is None:
        return None
    return bank_format, bank_format.build_column_mapping(headers)


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


def _earliest_balance_row_in_rows(
    reader: Any, bank_format: BankFormat, mapping: ColumnMapping
) -> tuple[date, str, str] | None:
    earliest: tuple[date, str, str] | None = None
    for row in reader:
        with contextlib.suppress(ValueError, IndexError):
            iso_date = bank_format.normalise_date(row[mapping.date_idx])
            row_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
            balance = f"{parse_amount(row[mapping.balance_idx]):.2f}"
            if earliest is None or row_date < earliest[0]:
                earliest = (row_date, iso_date, balance)
    return earliest


def _earliest_balance_row_in_file(csv_path: Path) -> tuple[date, str, str] | None:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            return None
        bank_format, mapping = resolved
        if mapping.balance_idx is None:
            return None
        return _earliest_balance_row_in_rows(reader, bank_format, mapping)


def _find_earliest_balance_row(csv_files: list[Path]) -> tuple[str, str] | None:
    """Return (iso_date, balance) of the earliest-dated row across csv_files.

    Only considers files whose bank format defines a balance column. Returns
    None if no such row is found (no balance column available, or no rows).
    """
    earliest: tuple[date, str, str] | None = None
    for csv_path in csv_files:
        candidate = _earliest_balance_row_in_file(csv_path)
        if candidate is not None and (earliest is None or candidate[0] < earliest[0]):
            earliest = candidate
    if earliest is None:
        return None
    return earliest[1], earliest[2]


def _apply_auto_opening_balance(
    client: FireflyClient,
    account_id: int,
    csv_files: list[Path],
    dry_run: bool,
) -> OpeningBalanceResult | None:
    """Set the account's opening balance from its earliest bank export row,
    if the account's current opening balance is 0 (UC-30, FR-65).

    Returns a structured result (FR-71) if an opening balance was set (or
    would be set, in dry-run mode), so callers can exclude that row from
    import and the CLI can render the outcome; returns None otherwise (no
    logging is performed here -- rendering is the CLI's responsibility).
    """
    try:
        current = client.get_opening_balance(str(account_id))
    except FireflyConnectionError:
        return None

    balance_str = current.get("balance")
    if balance_str is not None and parse_amount(balance_str) != 0:
        return None

    earliest = _find_earliest_balance_row(csv_files)
    if earliest is None:
        return None

    iso_date, balance = earliest
    if not dry_run:
        client.set_opening_balance(str(account_id), balance, iso_date)

    return OpeningBalanceResult(
        account_id=account_id,
        balance=parse_amount(balance),
        date=iso_date,
        excluded_row_date=iso_date,
        dry_run=dry_run,
    )


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


def _opening_balance_floor(result: OpeningBalanceResult | None) -> date | None:
    if result is None:
        return None
    return datetime.strptime(result.excluded_row_date, "%Y-%m-%d").date()


def _build_transaction_payload(date: str, description: str, amount: float, account_id: int) -> dict[str, str]:
    if amount < 0:
        return {
            "type": "withdrawal",
            "date": date,
            "amount": f"{abs(amount):.2f}",
            "description": description,
            "source_id": str(account_id),
            "currency_code": "SEK",
        }
    return {
        "type": "deposit",
        "date": date,
        "amount": f"{amount:.2f}",
        "description": description,
        "destination_id": str(account_id),
        "currency_code": "SEK",
    }


def _transaction_type_and_abs(amount: float) -> tuple[str, float]:
    """Derive the Firefly transaction type (withdrawal/deposit) and display
    magnitude from a signed amount (negative = withdrawal, per FR-69)."""
    return ("withdrawal" if amount < 0 else "deposit", abs(amount))


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


def create_transaction(
    client: FireflyClient,
    date: str,
    description: str,
    amount: str | float,
    account_id: int,
    dry_run: bool = False,
    account_name: str | None = None,
) -> TransactionResult:
    """Post (or simulate posting, in dry-run mode) a single transaction.

    Returns a structured `TransactionResult` (FR-71); no `logging` calls are
    made here -- rendering the outcome is the CLI adapter's job (FR-72).
    """
    parsed_amount = parse_amount(str(amount))
    display_name = account_name if account_name is not None else str(account_id)

    if dry_run:
        return TransactionResult(
            date=date,
            amount=parsed_amount,
            account_id=account_id,
            status=TransactionStatus.OK,
            description=description,
            account_name=display_name,
        )

    if BLOCK_TRANSACTION_POSTS:
        return TransactionResult(
            date=date,
            amount=parsed_amount,
            account_id=account_id,
            status=TransactionStatus.ERROR,
            error_message=BLOCK_GUARD_MESSAGE,
            description=description,
            account_name=display_name,
        )

    payload = _build_transaction_payload(date, description, parsed_amount, account_id)
    client.create_transaction({"transactions": [payload]})

    return TransactionResult(
        date=date,
        amount=parsed_amount,
        account_id=account_id,
        status=TransactionStatus.OK,
        description=description,
        account_name=display_name,
    )


def _collect_pending_rows(
    reader: Any,
    datum_idx: int,
    text_idx: int,
    belopp_idx: int,
    type_idx: int | None,
    latest_date: date | None,
    normalise_date: Callable[[str], str],
) -> tuple[list[PendingTransaction], int]:
    skipped = 0
    pending: list[PendingTransaction] = []
    for row in reader:
        iso_date = normalise_date(row[datum_idx])
        row_date = datetime.strptime(iso_date, "%Y-%m-%d").date()
        if latest_date is not None and row_date <= latest_date:
            skipped += 1
            continue
        description = row[text_idx].strip()
        if type_idx is not None:
            description = f"{description} [{row[type_idx].strip()}]"
        pending.append((iso_date, description, row[belopp_idx]))
    return pending, skipped


def _submit_batch(
    executor: ThreadPoolExecutor,
    client: FireflyClient,
    account_id: int,
    account_name: str,
    batch: list[PendingTransaction],
) -> list[Any]:
    return [
        executor.submit(create_transaction, client, tx_date, desc, amount, account_id, False, account_name)
        for tx_date, desc, amount in batch
    ]


def _handle_batch_result(fut: Any, tx_date: str, desc: str, account_id: int, account_name: str) -> TransactionResult:
    """Resolve a submitted future into a structured `TransactionResult`,
    turning any posting exception into an ERROR result instead of letting
    it propagate (FR-71)."""
    try:
        return cast(TransactionResult, fut.result())
    except (FireflyConnectionError, RuntimeError, ValueError) as exc:
        return TransactionResult(
            date=tx_date,
            amount=0.0,
            account_id=account_id,
            status=TransactionStatus.ERROR,
            error_message=str(exc),
            description=desc,
            account_name=account_name,
        )


def _run_threaded_import(
    client: FireflyClient,
    pending: list[PendingTransaction],
    account_id: int,
    account_name: str | None = None,
) -> Iterator[TransactionResult]:
    """Post `pending` transactions concurrently, yielding a `TransactionResult`
    per row as it completes (FR-71). No progress bar or logging is owned
    here -- the CLI adapter renders and advances its own tqdm bar per
    yielded result."""
    display_name = account_name if account_name is not None else str(account_id)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_start in range(0, len(pending), MAX_WORKERS):
            batch = pending[batch_start : batch_start + MAX_WORKERS]
            futures = _submit_batch(executor, client, account_id, display_name, batch)
            for fut, (tx_date, desc, _amount) in zip(futures, batch, strict=True):
                yield _handle_batch_result(fut, tx_date, desc, account_id, display_name)


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


def _filter_csv_files_for_period(csv_files: list[Path], period: str | None) -> list[Path]:
    if period is None:
        return csv_files
    return [f for f in csv_files if f.stem == period]


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
    opening_balance_result = _apply_auto_opening_balance(client, account_id, csv_files, dry_run)
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


def _compute_latest_date_floor(
    client: FireflyClient,
    account_id: int,
    csv_files: list[Path],
    dry_run: bool,
    ignore_latest_date_check: bool,
) -> date | None:
    opening_balance_result = _apply_auto_opening_balance(client, account_id, csv_files, dry_run)
    _render_opening_balance_result(opening_balance_result)
    opening_balance_floor = _opening_balance_floor(opening_balance_result)
    latest_date = None
    if not ignore_latest_date_check:
        latest_date = get_latest_transaction_date(client, account_id)
    if opening_balance_floor is not None and (latest_date is None or opening_balance_floor > latest_date):
        latest_date = opening_balance_floor
    return latest_date


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
    latest_date = _compute_latest_date_floor(client, account_id, csv_files, dry_run, ignore_latest_date_check)

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


def _build_transfer_payload(a: PendingRow, b: PendingRow) -> dict[str, str]:
    neg, pos = (a, b) if parse_amount(a.amount) < 0 else (b, a)
    return {
        "type": "transfer",
        "date": neg.iso_date,
        "amount": f"{abs(parse_amount(neg.amount)):.2f}",
        "description": neg.description,
        "source_id": str(neg.account_id),
        "destination_id": str(pos.account_id),
        "currency_code": "SEK",
    }


def _post_transfer(
    client: FireflyClient,
    payload: dict[str, str],
    dry_run: bool,
    source_name: str | None = None,
    destination_name: str | None = None,
) -> TransferResult:
    """Post (or simulate posting) a transfer between two accounts (UC-31,
    FR-66). Returns a structured `TransferResult`; no `logging` calls are
    made here. A `BLOCK_TRANSACTION_POSTS` guard hit is reported as an
    ERROR result rather than raised, matching `create_transaction`'s
    handling of the same guard (FR-71 -- closes the pre-existing
    inconsistency between the two posting paths)."""
    amount = parse_amount(payload["amount"])
    source_id = int(payload["source_id"])
    destination_id = int(payload["destination_id"])
    source_display = source_name if source_name is not None else payload["source_id"]
    destination_display = destination_name if destination_name is not None else payload["destination_id"]

    def _result(status: TransactionStatus, error_message: str | None = None) -> TransferResult:
        return TransferResult(
            date=payload["date"],
            amount=amount,
            description=payload["description"],
            source_account_id=source_id,
            source_account_name=source_display,
            destination_account_id=destination_id,
            destination_account_name=destination_display,
            status=status,
            error_message=error_message,
        )

    if dry_run:
        return _result(TransactionStatus.OK)

    if BLOCK_TRANSACTION_POSTS:
        return _result(TransactionStatus.ERROR, BLOCK_GUARD_MESSAGE)

    try:
        client.create_transaction({"transactions": [payload]})
    except FireflyConnectionError as exc:
        return _result(TransactionStatus.ERROR, str(exc))

    return _result(TransactionStatus.OK)


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


def _post_unmatched_rows(client: FireflyClient, rows: list[PendingRow], dry_run: bool) -> Iterator[TransactionResult]:
    """Post rows that were not matched to a transfer (UC-31), grouped by
    account. Yields a `TransactionResult` per row; no progress bar or
    logging is owned here (FR-71)."""
    by_account: dict[int, list[PendingTransaction]] = defaultdict(list)
    account_names: dict[int, str] = {}
    for row in rows:
        by_account[row.account_id].append((row.iso_date, row.description, row.amount))
        account_names[row.account_id] = row.account_name
    for account_id, pending in by_account.items():
        account_name = account_names[account_id]
        if dry_run:
            for tx_date, description, amount in pending:
                yield create_transaction(
                    client, tx_date, description, amount, account_id, dry_run=True, account_name=account_name
                )
        else:
            yield from _run_threaded_import(client, pending, account_id, account_name=account_name)


def _run_multi_folder_import(
    client: FireflyClient,
    folders: list[Path],
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
    period: str | None = None,
) -> Iterator[TransferDetectionSummary | TransferResult | TransactionResult]:
    """Gather pending rows across all folders, detect cross-account
    transfers (UC-31/FR-66), and post everything. Yields a
    `TransferDetectionSummary` first (so the CLI can render the detection
    count and size its progress bar), then a `TransferResult` per matched
    pair, then a `TransactionResult` per unmatched row. No `tqdm` instance
    is created here -- that is the CLI adapter's responsibility (FR-71/72).
    """
    all_rows: list[PendingRow] = []
    for folder in folders:
        all_rows.extend(_gather_folder_pending(client, folder, account_map, dry_run, ignore_latest_date_check, period))

    pairs, matched = _match_transfer_pairs(all_rows)
    unmatched = [row for idx, row in enumerate(all_rows) if idx not in matched]
    total = len(pairs) + len(unmatched)

    yield TransferDetectionSummary(pairs_count=len(pairs), total=total)

    for i, j in pairs:
        a, b = all_rows[i], all_rows[j]
        neg, pos = (a, b) if parse_amount(a.amount) < 0 else (b, a)
        yield _post_transfer(
            client,
            _build_transfer_payload(a, b),
            dry_run,
            source_name=neg.account_name,
            destination_name=pos.account_name,
        )

    yield from _post_unmatched_rows(client, unmatched, dry_run)


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
    """CLI adapter: consumes `_run_multi_folder_import`'s event stream,
    owns the single shared tqdm progress bar, and renders each event to
    the log identically to the pre-TASK-067 behavior (FR-72)."""
    events = _run_multi_folder_import(client, folders, account_map, dry_run, ignore_latest_date_check, period)
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
