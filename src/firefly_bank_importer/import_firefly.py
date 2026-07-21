import contextlib
import csv
import json
import logging
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any, NamedTuple, TypedDict, cast

from firefly_python_api import FireflyClient, FireflyConnectionError
from tqdm import tqdm

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.bank_formats.base import BankFormat, ColumnMapping
from firefly_bank_importer.config import load_api_token, load_firefly_url

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_CACHE_FILE = _PROJECT_ROOT / "accounts_cache.json"

MAX_WORKERS = 5
BLOCK_TRANSACTION_POSTS = False


class Account(TypedDict):
    id: int
    name: str
    type: str


PendingTransaction = tuple[str, str, str]


class PendingRow(NamedTuple):
    """A parsed CSV row awaiting posting, tagged with its account and bank
    format so cross-account transfer matching (UC-31) can compare rows from
    different folders.
    """

    account_id: int
    iso_date: str
    description: str
    amount: str
    bank_format: str
    row_date: date


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


MONTHLY_FILE_RE = re.compile(r"^\d{4}-\d{2}\.csv$")
_KONTOUTDRAG_RE = re.compile(r"konto", re.IGNORECASE)


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
        date_str = client.get_latest_transaction_date(str(account_id), transaction_type="withdrawal,deposit")
    except FireflyConnectionError:
        logging.warning(f"Kunde inte hamta senaste transaktion for konto {account_id}.")
        return None
    if date_str is None:
        return None
    return datetime.strptime(date_str, "%Y-%m-%d").date()


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
) -> date | None:
    """Set the account's opening balance from its earliest bank export row,
    if the account's current opening balance is 0 (UC-30, FR-65).

    Returns the earliest row's date if an opening balance was set (or would
    be set, in dry-run mode), so callers can exclude that row from import;
    returns None otherwise.
    """
    try:
        current = client.get_opening_balance(str(account_id))
    except FireflyConnectionError:
        logging.warning(f"  Kunde inte hamta nuvarande opening balance for konto {account_id}.")
        return None

    balance_str = current.get("balance")
    if balance_str is not None and parse_amount(balance_str) != 0:
        return None

    earliest = _find_earliest_balance_row(csv_files)
    if earliest is None:
        logging.warning("  Kunde inte auto-detektera startsaldo (ingen saldokolumn i bankformatet).")
        return None

    iso_date, balance = earliest
    if dry_run:
        logging.info(f"  [DRY RUN] Skulle satta opening balance: {balance} SEK per {iso_date} (rad exkluderas).")
    else:
        client.set_opening_balance(str(account_id), balance, iso_date)
        logging.info(f"  Satte opening balance: {balance} SEK per {iso_date} (rad exkluderad fran import).")

    return datetime.strptime(iso_date, "%Y-%m-%d").date()


def parse_amount(raw_amount: str) -> float:
    cleaned = raw_amount.strip()
    cleaned = re.sub(r"\s*(kr|sek)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


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


def _log_tx_result(transaction_type: str, amount_abs: float, date: str, description: str) -> None:
    logging.info(f"  [OK] [{transaction_type}] {amount_abs:.2f} SEK | {date} | {description}")


def create_transaction(
    client: FireflyClient,
    date: str,
    description: str,
    amount: str | float,
    account_id: int,
    dry_run: bool = False,
    log: bool = True,
) -> tuple[str, float] | None:
    parsed_amount = parse_amount(str(amount))
    payload = _build_transaction_payload(date, description, parsed_amount, account_id)
    transaction_type = payload["type"]
    amount_abs = abs(parsed_amount)

    if dry_run:
        logging.info(
            "  [DRY RUN] [%s] %.2f SEK | %s | %s",
            transaction_type,
            amount_abs,
            date,
            description,
        )
        return None

    if BLOCK_TRANSACTION_POSTS:
        raise RuntimeError("POST av transaktion blockerad eftersom dry-run-skydd är aktivt.")

    client.create_transaction({"transactions": [payload]})

    if log:
        _log_tx_result(transaction_type, amount_abs, date, description)

    return transaction_type, amount_abs


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
    batch: list[PendingTransaction],
) -> list[Any]:
    return [
        executor.submit(create_transaction, client, tx_date, desc, amount, account_id, False, log=False)
        for tx_date, desc, amount in batch
    ]


