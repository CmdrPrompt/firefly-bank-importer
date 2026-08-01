# Requirements Specification: import_firefly.py

## 1. Purpose and Scope
This document defines the requirements and use cases for the current implementation of import_firefly.py (version 1.0.0) and the planned changes tracked under [Unreleased].

The script is intended to import bank transactions from CSV files (SEB, ICA, and Nordea formats) into Firefly III through its API, both as a standalone CLI tool and as an importable service layer for external applications (e.g. a separate web frontend project) — this repository does not run its own web server.

## 2. Goals
- Import transactions from one or more account folders. Multi-account import (UC-2) is the primary real-world usage pattern: only importing multiple accounts together lets cross-account transfer detection (UC-31) match transfers correctly. Single-folder import (UC-1) remains a supported but secondary capability.
- Reduce duplicate imports through latest-date validation against Firefly.
- Support dry runs without creating transactions.
- Handle unsplit export files by automatically splitting them by month.
- Provide clear logging to both terminal and log file.
- Discover available destination asset accounts from Firefly instead of relying on a hardcoded list.
- Cache discovered accounts locally so they can be reused in later runs.
- Store Firefly URL and API token in local files so the user is only prompted once.
- Isolate bank export formats in separate packages so new banks can be added without changing the core importer.
- Identify bank export formats by reading CSV headers and mapping source columns to Firefly-relevant fields through bank-specific format packages.

## 3. System Context
- Input: CSV files in account folders.
- Configuration: Firefly URL in config.json in the project root.
- Configuration: API token in secrets.json in the project root (token file supported as fallback).
- Configuration: cached account list file generated from Firefly account discovery.
- Bank format packages: local Python packages that describe how a bank export file is recognized and how its columns map to normalized transaction fields.
- Target environment: Firefly III API.
- Output: created transactions in Firefly III and a log file named import_YYYYMMDD_HHMMSS.log.
- Core import logic (folder/account resolution, CSV parsing, opening-balance detection, transfer detection, transaction posting) lives in a service layer independent of any interface. It has no dependency on stdout/print, argparse, process exit codes, or terminal-only libraries (e.g. tqdm); it communicates progress and results only through return values and structured events.
- The CLI (`import_firefly.py` entry point) is a thin adapter over the service layer: it parses argv, calls the service layer, and renders CLI-specific output (stdout, a tqdm progress bar, exit codes) from the structured results/events it receives.
- This repository does not run its own web server or HTTP UI. The service layer is packaged so it can be imported by an external application — a separate frontend project (its own repository) that also serves other Firefly-related tools (e.g. a bills-analysis project) — which is responsible for any HTTP API, web UI, background-job execution, and progress streaming built on top of it.

## 4. Use Cases

### UC-1: Import a single account folder
- Actor: User
- Preconditions: The account folder contains CSV files and the folder name matches an account in the discovered/cached account list.
- Trigger: The user runs the script with the folder path.
- Main flow:
1. The script starts logging.
2. The script reads the token.
3. The script identifies the account from the folder name.
4. The script splits unsplit CSV files into monthly files.
5. The script reads and imports each CSV file.
6. The script logs the outcome.
- Result: Transactions are imported to the correct Firefly account.

### UC-2: Import multiple account folders
- Actor: User
- Preconditions: The provided path contains subfolders with account data.
- Trigger: The user runs the script with a base directory path.
- Main flow:
1. The script lists all subfolders.
2. The script executes UC-1 for each folder in sorted order.
- Result: All valid account folders are processed.

### UC-3: Dry run
- Actor: User
- Trigger: The user provides the --dry-run flag.
- Main flow:
1. The script parses transactions as usual.
2. The script does not perform API POST calls.
3. The script logs which transactions would have been imported.
- Result: Import validation without changing data in Firefly.

### UC-4: Prevent duplicate imports using latest date
- Actor: System
- Preconditions: The --ignore-latest-date-check flag is not used.
- Main flow:
1. The script fetches the latest withdrawal/deposit transaction date for the account from Firefly, excluding transfers.
2. The script skips rows with date <= latest date.
3. The script imports only newer rows.
- Result: Reduced risk of duplicate imports.

### UC-5: Force import of historical rows
- Actor: User
- Trigger: The user provides the --ignore-latest-date-check flag.
- Main flow:
1. The script skips latest-date retrieval.
2. The script imports all rows in the CSV files.
- Result: Full import, including historical rows.

### UC-6: Automatically split an unsplit export file
- Actor: System
- Preconditions: A CSV file in the folder is not named YYYY-MM.csv.
- Main flow:
1. The script identifies an unsplit file.
2. The script splits the file by year-month.
3. The script normalizes amount and balance values to decimal-dot format.
4. The script sorts rows in each monthly file chronologically.
5. The script removes the source file after a successful split.
- Result: Monthly files are ready for import.

### UC-7: Parallel import with ordered logging
- Actor: System
- Preconditions: Not in dry-run mode.
- Main flow:
1. The script groups transactions into batches of MAX_WORKERS.
2. The script submits transactions in each batch in parallel to Firefly.
3. The script writes log lines sequentially in CSV order while collecting batch results.
- Result: Improved performance while keeping ordered logs.

### UC-8: Discover importable asset accounts from Firefly
- Actor: User
- Trigger: The user runs the script with --refresh-accounts, or no cache file exists.
- Main flow:
1. The script calls the Firefly API for asset accounts available to the token.
2. The script filters and normalizes account metadata required for import.
3. The script stores the account list in a local cache file.
4. The script creates local import folders named kontoutdrag_<sanitized-account-name> for each discovered account.
5. The script logs how many accounts were discovered, cached, and how many folders were created.
- Result: The tool has an up-to-date local account list from Firefly and ready-to-use import folders.

