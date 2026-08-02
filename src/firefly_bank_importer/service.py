"""Service layer for the Firefly bank importer (FR-71, FR-72, FR-73).

This module has no dependency on stdout/print, argparse, process exit codes,
or terminal-only libraries (e.g. tqdm), so it can be imported by external
applications without pulling in CLI-only concerns. Progress and results are
communicated only through return values and structured types.
"""

import re
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import NamedTuple


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