def _handle_batch_result(fut: Any, tx_date: str, desc: str, pbar: "tqdm[Any] | None") -> bool:
    """Returns True on success, False on error/None result. Always advances pbar."""
    try:
        result = fut.result()
    except (FireflyConnectionError, RuntimeError, ValueError) as exc:
        logging.error(f"  [FEL] {tx_date} | {desc}: {exc}")
        if pbar is not None:
            pbar.update(1)
        return False
    if pbar is not None:
        pbar.update(1)
    if result is None:
        return False
    transaction_type, amount_abs = result
    _log_tx_result(transaction_type, amount_abs, tx_date, desc)
    return True


def _run_threaded_import(
    client: FireflyClient,
    pending: list[PendingTransaction],
    account_id: int,
    pbar: "tqdm[Any] | None" = None,
) -> None:
    ok = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_start in range(0, len(pending), MAX_WORKERS):
            batch = pending[batch_start : batch_start + MAX_WORKERS]
            futures = _submit_batch(executor, client, account_id, batch)
            for fut, (tx_date, desc, _amount) in zip(futures, batch, strict=True):
                if _handle_batch_result(fut, tx_date, desc, pbar):
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
) -> None:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            logging.error(f"Okant CSV-format i {csv_path.name}. Hittade headers: {headers}")
            return
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
        with tqdm(total=len(pending), desc=f"{csv_path.name} (dry-run)", unit="rad") as pbar:
            for date, description, amount in pending:
                create_transaction(client, date, description, amount, account_id, dry_run=True)
                pbar.update(1)
        logging.info(f"  Summa: {len(pending)} transaktioner")
    else:
        with tqdm(total=len(pending), desc=csv_path.name, unit="rad") as pbar:
            _run_threaded_import(client, pending, account_id, pbar=pbar)

    if skipped:
        logging.info(f"  Hoppade over: {skipped} rader")


def process_folder(
    client: FireflyClient,
    folder: Path,
    account_map: dict[str, int],
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
) -> None:
    account_id = find_account_id(folder.name, account_map)
    if not account_id:
        logging.warning(f"Inget konto hittat för {folder.name}, hoppar över.")
        return

    auto_split_folder(folder)

    csv_files = sorted(f for f in folder.glob("*.csv") if MONTHLY_FILE_RE.match(f.name))
    if not csv_files:
        logging.warning(f"Inga CSV-filer i {folder.name}, hoppar över.")
        return

    opening_balance_floor = _apply_auto_opening_balance(client, account_id, csv_files, dry_run)

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

    for csv_path in csv_files:
        logging.info(f"Bearbetar: {csv_path.name}")
        process_csv(client, csv_path, account_id, dry_run, latest_date)


def _resolve_folder_account_and_files(folder: Path, account_map: dict[str, int]) -> tuple[int, list[Path]] | None:
    account_id = find_account_id(folder.name, account_map)
    if not account_id:
        logging.warning(f"Inget konto hittat för {folder.name}, hoppar över.")
        return None
    auto_split_folder(folder)
    csv_files = sorted(f for f in folder.glob("*.csv") if MONTHLY_FILE_RE.match(f.name))
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
    opening_balance_floor = _apply_auto_opening_balance(client, account_id, csv_files, dry_run)
    latest_date = None
    if not ignore_latest_date_check:
        latest_date = get_latest_transaction_date(client, account_id)
    if opening_balance_floor is not None and (latest_date is None or opening_balance_floor > latest_date):
        latest_date = opening_balance_floor
    return latest_date


def _collect_csv_pending_rows(
    csv_path: Path, account_id: int, latest_date: date | None
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
        PendingRow(account_id, d, desc, amt, bank_format.name, datetime.strptime(d, "%Y-%m-%d").date())
        for d, desc, amt in pending
    ]
    return rows, skipped