### UC-9: Reuse cached account list on later runs
- Actor: System
- Preconditions: A valid local account cache file exists.
- Main flow:
1. The script loads the cached account list at startup.
2. The script resolves folder-to-account mapping using cached account names/aliases.
3. The script performs import without requiring a discovery API call every run.
- Result: Faster startup and no hardcoded account table dependency.

### UC-10: Fallback when Firefly account discovery is unavailable
- Actor: System
- Trigger: Discovery API fails due to network/auth/server issues.
- Main flow:
1. The script logs that discovery failed.
2. The script uses the last known valid cache if available.
3. If no cache exists, the script aborts account-resolution steps with clear errors.
- Result: Predictable behavior during API outages and clear operator guidance.

### UC-11: Automatic creation of import folders
- Actor: System
- Preconditions: Account discovery has completed (live or refresh).
- Main flow:
1. For each discovered account the script derives a sanitized folder name.
2. Folder name sanitization replaces Swedish characters (å→a, ä→a, ö→o) and spaces with underscores, and strips invalid filesystem characters.
3. The script creates any folder that does not already exist under the base directory.
4. Existing folders are left unchanged.
5. The script logs names of created folders and total count.
- Result: Import folders with consistent, filesystem-safe names exist for all accounts.

### UC-12: Configure Firefly connection on first run
- Actor: User
- Trigger: config.json or secrets.json is missing, or the user provides the --configure flag.
- Main flow:
1. If the Firefly URL is missing, the script prompts the user to enter it interactively.
2. The script validates the URL by calling /api/v1/about and reports the result.
3. If validation succeeds, the script saves the URL to config.json.
4. If the API token is missing, the script prompts the user to enter it interactively with hidden input.
5. The script saves the token to secrets.json.
6. The script continues with normal startup once both values are available.
- Result: config.json and secrets.json are created and used on all subsequent runs without prompting.

### UC-13: Resolve a bank export format through a format package
- Actor: System
- Trigger: The script opens a CSV file for split or import.
- Main flow:
1. The script reads the CSV header row.
2. The script evaluates registered bank format packages against the header.
3. The script selects the matching format package.
4. The format package provides a mapping from source columns to normalized fields required by the importer.
5. The script uses the normalized mapping for split and import processing.
- Result: The core importer can process supported bank formats without embedding bank-specific parsing rules in the main module.

### UC-14: Add a new bank export format without changing the core importer
- Actor: Developer
- Trigger: A new bank export CSV format needs to be supported.
- Main flow:
1. The developer creates a new bank format package in the designated format-package location.
2. The package declares how to recognize the CSV header.
3. The package declares how CSV columns map to normalized transaction fields.
4. The core importer discovers and uses the package during normal processing.
- Result: New bank formats can be added by extension rather than by editing core CSV detection logic.

### UC-23: Clear old import logs
- Actor: User
- Trigger: The user chooses to clear logs from the CLI.
- Main flow:
1. The system lists existing import log files.
2. The user chooses clear scope (all logs or logs older than N days).
3. The system asks for confirmation before deletion.
4. The system deletes selected logs and reports how many files were removed.
- Result: Log directory can be cleaned without manual file-system operations.

### UC-24: Reduce cognitive complexity in flagged functions
- Actor: Developer
- Trigger: Linting fails due to Complexipy cognitive-complexity violations.
- Main flow:
1. The developer runs linting and reviews Complexipy failed functions in descending severity.
2. The developer refactors flagged functions into smaller units while preserving behavior.
3. The developer validates the refactor with lint and tests.
- Result: The codebase remains behaviorally stable while meeting complexity gates.

### UC-25: Use current-task Makefile shortcuts
- Actor: Developer
- Trigger: The developer is already on a task branch and wants to run stage, commit, or PR workflow without passing `f=<TASK-ID>`.
- Main flow:
1. The developer runs a current-task shortcut Make target.
2. The target resolves the task file from the current branch naming convention.
3. The target executes stage, commit, or PR logic using metadata in that task file.
- Result: Task-driven workflow is faster while keeping task files as source of truth.

### UC-26: Import a Nordea bank CSV export
- Actor: User
- Preconditions: A CSV export from Nordea is placed in an import folder.
- Trigger: The user runs the import script.
- Main flow:
1. The script opens the CSV file and reads the header row.
2. The script identifies the Nordea format by matching the header fields `Bokföringsdag`, `Belopp`, and `Rubrik`.
3. The Nordea format package maps source columns to normalised transaction fields: date (`Bokföringsdag`), amount (`Belopp`), description (`Rubrik`), balance (`Saldo`).
4. The script normalises the date from `YYYY/MM/DD` to `YYYY-MM-DD`.
5. The script normalises amounts to US format (decimal point, no thousands separator) for Firefly API compatibility.
6. The script imports the transactions using the same flow as other supported formats.
- Result: Nordea transactions are imported into Firefly III on the same basis as SEB and ICA exports.

### UC-27: Bootstrap repository governance from shared .commons
- Actor: Developer
- Trigger: A new related project repository is initialized.
- Main flow:
1. The developer adds the shared `.commons` subtree to the new repository.
2. The developer generates `CLAUDE.md` and `.github/copilot-instructions.md` from shared templates.
3. The developer provides only project-context values (project purpose, requirements path, and optional project-specific make targets).
4. The generated files are committed as the repository governance baseline.
- Result: The new repository starts with the same governance rules and only project context differs.

