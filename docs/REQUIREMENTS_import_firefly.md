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
Unknown format shall be logged as an error and the file shall not be imported.

### FR-6 Amount parsing
The script shall parse Swedish amount variants, including:
- spaces as thousands separators
- comma decimals
- currency suffixes kr or sek (case-insensitive)

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

### NFR-6 Startup efficiency
When a valid cache exists, account resolution should not require network calls during normal imports.

### NFR-7 Cache reliability
Cache reads and writes shall be atomic enough to avoid partial-file corruption during interrupted runs.

### NFR-8 Observability for discovery and cache
The script shall log whether account data came from live discovery or cache, including cache age.

### NFR-9 Extensibility of bank formats
Adding support for a new bank export format should require adding or registering a new format package with minimal or no changes to the core importer workflow.

## 7. Constraints and Assumptions
- CSV dates are assumed to be in YYYY-MM-DD format.
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
