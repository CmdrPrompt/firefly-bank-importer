"""Service layer for the Firefly bank importer (FR-71, FR-72, FR-73).

This module has no dependency on stdout/print, argparse, process exit codes,
or terminal-only libraries (e.g. tqdm), so it can be imported by external
applications without pulling in CLI-only concerns. Progress and results are
communicated only through return values and structured types.
"""

import contextlib
import csv
import re
from collections import defaultdict
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NamedTuple, TypedDict, cast

from firefly_python_api import FireflyClient, FireflyConnectionError

from firefly_bank_importer.bank_formats import resolve_bank_format
from firefly_bank_importer.bank_formats.base import BankFormat, ColumnMapping


class PendingRow(NamedTuple):
    """A parsed CSV row awaiting posting, tagged with its account and bank
    format so cross-account transfer matching (UC-31) can compare rows from
    different folders.
    """

    account_id: int
    account_name: str
    iso_date: str
    description: str
    amount: str
    bank_format: str
    row_date: date


class TransactionStatus(StrEnum):
    """Outcome status carried by `TransactionResult` and `TransferResult`:
    `OK` (posted, or would be posted in dry-run mode) or `ERROR` (posting
    failed or was blocked; see the result's `error_message`)."""

    OK = "OK"
    ERROR = "ERROR"


@dataclass(frozen=True)
class TransactionResult:
    """Outcome of posting (or attempting to post) a single transaction."""

    date: str
    amount: float
    account_id: int
    status: TransactionStatus
    error_message: str | None = None
    description: str = ""
    account_name: str = ""


@dataclass(frozen=True)
class TransferResult:
    """Outcome of posting (or attempting to post) a transfer between two
    accounts (UC-31/FR-66)."""

    date: str
    amount: float
    description: str
    source_account_id: int
    source_account_name: str
    destination_account_id: int
    destination_account_name: str
    status: TransactionStatus
    error_message: str | None = None


@dataclass(frozen=True)
class OpeningBalanceResult:
    """Outcome of auto-detecting and setting an account's opening balance
    (UC-30/FR-65)."""

    account_id: int
    balance: float
    date: str
    excluded_row_date: str
    dry_run: bool


@dataclass(frozen=True)
class TransferDetectionSummary:
    """Count of transfer pairs detected during a multi-folder import
    (UC-31), emitted once before the per-item posting results so the CLI
    can render the "Detekterade N overforing(ar)..." summary line and size
    its progress bar before consuming the rest of the stream."""

    pairs_count: int
    total: int


@dataclass(frozen=True)
class FolderResult:
    """Aggregated outcome of processing one account folder."""

    folder: str
    account_id: int | None
    transactions: list[TransactionResult] = field(default_factory=list)
    ok_count: int = 0
    error_count: int = 0


@dataclass(frozen=True)
class ProgressEvent:
    """A single unit of progress within a folder's import run."""

    folder: str
    completed: int
    total: int


