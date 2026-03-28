# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
