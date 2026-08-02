# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- CSV files in import folders are now filtered by filename: files containing `konto` or `kontoutdrag` (case-insensitive) are split into monthly files; `YYYY-MM.csv` files are imported directly; any other `.csv` file triggers a warning and is skipped (TASK-049).
- Import now only processes `YYYY-MM.csv` monthly files; leftover non-monthly CSV files that were not split are no longer imported (TASK-050).
- Web UI upload rejects files whose name does not contain `konto` or `kontoutdrag`, and the upload form now shows the naming convention (TASK-050).
- CLI usage message describes the two supported file types: kontoutdrag-fil and YYYY-MM.csv månadsfil (TASK-050).
- GitHub Actions CI pipeline: lint, test, and `pip-audit` dependency audit run automatically on every PR to main (TASK-044).
- Added shared `.commons` governance templates for `CLAUDE.md` and `.github/copilot-instructions.md`, plus a reproducible `make generate-governance-files` workflow that regenerates local project files with source-template headers (TASK-045).
- New `firefly-clear-transactions` command deletes transactions for all accounts or a chosen list of account names, to support reimporting from scratch. Shows a per-account/total count before acting, requires typing "JA" to confirm, and supports `--dry-run` to preview without deleting or prompting (TASK-051).
- Import now automatically sets an account's opening balance and opening balance date from the earliest row of its bank export CSVs, whenever the account's current opening balance is `0`. That earliest row is excluded from the imported transactions; all later rows import as before. Accounts with a non-zero opening balance, or bank formats without a balance column, are unaffected. `--dry-run` logs the balance/date and excluded row it would set without applying anything (TASK-053).
- When importing two or more account folders in the same run, matching withdrawal/deposit rows between the user's own accounts are now posted as a single `transfer` transaction instead of two unrelated withdrawal/deposit transactions. Rows are paired by equal-and-opposite amount, same-day for accounts at the same bank or up to 2 days apart across banks, with description overlap used to disambiguate multiple candidates; rows left ambiguous or unmatched import exactly as before. Single-folder imports are unaffected. `--dry-run` logs the transfer pairs it would post without posting anything (TASK-054).
- Import now shows a `tqdm` progress bar while posting transactions, in both dry-run and live mode, for single-folder and multi-folder runs (TASK-055).
- Widened the cross-account transfer matching window (TASK-054) to a unified 0–3 days regardless of bank, replacing the previous same-bank-only-same-day / cross-bank-2-day rule. Same-day matches still work on amount alone; matches 1–3 days apart now require the two rows' descriptions to overlap (case-insensitive substring), so unrelated transactions that coincidentally share an amount are no longer paired just because they're the only same-amount candidate within the window (TASK-056).
- New `--period YYYY-MM` flag imports a single month's `YYYY-MM.csv` file across all account folders in one run, instead of every monthly file in each folder. Cross-account transfer detection still runs, scoped to that month's rows. Folders without a matching file for the period are skipped like today's "no CSV files" case (TASK-058).
- Transaction log lines now show the Firefly account name instead of its numeric ID, for both withdrawal/deposit rows (`[OK]/[DRY RUN] [<account name>] [<type>] ...`) and cross-account transfers (`... | <source name> -> <destination name> | ...`), falling back to the numeric ID if a name can't be resolved. The same format appears in both the terminal and the log file (TASK-059).
- Every import run now logs the total elapsed time (`H:MM:SS`) and the average time per transaction (in seconds) as the final lines of the run, after "Klar!"; the average line is omitted when no transactions were attempted (TASK-059).
- Cross-account transfer matching and structured result/event types (`TransactionResult`, `FolderResult`, `ProgressEvent`) now live in a new `firefly_bank_importer.service` module with no dependency on `tqdm`, `argparse`, or stdout, so external applications can import the matching logic without pulling in CLI-only concerns (TASK-066).
- Transaction posting, opening-balance detection, and cross-account transfer posting now return structured result objects instead of calling `logging.info/error` or taking a `tqdm` progress bar directly, so an external application can drive these functions with its own progress/output handling. The CLI's terminal and log output (line format, account names, counts, `[FEL]` on error, elapsed time) is unchanged; hitting the dry-run-protection guard during a live posting now also produces an `[FEL]` line and continues the run for transfers, matching the existing behavior for regular transactions instead of crashing mid-import (TASK-067).