def _gather_folder_pending(
    client: FireflyClient,
    folder: Path,
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
) -> list[PendingRow]:
    resolved = _resolve_folder_account_and_files(folder, account_map)
    if resolved is None:
        return []
    account_id, csv_files = resolved
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
        rows, skipped = _collect_csv_pending_rows(csv_path, account_id, latest_date)
        all_rows.extend(rows)
        total_skipped += skipped
    if total_skipped:
        logging.info(f"  Hoppade over: {total_skipped} rader")
    return all_rows


def _description_overlap(a: str, b: str) -> bool:
    a_lower, b_lower = a.lower(), b.lower()
    return a_lower in b_lower or b_lower in a_lower


MAX_TRANSFER_DATE_DIFF_DAYS = 3


def _is_amount_and_date_match(row: PendingRow, other: PendingRow) -> bool:
    if other.account_id == row.account_id:
        return False
    if abs(parse_amount(row.amount) + parse_amount(other.amount)) > 0.005:
        return False
    return abs((row.row_date - other.row_date).days) <= MAX_TRANSFER_DATE_DIFF_DAYS


def _candidates_for_row(idx: int, rows: list[PendingRow], excluded: set[int]) -> list[int]:
    row = rows[idx]
    return [
        j for j, other in enumerate(rows) if j != idx and j not in excluded and _is_amount_and_date_match(row, other)
    ]


def _choose_among(row: PendingRow, rows: list[PendingRow], candidates: list[int]) -> int | None:
    """Pick the single candidate whose description overlaps row's, or None."""
    overlapping = [j for j in candidates if _description_overlap(row.description, rows[j].description)]
    if len(overlapping) == 1:
        return overlapping[0]
    return None


def _choose_candidate(row: PendingRow, rows: list[PendingRow], candidates: list[int]) -> int | None:
    """Choose a matching candidate per UC-31/FR-66 (TASK-056).

    Same-day (0-day) candidates use amount-only matching when unambiguous;
    a lone same-day candidate is chosen outright. With several same-day
    candidates, description overlap disambiguates. Candidates 1-3 days away
    are only ever chosen via description overlap — an amount-only match is
    never made across differing dates, to avoid pairing unrelated
    transactions that coincidentally share an amount.
    """
    same_day = [j for j in candidates if rows[j].row_date == row.row_date]
    if len(same_day) == 1:
        return same_day[0]
    if len(same_day) > 1:
        return _choose_among(row, rows, same_day)
    near_day = [j for j in candidates if rows[j].row_date != row.row_date]
    return _choose_among(row, rows, near_day)


def _resolve_row_choice(idx: int, rows: list[PendingRow], matched: set[int]) -> int | None:
    candidates = _candidates_for_row(idx, rows, matched)
    if not candidates:
        return None
    return _choose_candidate(rows[idx], rows, candidates)


def _match_transfer_pairs(rows: list[PendingRow]) -> tuple[list[tuple[int, int]], set[int]]:
    """Pair rows across different accounts per UC-31 (FR-66).

    A pair is only formed when the match is mutual: row i's best (possibly
    disambiguated) candidate is j, and j's own best candidate is i. This
    avoids one row in an ambiguous group "stealing" a pairing just because
    it happens to be processed first while looking unambiguous from its own
    side (e.g. three same-amount rows where two share the same counterpart
    candidates).

    Returns (pairs of row indices, set of all matched row indices).
    """
    matched: set[int] = set()
    pairs: list[tuple[int, int]] = []
    for i in range(len(rows)):
        if i in matched:
            continue
        chosen = _resolve_row_choice(i, rows, matched)
        if chosen is None:
            continue
        if _resolve_row_choice(chosen, rows, matched) != i:
            continue
        pairs.append((i, chosen))
        matched.add(i)
        matched.add(chosen)
    return pairs, matched


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
    client: FireflyClient, payload: dict[str, str], dry_run: bool, pbar: "tqdm[Any] | None" = None
) -> None:
    summary = (
        f"{payload['amount']} SEK | {payload['date']} | "
        f"{payload['source_id']} -> {payload['destination_id']} | {payload['description']}"
    )
    try:
        if dry_run:
            logging.info(f"  [DRY RUN] [transfer] {summary}")
            return
        if BLOCK_TRANSACTION_POSTS:
            raise RuntimeError("POST av transaktion blockerad eftersom dry-run-skydd är aktivt.")
        try:
            client.create_transaction({"transactions": [payload]})
        except FireflyConnectionError as exc:
            logging.error(f"  [FEL] transfer {payload['date']}: {exc}")
            return
        logging.info(f"  [OK] [transfer] {summary}")
    finally:
        if pbar is not None:
            pbar.update(1)


