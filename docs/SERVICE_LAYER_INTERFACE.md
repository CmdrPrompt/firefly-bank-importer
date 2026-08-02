# Service layer interface (`firefly_bank_importer.service`)

This document is the interface guide for the stable, importable service
layer required by FR-71/FR-72/FR-73. It describes the public module path,
the public functions and classes, the event/result types they produce, and
how an external application (e.g. a separate web frontend project) can
import and drive this logic without depending on this repository's CLI
(`firefly_bank_importer.import_firefly`) or running any HTTP server of its
own.

## Module path

```python
from firefly_bank_importer.service import (
    # event / result types
    Account,
    FolderResult,
    OpeningBalanceResult,
    PendingRow,
    ProgressEvent,
    TransactionResult,
    TransactionStatus,
    TransferDetectionSummary,
    TransferResult,
    # public functions
    apply_auto_opening_balance,
    create_transaction,
    fetch_accounts_from_firefly,
    post_transfer,
    run_multi_folder_import,
)
```

The same names are re-exported from the top-level `firefly_bank_importer`
package (`from firefly_bank_importer import run_multi_folder_import, ...`).

This module has no dependency on stdout/print, argparse, process exit
codes, or terminal-only libraries (e.g. `tqdm`); all results are
communicated through return values and the structured types below. It has
no dependency on any web framework (Flask, FastAPI, Django) or HTTP server
(uvicorn, gunicorn, waitress) -- the only HTTP client it uses is a
caller-supplied `firefly_python_api.FireflyClient` instance. This service
layer never constructs its own `FireflyClient`; callers always provide one
(real, against a running Firefly III instance, or a test double/mock).

## Event and result types

| Type | Fields | Emitted by |
|---|---|---|
| `Account` (`TypedDict`) | `id: int`, `name: str`, `type: str` | `fetch_accounts_from_firefly` |
| `TransactionStatus` (`StrEnum`) | `OK`, `ERROR` | carried by `TransactionResult`/`TransferResult` |
| `TransactionResult` (frozen dataclass) | `date: str`, `amount: float`, `account_id: int`, `status: TransactionStatus`, `error_message: str \| None`, `description: str`, `account_name: str` | `create_transaction`, `run_multi_folder_import` |
| `TransferResult` (frozen dataclass) | `date: str`, `amount: float`, `description: str`, `source_account_id: int`, `source_account_name: str`, `destination_account_id: int`, `destination_account_name: str`, `status: TransactionStatus`, `error_message: str \| None` | `post_transfer`, `run_multi_folder_import` |
| `OpeningBalanceResult` (frozen dataclass) | `account_id: int`, `balance: float`, `date: str`, `excluded_row_date: str`, `dry_run: bool` | `apply_auto_opening_balance` |
| `TransferDetectionSummary` (frozen dataclass) | `pairs_count: int`, `total: int` | first event yielded by `run_multi_folder_import` |
| `FolderResult` (frozen dataclass) | `folder: str`, `account_id: int \| None`, `transactions: list[TransactionResult]`, `ok_count: int`, `error_count: int` | aggregate result type available for callers that want a per-folder summary |
| `ProgressEvent` (frozen dataclass) | `folder: str`, `completed: int`, `total: int` | a single unit of progress within a folder's import run |
| `PendingRow` (`NamedTuple`) | `account_id: int`, `account_name: str`, `iso_date: str`, `description: str`, `amount: str`, `bank_format: str`, `row_date: date` | a parsed CSV row awaiting posting/transfer-matching |

## Public functions

### `fetch_accounts_from_firefly(client: FireflyClient) -> list[Account]`

Fetch all asset accounts from Firefly III via `client`.

- **Parameters:** `client` -- a configured `FireflyClient` (real or test
  double), provided by the caller.
- **Returns:** a list of `Account` dicts.
- **Raises:** `firefly_python_api.FireflyConnectionError` if the request
  fails; not caught here.

### `create_transaction(client, date, description, amount, account_id, dry_run=False, account_name=None) -> TransactionResult`

Post (or simulate posting, in dry-run mode) a single transaction.

- **Parameters:**
  - `client: FireflyClient` -- caller-supplied client.
  - `date: str` -- ISO (`YYYY-MM-DD`) transaction date.
  - `description: str` -- free-text description.
  - `amount: str | float` -- signed amount (negative = withdrawal, positive
    = deposit); parsed via `parse_amount`.
  - `account_id: int` -- the Firefly asset account ID.
  - `dry_run: bool` -- if `True`, simulate and return an OK result without
    calling the client.
  - `account_name: str | None` -- optional display name carried on the
    result.
