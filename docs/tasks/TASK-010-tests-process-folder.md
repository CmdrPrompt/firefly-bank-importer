# TASK-010 Tests for process_folder

## Status
done

## Description
Add characterisation tests for `process_folder`. The function ties together account
matching, auto-splitting, latest-date fetching, and per-CSV import. A mock
`requests.Session` is needed to avoid real API calls; `tmp_path` provides the
filesystem fixtures.

## Acceptance criteria
- [x] No matching account in `account_map`: logs warning and returns without touching
      CSV files or calling the session
- [x] Matching account but folder contains no CSV files: logs warning and returns
- [x] `ignore_latest_date_check=True`: `get_latest_transaction_date` is **not** called,
      "Ignorerar senaste datum-kontroll" is logged
- [x] `ignore_latest_date_check=False`, latest date returned by mock: `process_csv`
      called with that date
- [x] `ignore_latest_date_check=False`, no previous transactions (mock returns `None`):
      "Ingen tidigare transaktion hittades" is logged
- [x] Non-`YYYY-MM.csv` file in folder: `split_file_in_place` runs before `process_csv`
      (original file gone, split output processed)
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 10 characterisation tests covering all acceptance criteria. Monkeypatches
`get_latest_transaction_date` to avoid HTTP calls. Coverage rose to 79%.
**Files changed:**
- `tests/unit/test_process_folder.py` — created
- `docs/tasks/TASK-010-tests-process-folder.md` — modified
**Stage:** `git add tests/unit/test_process_folder.py docs/tasks/TASK-010-tests-process-folder.md`
**Commit:** `git commit -m "Add characterisation tests for process_folder"`