def _post_unmatched_rows(
    client: FireflyClient, rows: list[PendingRow], dry_run: bool, pbar: "tqdm[Any] | None" = None
) -> None:
    by_account: dict[int, list[PendingTransaction]] = defaultdict(list)
    for row in rows:
        by_account[row.account_id].append((row.iso_date, row.description, row.amount))
    for account_id, pending in by_account.items():
        if dry_run:
            for tx_date, description, amount in pending:
                create_transaction(client, tx_date, description, amount, account_id, dry_run=True)
                if pbar is not None:
                    pbar.update(1)
            logging.info(f"  Konto {account_id}: {len(pending)} transaktioner")
        else:
            _run_threaded_import(client, pending, account_id, pbar=pbar)


def _run_multi_folder_import(
    client: FireflyClient,
    folders: list[Path],
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
) -> None:
    all_rows: list[PendingRow] = []
    for folder in folders:
        all_rows.extend(_gather_folder_pending(client, folder, account_map, dry_run, ignore_latest_date_check))

    pairs, matched = _match_transfer_pairs(all_rows)
    logging.info(f"Detekterade {len(pairs)} overforing(ar) mellan konton.")

    unmatched = [row for idx, row in enumerate(all_rows) if idx not in matched]
    total = len(pairs) + len(unmatched)
    with tqdm(total=total, desc="Import", unit="rad") as pbar:
        for i, j in pairs:
            _post_transfer(client, _build_transfer_payload(all_rows[i], all_rows[j]), dry_run, pbar=pbar)
        _post_unmatched_rows(client, unmatched, dry_run, pbar=pbar)


def _parse_cli_args(argv: list[str]) -> tuple[str, bool, bool, bool, bool]:
    if len(argv) < 2:
        raise ValueError(
            "Användning: python3 import_firefly.py <sökväg> "
            "[--dry-run] [--ignore-latest-date-check] [--refresh-accounts] [--configure]\n"
            "  Stödda filtyper i importmappen:\n"
            "    kontoutdrag-fil — filnamn innehåller 'konto' (t.ex. kontoutdrag_seb.csv, kontoutdrag 20260505.csv)\n"
            "    månadsfil       — filnamn matchar YYYY-MM.csv (t.ex. 2026-01.csv)"
        )

    dry_run = "--dry-run" in argv
    ignore_latest_date_check = "--ignore-latest-date-check" in argv
    refresh_accounts = "--refresh-accounts" in argv
    configure = "--configure" in argv

    try:
        folder = next(arg for arg in argv[1:] if not arg.startswith("--"))
    except StopIteration as exc:
        raise ValueError("Sökväg saknas. Ange en mapp före eller efter flaggor.") from exc

    return folder, dry_run, ignore_latest_date_check, refresh_accounts, configure


def main(
    base_folder: str | None = None,
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
    refresh_accounts: bool = False,
    configure: bool = False,
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
            ) = _parse_cli_args(sys.argv)
        except ValueError as exc:
            print(str(exc))
            return 1

    BLOCK_TRANSACTION_POSTS = dry_run

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
        _run_multi_folder_import(client, folders, account_map, dry_run, ignore_latest_date_check)
    else:
        for folder in folders:
            process_folder(client, folder, account_map, dry_run, ignore_latest_date_check)

    logging.info("Klar!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