### Fixed

- Upgraded `click`, `idna`, `pytest`, `starlette`, and `urllib3` in `uv.lock` past 14 known CVEs `pip-audit` flagged, so CI's Audit step now passes cleanly with zero reported vulnerabilities (TASK-062).
- Added `pip-audit` to the `dev` extra in `pyproject.toml`, fixing CI's Audit step, which previously failed with `Failed to spawn: pip-audit ... No such file or directory` because the tool was never installed by `uv sync --extra dev` (TASK-061).
- CI's `ci.yml` now calls the reusable workflow at `CmdrPrompt/python-butler` instead of the renamed `python-commons`, fixing an intermittent "Invalid workflow file ... workflow was not found" failure caused by GitHub Actions not reliably resolving `uses:` references across a repo rename (TASK-060).
- The duplicate-import check no longer treats a cross-account transfer transaction as the account's latest transaction. Previously, once a transfer (UC-31, TASK-054/056) had been posted with a date later than other not-yet-imported withdrawal/deposit rows on the same account, the duplicate-import check would incorrectly skip all of those earlier rows on the next run. The latest-date lookup now excludes transfers, comparing only against the account's latest withdrawal/deposit transaction (TASK-057).
- Restored `pyproject.toml` dependencies, CLI entry points, `[tool.uv.sources]`, mypy overrides, coverage config, and `tool.ruff.line-length` (120) that were accidentally dropped when `.butler` was integrated as a submodule, and fixed the resulting TOML syntax error that broke `uv`/`make install`/`make branch-task` (TASK-052).
- Web UI folder selection test now exercises the happy path by mocking the account cache; unresolved-folder assertion tightened to verify exact CSS class and status text (TASK-043).

### Changed

- All Firefly III HTTP calls (`session management`, `get_asset_accounts`, `get_latest_transaction_date`, `create_transaction`, `validate_connection`) are now delegated to the `firefly-python-api` library, bundled as a git subtree at `libs/firefly-python-api/`. Inline `requests.Session` construction removed from `import_firefly.py`, `web_ui.py`, and `config.py` (TASK-046).
- Removed unreachable `KeyError` from `except`-clauses in `config.py` — `json.loads()` never raises `KeyError` (TASK-030).
- Removed dead code `detect_csv_format()` and `_get_csv_indices()` from `import_firefly.py` — neither function was called (TASK-030).
- Removed silent `[:10]`-slice before `strptime` in `web_ui.py` — date strings are now parsed strictly as `YYYY-MM-DD` (TASK-030).
- Replaced misleading catch-all warning "Kunde inte läsa Firefly-inställningar" with separate, precise messages for missing URL and missing token in `web_ui.py` (TASK-030).
- Added `description_idx` bounds-check inside `_build_live_import_description` in `web_ui.py` to guard against out-of-bounds access if called outside its normal context (TASK-030).
- Documented the design decision that empty CSV files are warnings (non-blocking) while unknown formats are errors (blocking) in `web_ui.py` (TASK-030).

### Removed

- The local FastAPI/Jinja2/HTMX web UI (`web_ui.py` and its test suite) has been removed from this repository, along with the `firefly-import-web` console script, the `fastapi`/`uvicorn`/`python-multipart`/`httpx` dependencies, and the `make web` target. The web frontend is being rebuilt as a standalone application in a separate repository, consuming this project's import logic as an importable service layer instead of a locally-hosted HTTP UI (TASK-064).
- README and the NFR-13 HTTP session layer requirement no longer reference the removed `web_ui.py` module or `uv run firefly-web`; README now describes this repository as CLI-only, and its supported-CSV-formats table now lists Nordea alongside SEB and ICA (TASK-065).

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