def parse_amount(raw_amount: str) -> float:
    cleaned = raw_amount.strip()
    cleaned = re.sub(r"\s*(kr|sek)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


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


# ---------------------------------------------------------------------------
# Public/internal helpers finalized as the stable service-layer surface
# (FR-71/72/73, TASK-068). Moved here from `import_firefly.py` (TASK-067's
# CLI module) so external applications can import them without pulling in
# any CLI-only concern (argparse, tqdm, `sys.exit`, `logging` configuration).
# ---------------------------------------------------------------------------


class Account(TypedDict):
    """A Firefly asset account as surfaced to callers of this service layer."""

    id: int
    name: str
    type: str


PendingTransaction = tuple[str, str, str]

MAX_WORKERS = 5

BLOCK_GUARD_MESSAGE = "POST av transaktion blockerad eftersom dry-run-skydd är aktivt."

#: Test-safety guard (not a production feature): when True, `create_transaction`
#: and `post_transfer` report a structured ERROR result instead of calling the
#: Firefly client, without raising. Toggled by test fixtures; production code
#: only ever sets it equal to `dry_run` (itself already short-circuited before
#: this guard is reached), so it has no effect on real imports.
BLOCK_TRANSACTION_POSTS = False

MONTHLY_FILE_RE = re.compile(r"^\d{4}-\d{2}\.csv$")


def sanitize_folder_name(name: str) -> str:
    """Normalise an account name into a filesystem-safe folder-name fragment.

    Replaces Swedish diacritics with their ASCII equivalents, strips
    characters that are illegal in filenames on common platforms, and
    replaces spaces with underscores.

    Args:
        name: The raw account (or folder) name.

    Returns:
        The sanitised name, safe for use as a filesystem path component.
    """
    name = name.replace("å", "a").replace("Å", "A")
    name = name.replace("ä", "a").replace("Ä", "A")
    name = name.replace("ö", "o").replace("Ö", "O")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.replace(" ", "_")
    return name.strip("_")


def _resolve_account_name(account_id: int, account_map: dict[str, int]) -> str:
    for name, aid in account_map.items():
        if aid == account_id:
            return name
    return str(account_id)


PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _validate_period(period: str) -> None:
    if not PERIOD_RE.match(period):
        raise ValueError(f"Ogiltigt --period-varde: '{period}'. Ange formatet ÅÅÅÅ-MM (t.ex. 2025-06).")


def _resolve_column_mapping(headers: list[str]) -> tuple[BankFormat, ColumnMapping] | None:
    bank_format = resolve_bank_format(headers)
    if bank_format is None:
        return None
    return bank_format, bank_format.build_column_mapping(headers)


def fetch_accounts_from_firefly(client: FireflyClient) -> list[Account]:
    """Fetch all asset accounts from Firefly III via `client`.

    Args:
        client: A configured `FireflyClient` (real or test double), provided
            by the caller -- this service layer never constructs its own
            HTTP client (FR-73).

    Returns:
        A list of `Account` dicts (`id`, `name`, `type`).

    Raises:
        firefly_python_api.FireflyConnectionError: If the request to
            Firefly fails (network error, non-2xx response, etc.); not
            caught here -- callers decide how to handle connectivity
            failures.
    """
    raw = client.get_asset_accounts()
    return [{"id": int(a["id"]), "name": a["name"], "type": "asset"} for a in raw]


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

    Args:
        client: A configured `FireflyClient`, provided by the caller.
        date: ISO (`YYYY-MM-DD`) transaction date.
        description: Free-text transaction description.
        amount: Signed amount (negative = withdrawal, positive = deposit),
            as a raw string (e.g. `"-10,00"`) or float; parsed via
            `parse_amount`.
        account_id: The Firefly asset account ID this transaction belongs to.
        dry_run: If True, simulate the post and return an OK result without
            calling the client.
        account_name: Optional display name for the account, carried on the
            result for rendering; falls back to the numeric ID string.

    Returns:
        A `TransactionResult` (FR-71) with `status` OK or ERROR. No
        `logging` calls are made here -- rendering the outcome is the
        caller's job (FR-72).
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


def _opening_balance_floor(result: OpeningBalanceResult | None) -> date | None:
    if result is None:
        return None
    return datetime.strptime(result.excluded_row_date, "%Y-%m-%d").date()


def apply_auto_opening_balance(
    client: FireflyClient,
    account_id: int,
    csv_files: list[Path],
    dry_run: bool,
) -> OpeningBalanceResult | None:
    """Set the account's opening balance from its earliest bank export row,
    if the account's current opening balance is 0 (UC-30, FR-65).

    Args:
        client: A configured `FireflyClient`, provided by the caller.
        account_id: The Firefly asset account ID to inspect/update.
        csv_files: The account's CSV export files to search for the
            earliest dated row with a balance column.
        dry_run: If True, do not call `client.set_opening_balance`; only
            report what would happen.

    Returns:
        A structured `OpeningBalanceResult` (FR-71) if an opening balance
        was set (or would be set, in dry-run mode), so callers can exclude
        that row from import; `None` if no opening balance was set (current
        balance already non-zero, no balance column available, or the
        client call failed). No `logging` is performed here -- rendering is
        the caller's responsibility (FR-72).

    Raises:
        firefly_python_api.FireflyConnectionError: Only if raised by
            `client.set_opening_balance` itself (the initial
            `get_opening_balance` lookup's connection errors are caught and
            treated as "no opening balance set").
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


def post_transfer(
    client: FireflyClient,
    payload: dict[str, str],
    dry_run: bool,
    source_name: str | None = None,
    destination_name: str | None = None,
) -> TransferResult:
    """Post (or simulate posting) a transfer between two accounts (UC-31,
    FR-66).

    Args:
        client: A configured `FireflyClient`, provided by the caller.
        payload: A Firefly transfer payload as built by
            `_build_transfer_payload` (`type`, `date`, `amount`,
            `description`, `source_id`, `destination_id`, `currency_code`).
        dry_run: If True, simulate the post and return an OK result without
            calling the client.
        source_name: Optional display name for the source account.
        destination_name: Optional display name for the destination account.

    Returns:
        A structured `TransferResult`; no `logging` calls are made here. A
        `BLOCK_TRANSACTION_POSTS` guard hit is reported as an ERROR result
        rather than raised, matching `create_transaction`'s handling of the
        same guard (FR-71).
    """
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
    here -- the caller renders and advances its own progress indicator per
    yielded result."""
    display_name = account_name if account_name is not None else str(account_id)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_start in range(0, len(pending), MAX_WORKERS):
            batch = pending[batch_start : batch_start + MAX_WORKERS]
            futures = _submit_batch(executor, client, account_id, display_name, batch)
            for fut, (tx_date, desc, _amount) in zip(futures, batch, strict=True):
                yield _handle_batch_result(fut, tx_date, desc, account_id, display_name)


def _filter_csv_files_for_period(csv_files: list[Path], period: str | None) -> list[Path]:
    if period is None:
        return csv_files
    return [f for f in csv_files if f.stem == period]


def _compute_latest_date_floor(
    client: FireflyClient,
    account_id: int,
    csv_files: list[Path],
    dry_run: bool,
    ignore_latest_date_check: bool,
) -> date | None:
    """Combine the auto-detected opening-balance floor (UC-30) with the
    latest known Firefly transaction date for `account_id` (via the silent,
    logging-free `_latest_transaction_date` lookup, keeping this function
    logging-free per FR-71), returning the later (more restrictive) of the
    two as the cutoff below which CSV rows are skipped as
    already-imported. Used only by `run_multi_folder_import`'s
    self-contained gather step (`_gather_folder_pending` below); the CLI's
    own gather path (`import_firefly._gather_folder_pending`) inlines the
    equivalent logic itself so it can render the opening-balance outcome
    and use its own connectivity-logging latest-date lookup."""
    opening_balance_result = apply_auto_opening_balance(client, account_id, csv_files, dry_run)
    opening_balance_floor = _opening_balance_floor(opening_balance_result)
    latest_date = None
    if not ignore_latest_date_check:
        latest_date = _latest_transaction_date(client, account_id)
    if opening_balance_floor is not None and (latest_date is None or opening_balance_floor > latest_date):
        latest_date = opening_balance_floor
    return latest_date


def _latest_transaction_date(client: FireflyClient, account_id: int) -> date | None:
    """Silent (logging-free) equivalent of the CLI's
    `get_latest_transaction_date`, used as the default lookup by
    `_compute_latest_date_floor` when no caller-supplied lookup is given
    (e.g. by `run_multi_folder_import`'s self-contained gather step)."""
    try:
        transactions = client.get_transactions_by_type(
            "withdrawal,deposit", start="2000-01-01", end=date.today().isoformat()
        )
    except FireflyConnectionError:
        return None
    account_id_str = str(account_id)
    dates = [
        datetime.strptime(tx["date"], "%Y-%m-%d").date()
        for tx in transactions
        if tx["source_id"] == account_id_str or tx["destination_id"] == account_id_str
    ]
    return max(dates) if dates else None


def _account_id_for_folder(folder_name: str, account_map: dict[str, int]) -> int | None:
    """Silent (logging-free) equivalent of the CLI's `find_account_id`,
    used by `run_multi_folder_import`'s self-contained gather step."""
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
    return matches[0][1]


def _collect_csv_pending_rows(
    csv_path: Path, account_id: int, account_name: str, latest_date: date | None
) -> tuple[list[PendingRow], int]:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
        resolved = _resolve_column_mapping(headers)
        if resolved is None:
            return [], 0
        bank_format, mapping = resolved
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
    """Self-contained (logging-free) folder-to-pending-rows resolution used
    by `run_multi_folder_import`. Resolves `folder` to an account via
    `account_map`, lists its monthly CSV files (optionally scoped to
    `period`), and parses each into `PendingRow` objects, skipping rows at
    or before the later of the auto-detected opening-balance floor and the
    latest known Firefly transaction date.

    Unlike the CLI's `import_firefly._gather_folder_pending` (which this
    mirrors), this function does not auto-split non-monthly-named CSV files
    in the folder and performs no `logging` calls (FR-71); it is meant for
    external callers who supply already-monthly-named CSV exports."""
    account_id = _account_id_for_folder(folder.name, account_map)
    if not account_id:
        return []
    csv_files = sorted(f for f in folder.glob("*.csv") if MONTHLY_FILE_RE.match(f.name))
    csv_files = _filter_csv_files_for_period(csv_files, period)
    if not csv_files:
        return []
    account_name = _resolve_account_name(account_id, account_map)
    latest_date = _compute_latest_date_floor(client, account_id, csv_files, dry_run, ignore_latest_date_check)

    all_rows: list[PendingRow] = []
    for csv_path in csv_files:
        rows, _skipped = _collect_csv_pending_rows(csv_path, account_id, account_name, latest_date)
        all_rows.extend(rows)
    return all_rows


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


def _post_transfer_and_unmatched_events(
    client: FireflyClient,
    all_rows: list[PendingRow],
    dry_run: bool,
) -> Iterator[TransferDetectionSummary | TransferResult | TransactionResult]:
    """Detect cross-account transfers (UC-31/FR-66) among already-gathered
    `all_rows` and post everything. Yields a `TransferDetectionSummary`
    first (so a caller can render the detection count and size its own
    progress indicator), then a `TransferResult` per matched pair, then a
    `TransactionResult` per unmatched row.

    Shared by `run_multi_folder_import` (which gathers `all_rows` itself,
    silently) and the CLI adapter (`import_firefly._render_multi_folder_import`,
    which gathers `all_rows` via its own logging-emitting gather step) so
    the transfer-detection and posting logic has a single implementation.
    """
    pairs, matched = _match_transfer_pairs(all_rows)
    unmatched = [row for idx, row in enumerate(all_rows) if idx not in matched]
    total = len(pairs) + len(unmatched)

    yield TransferDetectionSummary(pairs_count=len(pairs), total=total)

    for i, j in pairs:
        a, b = all_rows[i], all_rows[j]
        neg, pos = (a, b) if parse_amount(a.amount) < 0 else (b, a)
        yield post_transfer(
            client,
            _build_transfer_payload(a, b),
            dry_run,
            source_name=neg.account_name,
            destination_name=pos.account_name,
        )

    yield from _post_unmatched_rows(client, unmatched, dry_run)


def run_multi_folder_import(
    client: FireflyClient,
    folders: list[Path],
    account_map: dict[str, int],
    dry_run: bool,
    ignore_latest_date_check: bool,
    period: str | None = None,
) -> Iterator[TransferDetectionSummary | TransferResult | TransactionResult]:
    """Import CSV exports from multiple account folders, detecting
    cross-account transfers (UC-31/FR-66) and posting everything to Firefly.

    This is the primary public entry point for external applications
    (FR-73): given a caller-provided `FireflyClient`, a list of account
    folders (each named/matched against `account_map`), and an
    account-name-to-ID map, it gathers each folder's pending CSV rows,
    matches transfer pairs across accounts, and posts transfers and
    unmatched transactions -- all communicated as a stream of structured
    events, never via `logging` or stdout (FR-71/72).

    Args:
        client: A configured `FireflyClient`, provided by the caller.
        folders: Account folders to import; each folder's name is matched
            against `account_map` to resolve its Firefly account ID.
        account_map: Mapping of account display name to Firefly account ID
            (as returned by `fetch_accounts_from_firefly`).
        dry_run: If True, simulate all posts (no Firefly writes) and report
            what would happen.
        ignore_latest_date_check: If True, skip consulting Firefly for each
            account's latest existing transaction date (all rows are
            considered pending).
        period: Optional `YYYY-MM` filter restricting import to a single
            month's CSV file per folder.

    Yields:
        First a `TransferDetectionSummary` (pair count and total item
        count), then a `TransferResult` per matched transfer pair, then a
        `TransactionResult` per unmatched row.

    Raises:
        Nothing is raised for per-row/per-transfer posting failures --
        those are reported as `TransactionResult`/`TransferResult` objects
        with `status=TransactionStatus.ERROR` (FR-71).
    """
    all_rows: list[PendingRow] = []
    for folder in folders:
        all_rows.extend(_gather_folder_pending(client, folder, account_map, dry_run, ignore_latest_date_check, period))

    yield from _post_transfer_and_unmatched_events(client, all_rows, dry_run)
