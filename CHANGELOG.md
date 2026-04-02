# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Web UI folder selection test now exercises the happy path by mocking the account cache; unresolved-folder assertion tightened to verify exact CSS class and status text (TASK-043).

### Changed
- Removed unreachable `KeyError` from `except`-clauses in `config.py` — `json.loads()` never raises `KeyError` (TASK-030).
- Removed dead code `detect_csv_format()` and `_get_csv_indices()` from `import_firefly.py` — neither function was called (TASK-030).
- Removed silent `[:10]`-slice before `strptime` in `web_ui.py` — date strings are now parsed strictly as `YYYY-MM-DD` (TASK-030).
- Replaced misleading catch-all warning "Kunde inte läsa Firefly-inställningar" with separate, precise messages for missing URL and missing token in `web_ui.py` (TASK-030).
- Added `description_idx` bounds-check inside `_build_live_import_description` in `web_ui.py` to guard against out-of-bounds access if called outside its normal context (TASK-030).
- Documented the design decision that empty CSV files are warnings (non-blocking) while unknown formats are errors (blocking) in `web_ui.py` (TASK-030).

### Added
- Fixed `normalise_date` crash when importing already-split Nordea files: the method now falls back to ISO 8601 parsing if the bank-specific format does not match, making it idempotent for dates that were normalised during split (TASK-040).
- Added Nordea bank CSV format support: the importer now recognises Nordea exports (`Bokföringsdag`, `Belopp`, `Rubrik` headers), normalises `YYYY/MM/DD` dates to ISO 8601, and converts Swedish comma-decimal amounts to US format before sending to the Firefly API (TASK-039).
- Added a FastAPI-based web UI for import folder selection, including HTML and JSON endpoints for listing folders, CSV counts, detected formats, and date ranges (TASK-016).
- Added interactive account matching in the web UI with candidate lookup from the Firefly account cache and validation that blocks unresolved folders (TASK-017).
- Added dry-run preview endpoints and page showing per-folder and total candidate transactions, duplicate skips, date ranges, warnings, and blocking errors before live import (TASK-018).
- Added live-import job execution in the web UI with asynchronous start/status APIs, polling-based progress view, per-job event log, current folder/file context, and completion totals (TASK-019).
- Added web UI import history and per-run log details with endpoints (`/api/import-history`, `/api/import-history/{run_id}`) and pages (`/history`, `/history/{run_id}`), plus unit tests for list/details behavior (TASK-022).
- Added a CSV upload page and multipart API endpoint in the web UI for placing files in import folders with per-file validation and user-visible saved/rejected feedback (TASK-020).
- Added web UI account refresh via `POST /api/refresh-accounts` endpoint: triggers live account discovery from Firefly, updates the local cache, creates missing import folders, and returns a summary with total accounts, list of account names, and new folders created; `POST /refresh-accounts` renders an HTML result page listing all discovered account names and counts; index page button now navigates to this result page instead of displaying raw JSON (TASK-023).
- Added web UI settings endpoints (`GET /settings`, `POST /api/settings`) for reading and updating Firefly URL and API token with URL validation against the Firefly API and atomic persist to `config.json`/`secrets.json`; token value is never returned in responses (TASK-021).
- Added characterization tests for web UI upload, settings, and live-import error branches (TASK-025).
- Added Makefile shortcut targets for the active task branch: `stage-current-task`, `commit-current-task`, and `pr-current-task`, enabling task-file-driven stage/commit/PR flow without passing `f=<TASK-ID>` explicitly (TASK-027).

### Changed
- Increased web UI coverage from 73% to 90%, restoring `make test` to passing with 87% total project coverage (TASK-025).
- Reduced cognitive complexity in configuration and web UI flow by extracting smaller helper functions, moving route logic out of `create_app`, and refactoring dry-run/live-import processing so all functions pass Complexipy thresholds in `make lint` (TASK-026).

### Fixed
- Made optional bank-format column mapping robust when optional headers are configured but absent in CSV input, so `build_column_mapping` now returns `None` for missing optional indices instead of raising lookup errors.

## [0.1.2] - 2026-03-28

### Added
- Characterisation test suite covering date parsing, duplicate detection, CSV parsing,
  amount parsing, account matching, transaction payload building, log result handling,
  CLI argument parsing, account cache loading, CSV splitting, `process_csv`,
  `process_folder`, `build_account_map`, `save_account_cache`, `create_import_folders`,
  `auto_split_folder`, and `create_transaction` (220+ tests in total).
- `make stage`, `make stage-task`, and `make commit-task` Makefile targets to automate
  the task-driven commit workflow.

### Changed
- Minimum test coverage threshold raised to 80% (currently 85%).
- pre-commit ruff hook updated to v0.15.8 (matching local tooling) and switched to
  `--check` mode to prevent stash conflicts during commits.
- mypy configuration extended with module overrides for `pytest`, `hypothesis`, and
  `requests` stubs.

## [0.1.1] - 2026-03-27

### Added
- Dynamic asset account discovery from Firefly III via `GET /api/v1/accounts?type=asset` with pagination support.
- Local account cache file (`accounts_cache.json`) storing discovered account IDs, names, types, and fetch timestamp.
- `--refresh-accounts` CLI flag to force a fresh account fetch from Firefly and overwrite the local cache.
- Fallback to local cache when Firefly account discovery fails at runtime.
- Deterministic tie-break strategy when multiple accounts match a folder name (longest name wins), with log output when a tie-break occurs.
- Automatic creation of import folders (named `kontoutdrag_<account>`) when account discovery runs.

### Changed
- `ACCOUNT_MAP` hardcoded dictionary replaced by dynamic account resolution using discovered/cached Firefly data.
- `find_account_id` now accepts the resolved account map as a parameter instead of reading from a module-level constant.
- `process_folder` and `main` updated to pass the account map through the call chain.
- Usage message updated to include the new `--refresh-accounts` flag.
- Folder name sanitization now replaces Swedish characters (å→a, ä→a, ö→o), spaces, and filesystem-invalid characters with underscores.

## [0.1.0] - 2026-03-27

### Added
- Unified import script for Firefly III in import_firefly.py.
- Support for SEB CSV format via header detection.
- Support for ICA CSV format via header detection.
- Automatic CSV format detection with explicit handling for unknown headers.
- Account mapping from folder names to Firefly account IDs.
- Support for importing a single folder containing CSV files directly.
- Support for importing multiple account subfolders from a base directory.
- API token loading from local token file.
- Dry-run mode via --dry-run flag.
- Latest-date deduplication via Firefly account transactions endpoint.
- Override flag --ignore-latest-date-check to bypass deduplication filter.
- Amount normalization for Swedish numeric and currency variants.
- Transaction creation with deposit/withdrawal mapping based on amount sign.
- Currency assignment to SEK in outbound transactions.
- Timestamped logging to both console and log file.
- Per-file import summaries including success, error, and skipped counts.

### Changed
- Amount serialization standardized to decimal-dot output suitable for API payloads.
- Import flow updated to run automatic split before date-check and posting.
- Posting performance improved with parallel execution using ThreadPoolExecutor.
- Logging behavior adjusted to preserve sequential output order while using parallel posting.

### Fixed
- Latest imported transaction date extraction aligned with Firefly response path attributes.transactions[0].date.
- Restored stable script structure after earlier regression in main/date-check integration.