- **Returns:** a `TransactionResult` with `status` `OK` or `ERROR`. No
  `logging` calls are made; rendering is the caller's responsibility.
- **Raises:** posting failures are reported as an `ERROR` result, not
  raised.

### `apply_auto_opening_balance(client, account_id, csv_files, dry_run) -> OpeningBalanceResult | None`

Set the account's opening balance from its earliest bank export row, if
the account's current opening balance is 0 (UC-30, FR-65).

- **Parameters:**
  - `client: FireflyClient` -- caller-supplied client.
  - `account_id: int` -- the Firefly asset account ID to inspect/update.
  - `csv_files: list[Path]` -- the account's CSV export files.
  - `dry_run: bool` -- if `True`, do not call `client.set_opening_balance`.
- **Returns:** an `OpeningBalanceResult` if an opening balance was set (or
  would be, in dry-run mode); `None` otherwise.
- **Raises:** `firefly_python_api.FireflyConnectionError` only if raised by
  `client.set_opening_balance` itself.

### `post_transfer(client, payload, dry_run, source_name=None, destination_name=None) -> TransferResult`

Post (or simulate posting) a transfer between two accounts (UC-31, FR-66).

- **Parameters:**
  - `client: FireflyClient` -- caller-supplied client.
  - `payload: dict[str, str]` -- a Firefly transfer payload (`type`,
    `date`, `amount`, `description`, `source_id`, `destination_id`,
    `currency_code`).
  - `dry_run: bool` -- if `True`, simulate and return an OK result.
  - `source_name`, `destination_name: str | None` -- optional display
    names for the two accounts.
- **Returns:** a `TransferResult`. Posting failures (including the
  internal test-safety guard) are reported as an `ERROR` result, not
  raised.

### `run_multi_folder_import(client, folders, account_map, dry_run, ignore_latest_date_check, period=None) -> Iterator[TransferDetectionSummary | TransferResult | TransactionResult]`

The primary entry point for external applications. Imports CSV exports
from multiple account folders, detects cross-account transfers (UC-31,
FR-66), and posts transfers and unmatched transactions -- communicated
entirely as a stream of structured events.

- **Parameters:**
  - `client: FireflyClient` -- caller-supplied client.
  - `folders: list[Path]` -- account folders to import; each folder's
    name is matched against `account_map` to resolve its Firefly account
    ID.
  - `account_map: dict[str, int]` -- account display name to Firefly
    account ID (as produced from `fetch_accounts_from_firefly`'s result).
  - `dry_run: bool` -- if `True`, simulate all posts.
  - `ignore_latest_date_check: bool` -- if `True`, skip consulting Firefly
    for each account's latest existing transaction date.
  - `period: str | None` -- optional `YYYY-MM` filter restricting import
    to a single month's CSV file per folder.
- **Yields:** first a `TransferDetectionSummary`, then a `TransferResult`
  per matched transfer pair, then a `TransactionResult` per unmatched row.
- **Raises:** nothing for per-row/per-transfer posting failures -- those
  are reported as `TransactionResult`/`TransferResult` objects with
  `status=TransactionStatus.ERROR`.

## Usage example

```python
from pathlib import Path

from firefly_python_api import FireflyClient

from firefly_bank_importer.service import (
    TransactionResult,
    TransferDetectionSummary,
    TransferResult,
    fetch_accounts_from_firefly,
    run_multi_folder_import,
)

# The external application constructs its own client -- this service layer
# never does so itself (FR-73).
client = FireflyClient(base_url="https://firefly.example.com", token="...")

accounts = fetch_accounts_from_firefly(client)
account_map = {account["name"]: account["id"] for account in accounts}

folders = [Path("imports/kontoutdrag_Lonekonto"), Path("imports/kontoutdrag_Sparkonto")]

for event in run_multi_folder_import(
    client,
    folders,
    account_map,
    dry_run=False,
    ignore_latest_date_check=False,
):
    if isinstance(event, TransferDetectionSummary):
        print(f"Detected {event.pairs_count} transfer(s), {event.total} item(s) total")
    elif isinstance(event, TransferResult):
        print(f"transfer {event.status}: {event.source_account_name} -> {event.destination_account_name}")
    elif isinstance(event, TransactionResult):
        print(f"transaction {event.status}: {event.account_name} {event.amount}")
```

## Known gap

A handful of orchestration functions (`process_csv`, `process_folder`,
`build_account_map`, `find_account_id`, `create_import_folders`, and a
couple of their private helpers) still call `logging.*` directly and
remain internal to `firefly_bank_importer.import_firefly` (the CLI
module) rather than being part of this public surface. See
`docs/tasks/TASK-069-*.md` for the follow-up task tracking their
decoupling.
