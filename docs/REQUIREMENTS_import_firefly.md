# Requirements Specification: import_firefly.py

## 1. Purpose and Scope
This document defines the requirements and use cases for the current implementation of import_firefly.py (version 1.0.0) and the planned changes tracked under [Unreleased].

The script is intended to import bank transactions from CSV files (SEB and ICA formats) into Firefly III through its API.

## 2. Goals
- Import transactions from one or more account folders.
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
1. The script fetches the latest transaction date for the account from Firefly.
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

### UC-18: Preview dry-run import in web UI
- Actor: User
- Preconditions: One or more import folders are selected and mapped to Firefly accounts in the web UI.
- Trigger: The user requests a dry-run preview before live import.
- Main flow:
1. The web UI validates that each selected folder has a resolved destination account.
2. The system parses files in selected folders using the existing format resolution and duplicate-date rules.
3. The system computes a preview summary per folder and total, including candidate transactions, skipped duplicates, date range, and parsing warnings/errors.
4. The web UI shows the summary and blocks live import when unresolved errors exist.
- Result: The user can verify what would be imported before executing live import.

### UC-19: Run live import with progress in web UI
- Actor: User
- Preconditions: Dry-run preview is completed and contains no blocking errors.
- Trigger: The user starts live import from the web UI.
- Main flow:
1. The web UI starts an asynchronous live-import job for selected folders and mappings.
2. The backend processes files and transactions while emitting incremental progress updates.
3. The web UI receives and renders progress updates in near real time.
4. When the job finishes, the web UI shows a completion summary with imported, skipped, and failed counts.
- Result: The user can monitor live import execution and outcome without terminal access.

### UC-20: Show import history and logs in web UI
- Actor: User
- Trigger: The user opens the web UI to review prior imports.
- Main flow:
1. The web UI requests a list of prior import runs.
2. The backend returns entries with status and timestamp.
3. The user selects one run to inspect details.
4. The backend returns detailed log lines for that run.
5. The web UI renders the detailed logs for troubleshooting.
- Result: The user can audit and troubleshoot previous imports without manual file access.

### UC-23: Clear old import logs
- Actor: User
- Trigger: The user chooses to clear logs from CLI or web UI.
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
- Trigger: The user runs the import script or triggers import from the web UI.
- Main flow:
1. The script opens the CSV file and reads the header row.
2. The script identifies the Nordea format by matching the header fields `Bokföringsdag`, `Belopp`, and `Rubrik`.
3. The Nordea format package maps source columns to normalised transaction fields: date (`Bokföringsdag`), amount (`Belopp`), description (`Rubrik`), balance (`Saldo`).
4. The script normalises the date from `YYYY/MM/DD` to `YYYY-MM-DD`.
5. The script normalises amounts to US format (decimal point, no thousands separator) for Firefly API compatibility.
6. The script imports the transactions using the same flow as other supported formats.
- Result: Nordea transactions are imported into Firefly III on the same basis as SEB and ICA exports.

### UC-15: Configure Firefly URL and token in web UI settings
- Actor: User
- Preconditions: The web UI is running and the settings page is accessible.
- Trigger: The user opens the settings page and submits Firefly URL and API token.
- Main flow:
1. The web UI shows the current configured Firefly URL and indicates whether a token is already stored.
2. The user enters or updates the Firefly URL and API token.
3. The backend validates the URL by calling Firefly /api/v1/about.
4. If validation succeeds, the backend persists URL to config.json and token to secrets.json.
5. The web UI returns a success response.
- Alternative flow:
1. If URL validation fails, no values are persisted.
2. The web UI returns a clear validation error message.
- Result: Firefly connection settings are managed from the web UI with validation and persistence.

### UC-21: Trigger account refresh from web UI
- Actor: User
- Trigger: The user clicks "Refresh accounts" in the web UI.
- Main flow:
1. The web UI sends a POST request to `/refresh-accounts`.
2. The backend calls Firefly to fetch all asset accounts and rebuilds the local cache.
3. The backend creates any new import folders for newly discovered accounts.
4. The backend returns a result page showing: total accounts found, list of all account names, new folders created, any errors.
5. The user sees which accounts are available and how many folders were created.
- Result: Account cache and import folders are updated; the user sees the full list of discovered accounts.

### UC-22: Upload CSV files in web UI
- Actor: User
- Preconditions: The web UI is running and at least one import folder exists.
- Trigger: The user uploads one or more CSV files via the web UI.
- Main flow:
1. The user selects target import folder and one or more CSV files.
2. The system validates file type and supported bank format via CSV headers.
3. The system stores valid files in the selected import folder.
4. The system reports per-file result (saved/rejected) with reason.
- Result: Valid CSV files are placed in import folders without manual filesystem operations.

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
The script shall fetch the latest transaction date per account from /api/v1/accounts/{id}/transactions with limit=1.

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

### FR-38 Web UI dry-run preview API
The system shall provide a web API endpoint that returns a dry-run preview summary for selected folders and account mappings without creating transactions in Firefly.

### FR-39 Web UI preview content
The dry-run preview response and UI shall include, at minimum, per-folder and total counts for candidate transactions, duplicate-skipped rows, date range, and parsing/validation warnings.

