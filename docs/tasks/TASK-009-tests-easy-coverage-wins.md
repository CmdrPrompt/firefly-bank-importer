# TASK-009 Tests for easy coverage wins

## Status
done

## Description
Add tests for several small functions that are currently untested. None require HTTP
mocking — they only touch the filesystem (via `tmp_path`) or simple module-level
globals. Together these are expected to raise coverage from ~65% to ~74%.

Functions to cover:

- `save_account_cache` — writes a JSON cache file to disk
- `create_import_folders` — creates one folder per account under a base path
- `auto_split_folder` — detects non-`YYYY-MM.csv` files and delegates to `split_file_in_place`
- `split_file_in_place` empty-row branch — source file must **not** be deleted when
  the CSV contains a header but no data rows
- `create_transaction` with `BLOCK_TRANSACTION_POSTS=True` — must raise `RuntimeError`
- `create_transaction` with `log=True` (default) — must call `_log_tx_result` and
  return `(response, type, amount_abs)`

## Acceptance criteria
- [x] `save_account_cache`: file written with correct `accounts` list and `fetched_at` key
- [x] `create_import_folders`: creates one subfolder per account, logs count; no-op
      when folders already exist
- [x] `auto_split_folder`: calls `split_file_in_place` for non-monthly files only;
      leaves `YYYY-MM.csv` files untouched
- [x] `split_file_in_place` with only a header row: no output files created, source
      file not deleted
- [x] `create_transaction` with `BLOCK_TRANSACTION_POSTS=True`: raises `RuntimeError`
- [x] `create_transaction` with `log=True` and a successful mock response: returns
      tuple and logs OK line
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 16 characterisation tests covering all acceptance criteria. Coverage
rose from 65% to 73%.
**Files changed:**
- `tests/unit/test_coverage_wins.py` — created
- `docs/tasks/TASK-009-tests-easy-coverage-wins.md` — modified
**Stage:** `git add tests/unit/test_coverage_wins.py docs/tasks/TASK-009-tests-easy-coverage-wins.md`
**Commit:** `git commit -m "Add characterisation tests for easy coverage wins"`
