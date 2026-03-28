# TASK-010 Tests for process_folder

## Status
todo

## Description
Add characterisation tests for `process_folder`. The function ties together account
matching, auto-splitting, latest-date fetching, and per-CSV import. A mock
`requests.Session` is needed to avoid real API calls; `tmp_path` provides the
filesystem fixtures.

## Acceptance criteria
- [ ] No matching account in `account_map`: logs warning and returns without touching
      CSV files or calling the session
- [ ] Matching account but folder contains no CSV files: logs warning and returns
- [ ] `ignore_latest_date_check=True`: `get_latest_transaction_date` is **not** called,
      "Ignorerar senaste datum-kontroll" is logged
- [ ] `ignore_latest_date_check=False`, latest date returned by mock: `process_csv`
      called with that date
- [ ] `ignore_latest_date_check=False`, no previous transactions (mock returns `None`):
      "Ingen tidigare transaktion hittades" is logged
- [ ] Non-`YYYY-MM.csv` file in folder: `split_file_in_place` runs before `process_csv`
      (original file gone, split output processed)
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
**Files changed:**
**Stage:**
**Commit:**