### FR-40 Live-import guard from preview
The web UI shall prevent continuing to live import when dry-run preview reports unresolved mapping errors or fatal parsing/validation errors.

### FR-41 Web UI live import job start
The system shall provide an API endpoint that starts a live-import job asynchronously for selected folders and resolved account mappings.

### FR-42 Web UI live progress stream
The system shall provide progress updates for running live-import jobs, including job state, current folder/file context, and cumulative imported/skipped/failed counts.

### FR-43 Web UI live import completion summary
When a live-import job completes, the system shall expose a completion summary containing imported, skipped, and failed totals and any terminal errors.

### FR-44 Web UI upload endpoint
The system shall provide a web API endpoint that accepts CSV file uploads and a target import folder.

### FR-45 Web UI upload validation
The upload flow shall validate that uploaded files are CSV and that headers match a supported bank format before saving files.

### FR-46 Web UI upload result feedback
The upload flow shall return user-visible per-file feedback containing filename, save status, and rejection reason when validation fails.

### FR-47 Web UI settings read
The web UI settings endpoint (GET /settings) shall return the current Firefly URL from config.json and indicate whether an API token is stored in secrets.json, without returning the token value.

### FR-48 Web UI settings save
The web UI settings save endpoint (POST /api/settings) shall accept Firefly URL and API token, validate the URL against Firefly /api/v1/about, and persist URL to config.json plus token to secrets.json only on successful validation.

### FR-49 Web UI settings validation failure
If URL validation fails in the settings save flow, the system shall not modify config.json or secrets.json and shall return an actionable error message.

### FR-50 Web UI settings update
The settings save flow shall support both first-time setup and updates to existing values; existing URL and token shall be replaced on successful validation.

### FR-51 Cognitive complexity lint gate
All functions under src/ shall satisfy the repository's Complexipy cognitive-complexity threshold enforced by make lint.

### FR-52 Current-task stage shortcut target
The Makefile shall provide a stage shortcut target that stages files from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-53 Current-task commit shortcut target
The Makefile shall provide a commit shortcut target that commits with the message from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-54 Current-task PR shortcut target
The Makefile shall provide a PR shortcut target that opens a pull request using title/body from the task file inferred from the current task branch, without requiring `f=<TASK-ID>`.

### FR-55 Web UI import history list API
The system shall provide an API endpoint that returns prior import runs with at least run identifier, status, timestamp, and source log filename.

### FR-56 Web UI import history page
The system shall provide a web UI page that lists prior import runs with status and timestamp and links each run to a details view.

### FR-57 Web UI per-run log details
The system shall provide an API endpoint and corresponding web UI page to show detailed log lines for a selected import run.

### FR-58 Web UI refresh-accounts endpoint
The system shall provide a POST `/api/refresh-accounts` endpoint that triggers live account discovery from Firefly, updates the local cache, creates missing import folders, and returns a JSON summary with total accounts found, list of discovered account names, and new folders created.

### FR-59 Web UI refresh-accounts action
The web UI index page shall expose a "Refresh accounts" button that POSTs to `/refresh-accounts`.

### FR-60 Web UI refresh-accounts result page
The system shall provide a POST `/refresh-accounts` HTML endpoint that performs account refresh and renders a result page showing total accounts found, each discovered account name, new folders created count, and a link back to the index.

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
| UC-18 | Preview dry-run import in web UI | Not implemented |
| UC-19 | Run live import with progress in web UI | Not implemented |
| UC-20 | Show import history and logs in web UI | Implemented |
| UC-21 | Trigger account refresh from web UI | Implemented |
| UC-22 | Upload CSV files in web UI | Not implemented |
| UC-23 | Clear old import logs | Not implemented |
| UC-24 | Reduce cognitive complexity in flagged functions | Implemented |
| UC-25 | Use current-task Makefile shortcuts | Implemented |
| UC-24 | Reduce cognitive complexity in flagged functions | Implemented |
| UC-29 | Clear transactions for reimport | Not implemented |

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
| FR-38 | Web UI dry-run preview API | Not implemented |
| FR-39 | Web UI preview content | Not implemented |
| FR-40 | Live-import guard from preview | Not implemented |
| FR-41 | Web UI live import job start | Not implemented |
| FR-42 | Web UI live progress stream | Not implemented |
| FR-43 | Web UI live import completion summary | Not implemented |
| FR-44 | Web UI upload endpoint | Not implemented |
| FR-45 | Web UI upload validation | Not implemented |
| FR-46 | Web UI upload result feedback | Not implemented |
| FR-51 | Cognitive complexity lint gate | Implemented |
| FR-52 | Current-task stage shortcut target | Implemented |
| FR-53 | Current-task commit shortcut target | Implemented |
| FR-54 | Current-task PR shortcut target | Implemented |
| FR-55 | Web UI import history list API | Implemented |
| FR-56 | Web UI import history page | Implemented |
| FR-57 | Web UI per-run log details | Implemented |
| FR-58 | Web UI refresh-accounts endpoint | Implemented |
| FR-59 | Web UI refresh-accounts action | Implemented |
| FR-60 | Web UI refresh-accounts result page | Implemented |
| FR-64 | Clear-transactions command | Not implemented |

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