### UC-28: Reuse CI policy through a thin project workflow wrapper
- Actor: Developer
- Trigger: A project needs CI that matches shared policy while allowing local context.
- Main flow:
1. The repository defines a local `.github/workflows/ci.yml` wrapper workflow.
2. The wrapper calls a shared reusable workflow from `.commons`-managed infrastructure.
3. The wrapper passes project-specific parameters (for example Python version and commands) without duplicating policy logic.
4. Pull requests to `main` execute the shared CI checks through the wrapper.
- Result: CI behavior remains consistent across projects while preserving per-project configuration.

### UC-29: Clear transactions for reimport
- Actor: User
- Trigger: The user runs the clear-transactions function and chooses either "all accounts" or provides a list of account names.
- Preconditions: Firefly URL and API token are configured.
- Main flow:
1. The script resolves the target account list (from cache or discovery) and matches it against the user's selection (all accounts, or the given list).
2. For each selected account, the script fetches all transaction IDs via `get_transactions_for_account`.
3. The script shows the total number of transactions that would be deleted, grouped by account, and requires the user to type "JA" to proceed.
4. If confirmed, the script deletes each transaction via `delete_transaction`.
5. The script logs the number of deleted transactions per account and in total.
- Alternative flow:
1. If the user does not confirm with "JA", the script aborts without deleting anything.
2. If `--dry-run` is provided, the script lists the transactions that would be deleted without requiring confirmation and without deleting anything.
- Result: Selected accounts' transactions are removed from Firefly, ready for reimport, without affecting accounts, budgets, or categories.

### UC-30: Automatically set opening balance from bank export on first import
- Actor: User
- Trigger: The user runs a normal import (UC-1/UC-2) for an account folder as usual.
- Preconditions: Firefly URL and API token are configured; the account's current opening balance (via `get_opening_balance`) is `0`; the bank format used for the account's CSV files defines a `balance_header` (SEB, ICA, and Nordea all do, via the "Saldo" column).
- Main flow:
1. Before importing any transactions for the account, the script determines the earliest-dated row across all of that account's CSV files.
2. The script sets the account's opening balance via `set_opening_balance(account_id, earliest_row_balance, earliest_row_date)`, using that row's "Saldo" value and date as-is.
3. The script excludes that earliest row from the transactions to be imported.
4. The script imports all remaining rows normally (UC-1), i.e. every row dated after the earliest one.
5. The script logs the opening balance and date that were set, and that the earliest row was used for this purpose and skipped as a transaction.
- Alternative flow:
1. If the account's current opening balance is not `0`, the script skips this step entirely and imports all rows as today, without excluding the earliest one.
2. If the bank format has no `balance_header` (no "Saldo" column available), the script logs a warning that opening balance could not be auto-detected and imports all rows normally, without excluding the earliest one.
3. If `--dry-run` is provided, the script logs the opening balance/date it *would* set and which row it would exclude, without calling `set_opening_balance` and without posting any transactions.
- Result: An account that starts at 0 automatically gets a correct opening balance and date derived from its own earliest bank export row, and the rest of that account's history imports normally on top of it — fully automatically, without manual saldo entry.

