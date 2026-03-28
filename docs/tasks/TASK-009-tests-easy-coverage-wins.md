# TASK-009 Tests for easy coverage wins

## Status
todo

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
- [ ] `save_account_cache`: file written with correct `accounts` list and `fetched_at` key
- [ ] `create_import_folders`: creates one subfolder per account, logs count; no-op
      when folders already exist
- [ ] `auto_split_folder`: calls `split_file_in_place` for non-monthly files only;
      leaves `YYYY-MM.csv` files untouched
- [ ] `split_file_in_place` with only a header row: no output files created, source
      file not deleted
- [ ] `create_transaction` with `BLOCK_TRANSACTION_POSTS=True`: raises `RuntimeError`
- [ ] `create_transaction` with `log=True` and a successful mock response: returns
      tuple and logs OK line
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
**Files changed:**
**Stage:**
**Commit:**