### UC-31: Detect and import transfers between accounts during multi-account import
- Actor: User
- Trigger: The user runs a multi-folder import (UC-2), importing two or more account folders in the same run.
- Preconditions: Firefly URL and API token are configured; at least two of the folders being imported map to distinct Firefly asset accounts.
- Main flow:
1. Before posting anything, the script collects all pending rows (date, description, amount, resolved bank format) from every folder in the batch, tagged with their resolved account.
2. The script identifies candidate pairs across *different* accounts where the amounts are equal in absolute value with opposite sign (one withdrawal-shaped, one deposit-shaped) and the dates differ by at most 3 days, regardless of bank format.
3. For a candidate pair whose dates are identical (0-day difference), the script applies amount-only matching: when a row has exactly one same-day candidate, it is paired directly; when a row has more than one same-day candidate, the script uses description overlap to disambiguate (a candidate whose description is a case-insensitive substring of the other's, in either direction, is preferred; if exactly one candidate has this overlap, that candidate is chosen).
4. For a candidate pair whose dates differ by 1–3 days, a match requires description overlap (as defined in step 3) regardless of how many same-amount candidates exist within the window — an amount-only match is never made across differing dates. If exactly one candidate within the window has description overlap, that candidate is chosen; if none or more than one do, the row is left unmatched.
5. Each resolved pair is posted as a single `transfer` transaction (`POST /api/v1/transactions`, `type: "transfer"`), with `source_id` = the account whose row was negative and `destination_id` = the account whose row was positive. Both rows are marked as consumed and are not posted again as withdrawal/deposit.
6. All unmatched or still-ambiguous rows are posted as withdrawal/deposit, exactly as today (UC-1).
7. The script logs how many transfers were detected and posted, plus the existing withdrawal/deposit/skip counts.
- Alternative flow:
1. If a row's matching resolves to no candidate (per steps 3–4), the script does not guess: it logs the ambiguity/no-match and posts the row as an ordinary withdrawal/deposit row.
2. If `--dry-run` is provided, the script logs which pairs it *would* post as transfers (and which rows remain ambiguous or unmatched) without posting anything.
3. If only one folder is being imported (UC-1, not UC-2), the script behaves exactly as today — no cross-account matching is attempted.
- Result: Transactions between the user's own accounts are recorded as `transfer` in Firefly III from the moment of import, instead of appearing as unrelated withdrawals and deposits — using a unified 0–3-day window regardless of bank, with same-day matches allowed on amount alone and 1–3-day matches requiring description overlap to avoid pairing coincidentally same-sized, unrelated transactions.

### UC-32: Show progress bar during transaction import
- Actor: User
- Trigger: The user runs an import (UC-1 single-folder or UC-2/multi-folder), with or without `--dry-run`.
- Preconditions: none beyond a normal import run.
- Main flow:
1. Before posting transactions for a run, the script determines the total number of rows to be processed: for a single folder, the pending rows for that account; for a multi-folder run, the total of transfer pairs plus unmatched rows across all folders.
2. The script displays a `tqdm` progress bar that advances once per row processed (whether posted live or logged as a dry-run preview), showing count and elapsed/estimated time.
3. The progress bar is written to the terminal (stderr) and does not interfere with the existing `INFO`-level log lines written to stdout and the log file.
4. On completion, the progress bar closes; existing summary log lines (`Summa: X ok, Y fel`, etc.) are unaffected.
- Result: The user sees live progress during long-running imports, in both dry-run and live mode, for both single- and multi-folder runs.

### UC-33: Import a single period across all accounts
- Actor: User
- Trigger: The user provides a `--period YYYY-MM` flag together with a base folder (UC-2, multiple account subfolders), or a single account folder (UC-1).
- Preconditions: The period matches the `YYYY-MM` format with a valid month (01-12).
- Main flow:
1. The script validates the `--period` value; an invalid format aborts the run with a clear error message before any account/API work happens.
2. For each account folder, the script restricts CSV file resolution to that folder's `<period>.csv` file only, instead of all `YYYY-MM.csv` files in the folder. Auto-split (UC-6) still runs first, so an unsplit export file is split into monthly files before the period filter is applied.
3. Folders without a matching `<period>.csv` file are skipped with the same warning as folders with no CSV files at all.
4. Import otherwise proceeds as in UC-2/UC-31 (multiple accounts, with cross-account transfer detection scoped to the selected period's rows only).
- Result: Only transactions from the selected month are imported, across every account in the same run, letting the user catch up month by month while transfer-matching still compares all accounts for that period.

### UC-34: Show account names in transaction log lines

- Actor: User
- Preconditions: None beyond a normal import run (UC-1, UC-2, or UC-3 dry run).
- Trigger: The script posts (or, under `--dry-run`, would post) a withdrawal/deposit or transfer transaction.
- Main flow:
1. For a withdrawal/deposit row, the script resolves the account's Firefly name from the discovered/cached account list and includes it in the log line instead of the numeric account ID.
2. For a transfer row (UC-31), the script resolves both the source and destination accounts' names and includes them in the log line as `<source name> -> <destination name>` instead of numeric account IDs.
3. If an account ID cannot be resolved to a name (e.g. a stale cache), the script falls back to logging the numeric ID so the line is still produced.
- Result: Every transaction log line names the account(s) involved, so the user can tell at a glance which account each posted (or dry-run) transaction belongs to, without cross-referencing account IDs.

### UC-35: Log total import duration

- Actor: User
- Preconditions: None; applies to every run of the script (UC-1, UC-2, UC-3 dry run, UC-33 period import).
- Trigger: The script reaches the end of a run, whether all transactions posted successfully or some rows/folders failed.
- Main flow:
1. The script records a start time as early as possible in `main()`, before token/URL loading and account discovery.
2. The script processes all folders as today (single-folder or multi-folder path).
3. Once all folders have been processed, the script computes the elapsed wall-clock duration since the recorded start time, and counts the total number of transactions attempted during the run (every withdrawal/deposit row and every transfer pair posted or attempted, across all folders, whether successful or failed).
4. The script logs the duration and, on the same or an immediately following log line, the average time per transaction (duration divided by the transaction count) as the last log lines of the run, after the existing "Klar!" message. If no transactions were attempted, the average-time line is omitted to avoid a division by zero.
- Result: The user can see how long the run took and how much time each transaction took on average, directly from the log output (terminal and log file) without needing an external timer, and these are always the final lines so they are easy to find.

## 5. Functional Requirements

### FR-1 Token loading
The script shall read the API token from secrets.json in the project root. If secrets.json does not exist, the script shall fall back to the legacy token file. If neither exists, the script shall trigger the interactive configuration flow (UC-12).

### FR-2 CLI usage
The script shall require at least one parameter (path). If missing, it shall print usage text and exit with an error code.

### FR-3 Path execution mode
If the provided path contains CSV files directly, the script shall treat it as a single account folder; otherwise, it shall treat it as a base directory containing account subfolders.

### FR-4 Account mapping
The script shall map folder names to Firefly account IDs using discovered/cached account metadata with case-insensitive substring matching. When multiple accounts match, the longest account name wins and the decision is logged.

### FR-5 CSV format detection
The script shall support:
- SEB format with headers Bokforingsdatum, Text, Belopp.
- ICA format with headers Datum, Text, Typ, Belopp.
- Nordea format with headers Bokföringsdag, Belopp, Rubrik.
Unknown format shall be logged as an error and the file shall not be imported.

### FR-6 Amount parsing and normalisation
The script shall parse Swedish amount variants, including:
- spaces as thousands separators
- comma decimals
- currency suffixes kr or sek (case-insensitive)

Parsed amounts shall be normalised to US format (decimal point, no thousands separator, e.g. `1 234,56` → `1234.56`) before being sent to the Firefly API.

### FR-7 Transaction type mapping
Negative amounts shall be created as withdrawal with source_id. Non-negative amounts shall be created as deposit with destination_id.

### FR-8 Currency
Created transactions shall use currency_code SEK.

### FR-9 Latest-date lookup
The script shall determine an account's latest withdrawal/deposit transaction date by calling client.get_transactions_by_type("withdrawal,deposit", start, end) (start="2000-01-01", end=today) and taking the maximum date among the returned transactions whose source_id or destination_id equals the account ID — since Firefly III's per-account endpoint (/api/v1/accounts/{id}/transactions) does not support filtering by transaction type (confirmed against a real instance: any type value is ignored). This excludes transfer transactions (UC-31/FR-66) from the duplicate-import floor, since transfers are not included in the "withdrawal,deposit" type list.

### FR-10 Ignore latest-date flag
The --ignore-latest-date-check flag shall disable latest-date filtering.

### FR-11 Dry-run mode
The --dry-run flag shall prevent transaction creation through the API and instead log planned transactions.

### FR-12 Automatic split
Before import, the script shall detect and split unsplit CSV files into YYYY-MM.csv files in the same directory.

### FR-13 Chronological sorting in split
Rows in each generated monthly file shall be sorted ascending by date.

### FR-14 Source file removal after split
The source file shall be removed after split files are created.

### FR-15 Parallelization
The script shall support parallel API calls using a thread pool of size MAX_WORKERS (current value: 5).

### FR-16 Logging
The script shall log to both stdout and file with timestamp, level, and message.

### FR-17 Result summary
After each CSV file, the script shall log successful imports, failed imports, and skipped rows.

### FR-18 Asset account discovery
The script shall be able to query Firefly for available asset accounts that are valid import targets.

### FR-19 Local account cache file
The script shall persist discovered accounts to a local cache file for reuse across runs.

### FR-20 Cache loading
At startup, the script shall load the local account cache file if present and valid.

### FR-21 Cache refresh mode
The script shall provide a way to refresh account metadata from Firefly and overwrite the local cache file.

### FR-22 Mapping from folder name to discovered accounts
The script shall resolve account IDs from folder names using discovered/cached account metadata rather than a hardcoded table.

### FR-23 Account cache schema
The cache shall include at least account ID, account name, account type, and fetch timestamp.

### FR-24 Discovery fallback behavior
If Firefly account discovery fails, the script shall fall back to the local cache when available.

### FR-25 No-cache failure behavior
If discovery fails and no valid cache exists, the script shall fail fast with a clear actionable error message.

### FR-26 Deterministic account resolution
If multiple discovered accounts match a folder name, the script shall use a deterministic tie-break strategy and log the decision.

### FR-27 Import folder creation
When account discovery runs (first run or --refresh-accounts), the script shall create import folders for each discovered account under the base directory.

### FR-28 Folder name sanitization
Derived folder names shall have Swedish characters (å, ä, ö) replaced with their ASCII equivalents (a, a, o), spaces replaced with underscores, and filesystem-invalid characters replaced with underscores.

### FR-29 Firefly URL from configuration file
The script shall read the Firefly base URL from config.json in the project root. If config.json does not exist or contains no URL, the script shall prompt the user interactively, validate the URL against the Firefly API, and save it to config.json.

### FR-30 API token from secrets file
The script shall read the API token from secrets.json in the project root. If secrets.json does not exist, the script shall fall back to the legacy token file. If neither exists, the script shall prompt the user interactively using hidden input and save the token to secrets.json.

### FR-31 --configure flag
The --configure flag shall force the interactive configuration flow for both URL and token, overwriting existing values in config.json and secrets.json.

### FR-32 Bank format packages
Bank-specific CSV recognition and field-mapping rules shall be implemented in separate packages/modules rather than hardcoded in the core importer module.

### FR-33 Header-based format resolution
Before splitting or importing a CSV file, the script shall read the header row and resolve the appropriate bank format package from the registered format packages.

### FR-34 Normalized field mapping
Each bank format package shall expose a mapping from source CSV columns to a normalized transaction model containing at least transaction date, description, amount, and any optional transaction-type field needed by the importer.

### FR-35 Shared importer contract for bank formats
The core importer shall consume bank format packages through a shared contract/interface so that split and import logic can operate on normalized fields instead of bank-specific column names.

### FR-36 Unsupported format handling in package architecture
If no bank format package matches a CSV header, the script shall log an unknown-format error and skip the file.

### FR-37 Log cleanup command
The system shall provide a log-cleanup operation that supports:
- deleting all import log files, or
- deleting import log files older than a user-provided retention period in days,
with explicit confirmation before destructive action.

### FR-51 Cognitive complexity lint gate
All functions under src/ shall satisfy the repository's Complexipy cognitive-complexity threshold enforced by make lint.

### FR-52 Current-task stage shortcut target
The Makefile shall provide a stage shortcut target that stages files from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-53 Current-task commit shortcut target
The Makefile shall provide a commit shortcut target that commits with the message from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-54 Current-task PR shortcut target
The Makefile shall provide a PR shortcut target that opens a pull request using title/body from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-61 Shared instruction templates
The repository governance files `CLAUDE.md` and `.github/copilot-instructions.md` shall be generated from shared templates managed in `.commons`, with project context as explicit input values.

### FR-62 Reusable CI invocation
The repository-level `.github/workflows/ci.yml` shall act as a thin wrapper that invokes a shared reusable CI workflow and forwards project-specific inputs.

### FR-63 CSV filename filter

When scanning an import folder for CSV files, the script shall recognize exactly two file types:

1. **Bank export file** — the filename (case-insensitive) contains the substring `konto` or `kontoutdrag`. These files are split into monthly files.
2. **Monthly file** — the filename matches the pattern `YYYY-MM.csv`. These files are imported directly.

A CSV file that matches neither pattern shall be logged as a warning (`WARNING: Okänd filtyp, hoppar över: <filename>`) and shall not be split or imported.

### FR-64 Clear-transactions command

The system shall provide a clear-transactions operation that accepts either "all accounts" or an explicit list of account names, fetches all transaction IDs for the selected accounts via the Firefly API, and deletes them individually. The operation shall require explicit user confirmation (typing "JA") before deleting, unless run with `--dry-run`, in which case it shall only list the transactions that would be deleted.

### FR-65 Automatic opening balance detection

Before importing transactions for an account whose current opening balance (via `get_opening_balance`) is `0`, the system shall determine the earliest-dated row across that account's CSV files and, if the bank format defines a `balance_header`, set the account's opening balance and opening balance date from that row's balance and date via `set_opening_balance`, then exclude that row from the transactions imported. If the current opening balance is not `0`, or the bank format has no `balance_header`, the system shall skip this step and import all rows unchanged. Under `--dry-run`, the system shall log the opening balance/date and excluded row it would use without calling `set_opening_balance` or posting transactions.

### FR-66 Cross-account transfer detection

When importing two or more account folders in the same run, the system shall collect all pending rows across those folders before posting any transaction, and identify candidate transfer pairs across different accounts by equal absolute amount with opposite sign and a date difference of at most `3` days, regardless of bank format. For a candidate pair with a `0`-day date difference, the system shall pair a row with its single same-day candidate directly, or — when multiple same-day candidates exist — prefer a candidate whose description is a case-insensitive substring of the other's (in either direction) if exactly one such candidate exists, and otherwise treat the row as unmatched. For a candidate pair with a `1`–`3`-day date difference, the system shall require description overlap (as defined above) to pair the row regardless of candidate count — an amount-only match shall never be made when dates differ — pairing only when exactly one candidate within the window has that overlap, and otherwise treating the row as unmatched. Each resolved pair shall be posted as a single `transfer` transaction (`source_id` = the negative-amount row's account, `destination_id` = the positive-amount row's account), and both rows shall be excluded from individual withdrawal/deposit posting. Unmatched or ambiguous rows shall be posted as withdrawal/deposit as today. Under `--dry-run`, the system shall log the pairs it would post as transfers and the rows left unmatched or ambiguous, without posting anything.

### FR-67 tqdm progress bar dependency

The system shall depend on `tqdm>=4.66` and wrap the transaction-posting loops in `process_csv` (single-folder path) and the multi-folder posting path (`_post_unmatched_rows`, transfer posting loop) with a `tqdm` progress bar advancing once per row processed, in both dry-run and live mode.

### FR-68 Period-scoped import

The script shall accept a `--period YYYY-MM` CLI flag. The system shall validate the value against the pattern `\d{4}-\d{2}` with a month component in `01`-`12`; an invalid value shall cause the script to print a clear error message and exit before any account or API work happens. When `--period` is provided, CSV file resolution for each account folder (both the single-folder path, UC-1, and the multi-folder path, UC-2) shall be restricted to that folder's `<period>.csv` file only, instead of all `YYYY-MM.csv` files matched by `MONTHLY_FILE_RE`. A folder with no `<period>.csv` file shall be skipped with the same warning used today for a folder with no CSV files at all. When `--period` is omitted, behavior is unchanged from today (all monthly files in each folder are processed).

### FR-69 Account-name transaction logging

The system shall resolve each transaction's account ID(s) to the corresponding Firefly account name (via the discovered/cached account list) before logging the result of posting (or, under `--dry-run`, the result it would post). For a withdrawal/deposit row, the log line shall be `[OK] [<account name>] [<transaction type>] <amount> SEK | <date> | <description>` (or `[DRY RUN]` in place of `[OK]` under dry-run). For a transfer row (FR-66), the log line shall be `[OK] [transfer] <amount> SEK | <date> | <source account name> -> <destination account name> | <description>` (or `[DRY RUN]` in place of `[OK]` under dry-run). If an account ID cannot be resolved to a name, the system shall fall back to logging the numeric ID for that account so the line is still produced. Since the script logs through the shared logging configuration (System Context), this account-name format shall appear identically in both the terminal output and the `import_YYYYMMDD_HHMMSS.log` file — there is no separate formatting path for the log file.

### FR-70 Import duration logging

The system shall record a monotonic start time at the beginning of `main()`, before token/URL loading and account discovery, and shall compute the elapsed wall-clock duration once all folders have been processed (regardless of whether individual rows or folders encountered errors). The system shall also count the total number of transactions attempted during the run (every withdrawal/deposit row and every transfer pair posted or attempted, across all folders, whether successful or failed). The system shall log the duration in `H:MM:SS` format (e.g. `0:05:12`), followed by the average time per transaction in seconds (duration in seconds divided by the transaction count, e.g. `0.42s/transaktion`), as the final log lines of the run, after the existing "Klar!" message. If the transaction count is `0`, the average-time line shall be omitted. These log lines shall appear in both the terminal output and the `import_YYYYMMDD_HHMMSS.log` file, per the shared logging configuration (System Context).

### FR-71 Shared service layer for import logic

Folder/account resolution, CSV parsing, duplicate-date filtering, opening-balance detection (UC-30), transfer detection (UC-31), period scoping (UC-33), account-name resolution (UC-34), and transaction posting shall live in a service layer with no dependency on stdout/print, argparse, process exit codes, or terminal-only libraries (e.g. `tqdm`). The service layer shall communicate progress and results only through return values and structured events (e.g. per-row/per-folder result objects), so any adapter (CLI or web) can consume them without depending on the other adapter's presentation concerns.

### FR-72 CLI is a thin adapter over the service layer

The CLI entry point (`main`, `_parse_cli_args`, and related argv/output handling in `import_firefly.py`) shall contain only CLI-specific concerns: argv parsing, rendering a `tqdm` progress bar, writing to stdout/the log file, and process exit codes. It shall delegate all import behavior to the shared service layer (FR-71) and shall not contain business logic (parsing rules, duplicate-date rules, opening-balance rules, transfer-matching rules) that an external consumer would otherwise need to duplicate.

### FR-73 Service layer packaged for external consumption

The service layer (FR-71) shall be importable as a Python library by an external application (e.g. a separate frontend project serving both this project and other Firefly-related tools) via a stable module path and function/class signatures, without this repository running its own HTTP server or web process. This repository's responsibility ends at exposing that importable interface; any HTTP API, web UI, background-job runner, or progress-streaming mechanism built on top of it is out of scope here and belongs to the consuming project.

## 6. Non-Functional Requirements

### NFR-1 Performance
The script shall reduce total import time compared to strictly sequential posting by using parallel API calls.

### NFR-2 Traceability
The script shall log all key steps so import flow and errors can be analyzed afterward.

### NFR-3 Robustness
If the latest transaction date cannot be retrieved, the script shall continue and log a warning.

### NFR-4 Data integrity
The script shall avoid unnecessary duplicate imports when latest-date filtering is enabled.

### NFR-5 Compatibility
The script shall run in a Python environment with requests installed.

### NFR-13 HTTP session layer

All HTTP communication with the Firefly III REST API (session management, credential
headers, account and transaction API calls, connection validation) shall be delegated
to the `firefly-python-api` library (bundled as a git subtree at
`libs/firefly-python-api/`). No inline `requests.Session` construction or direct
Firefly API calls shall exist in `import_firefly.py`, `web_ui.py`, or `config.py`.

### NFR-6 Startup efficiency
When a valid cache exists, account resolution should not require network calls during normal imports.

### NFR-7 Cache reliability
Cache reads and writes shall be atomic enough to avoid partial-file corruption during interrupted runs.

### NFR-8 Observability for discovery and cache
The script shall log whether account data came from live discovery or cache, including cache age.

### NFR-9 Extensibility of bank formats
Adding support for a new bank export format should require adding or registering a new format package with minimal or no changes to the core importer workflow.

### NFR-10 Maintainability via bounded complexity
The project shall keep function-level cognitive complexity bounded to preserve readability, ease of review, and safer incremental changes.

### NFR-11 CI pipeline
Every pull request against `main` shall automatically run lint, tests, and dependency audit via GitHub Actions. The pipeline shall fail if lint or tests fail, or if any dependency has a known CVE of severity moderate or higher.

### NFR-12 Governance consistency across related projects
Related projects that consume the same `.commons` baseline shall enforce equivalent workflow and instruction rules, differing only in declared project context.

## 7. Constraints and Assumptions
- CSV date formats vary by bank format package; each package is responsible for normalising dates to ISO 8601 (YYYY-MM-DD) before passing them to the importer.
- Firefly API is assumed to be reachable via FIREFLY_URL.
- The token file must exist and contain a valid Bearer token.
- Account identification is based on folder names and discovered/cached account metadata, not on CSV metadata.

## 8. Error Handling
- Unknown CSV format: log error and skip file.
- Missing account mapping: log warning and skip folder.
- No CSV files in folder: log warning and skip folder.
- API error during transaction creation: log error with status and truncated response text.
- Account discovery API failure: log warning/error, then fall back to cache if available.
- Invalid or corrupted cache file: log error and require refresh/discovery before import.
- **Path is a file (not a directory):** log error "Ange en mappsökväg, inte en fil." and exit with code 1.
- **Path does not exist:** create the directory (including parents) and continue normally.

## 9. Acceptance Criteria
- Running the script without a path shows usage and exits with error code.
- Running in dry-run mode creates no transactions but logs all candidates.
- Running with --ignore-latest-date-check imports older rows as well.
- The script splits unsplit CSV files to YYYY-MM.csv and removes the source file.
- The script imports both SEB and ICA formats.
- The script logs batch processing in sequential CSV order within each batch result.
- The script can fetch asset accounts from Firefly and store them in a local cache file.
- The script can import using cached account metadata without using a hardcoded account table.
- If discovery fails but cache exists, imports continue using cache and log the fallback.
- If discovery fails and no cache exists, the script exits with an actionable message.
- Running with --refresh-accounts creates import folders for all discovered accounts.
- Created folder names contain no spaces or Swedish characters.
- The system can clear old log files using explicit user confirmation.
- The system can clear transactions for all accounts or a chosen list of accounts using explicit user confirmation, with a dry-run preview available.

## 10. Implementation Status

This chapter tracks which requirements and use cases are implemented in the current codebase.

### Use Cases

| Use Case | Title | Status |
|---|---|---|
| UC-1 | Import a single account folder | Implemented |
| UC-2 | Import multiple account folders | Implemented |
| UC-3 | Dry run | Implemented |
| UC-4 | Prevent duplicate imports using latest date | Implemented |
| UC-5 | Force import of historical rows | Implemented |
| UC-6 | Automatically split an unsplit export file | Implemented |
| UC-7 | Parallel import with ordered logging | Implemented |
| UC-8 | Discover importable asset accounts from Firefly | Implemented |
| UC-9 | Reuse cached account list on later runs | Implemented |
| UC-10 | Fallback when Firefly account discovery is unavailable | Implemented |
| UC-11 | Automatic creation of import folders | Implemented |
| UC-12 | Configure Firefly connection on first run | Not implemented |
| UC-13 | Resolve a bank export format through a format package | Implemented |
| UC-14 | Add a new bank export format without changing the core importer | Implemented |
| UC-23 | Clear old import logs | Not implemented |
| UC-24 | Reduce cognitive complexity in flagged functions | Implemented |
| UC-25 | Use current-task Makefile shortcuts | Implemented |
| UC-29 | Clear transactions for reimport | Implemented |
| UC-30 | Automatically set opening balance from bank export on first import | Implemented |
| UC-31 | Detect and import transfers between accounts during multi-account import | Implemented |
| UC-32 | Show progress bar during transaction import | Implemented |
| UC-33 | Import a single period across all accounts | Implemented |
| UC-34 | Show account names in transaction log lines | Implemented |
| UC-35 | Log total import duration | Implemented |

### Functional Requirements

| Requirement | Title | Status |
|---|---|---|
| FR-1 | Token loading | Partial — reads from token file only, no secrets.json support yet |
| FR-2 | CLI usage | Implemented |
| FR-3 | Path execution mode | Implemented |
| FR-4 | Account mapping via discovered/cached data | Implemented |
| FR-5 | CSV format detection | Implemented |
| FR-6 | Amount parsing | Implemented |
| FR-7 | Transaction type mapping | Implemented |
| FR-8 | Currency | Implemented |
| FR-9 | Latest-date lookup | Implemented |
| FR-10 | Ignore latest-date flag | Implemented |
| FR-11 | Dry-run mode | Implemented |
| FR-12 | Automatic split | Implemented |
| FR-13 | Chronological sorting in split | Implemented |
| FR-14 | Source file removal after split | Implemented |
| FR-15 | Parallelization | Implemented |
| FR-16 | Logging | Implemented |
| FR-17 | Result summary | Implemented |
| FR-18 | Asset account discovery | Implemented |
| FR-19 | Local account cache file | Implemented |
| FR-20 | Cache loading | Implemented |
| FR-21 | Cache refresh mode | Implemented |
| FR-22 | Mapping from folder name to discovered accounts | Implemented |
| FR-23 | Account cache schema | Implemented |
| FR-24 | Discovery fallback behavior | Implemented |
| FR-25 | No-cache failure behavior | Implemented |
| FR-26 | Deterministic account resolution | Implemented |
| FR-27 | Import folder creation | Implemented |
| FR-28 | Folder name sanitization | Implemented |
| FR-29 | Firefly URL from configuration file | Not implemented |
| FR-30 | API token from secrets file | Not implemented |
| FR-31 | --configure flag | Not implemented |
| FR-32 | Bank format packages | Implemented |
| FR-33 | Header-based format resolution | Implemented |
| FR-34 | Normalized field mapping | Implemented |
| FR-35 | Shared importer contract for bank formats | Implemented |
| FR-36 | Unsupported format handling in package architecture | Implemented |
| FR-37 | Log cleanup command | Not implemented |
| FR-51 | Cognitive complexity lint gate | Implemented |
| FR-52 | Current-task stage shortcut target | Implemented |
| FR-53 | Current-task commit shortcut target | Implemented |
| FR-54 | Current-task PR shortcut target | Implemented |
| FR-64 | Clear-transactions command | Implemented |
| FR-65 | Automatic opening balance detection | Implemented |
| FR-66 | Cross-account transfer detection | Implemented |
| FR-67 | tqdm progress bar dependency | Implemented |
| FR-68 | Period-scoped import | Implemented |
| FR-69 | Account-name transaction logging | Implemented |
| FR-70 | Import duration logging | Implemented |
| FR-71 | Shared service layer for import logic | Not implemented (rebuild pending) |
| FR-72 | CLI is a thin adapter over the service layer | Not implemented (rebuild pending) |
| FR-73 | Service layer packaged for external consumption | Not implemented (rebuild pending) |

### Non-Functional Requirements

| Requirement | Title | Status |
|---|---|---|
| NFR-1 | Performance | Implemented |
| NFR-2 | Traceability | Implemented |
| NFR-3 | Robustness | Implemented |
| NFR-4 | Data integrity | Implemented |
| NFR-5 | Compatibility | Implemented |
| NFR-6 | Startup efficiency | Implemented |
| NFR-7 | Cache reliability | Partial — cache is written atomically by Path.write_text but no temp-file swap is used |
| NFR-8 | Observability for discovery and cache | Implemented |
| NFR-9 | Extensibility of bank formats | Implemented |
| NFR-10 | Maintainability via bounded complexity | Implemented |
| NFR-11 | CI pipeline | Not implemented |
