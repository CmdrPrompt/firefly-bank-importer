# TASK-008 Tests for process_csv

## Status
done

## Description
Add characterisation tests for `process_csv`. Uses `tmp_path` for CSV files and
`unittest.mock` for the HTTP session so no real API calls are made.

`process_csv` orchestrates: format detection, index resolution, row collection with
deduplication, and either dry-run logging or threaded import via `_run_threaded_import`.

## Acceptance criteria
- [x] SEB CSV file + dry_run=True: correct transactions logged, no POST calls made
- [x] ICA CSV file + dry_run=True: type column appended to description, no POST calls
- [x] Unknown-format CSV: logs error and returns without calling session.post
- [x] latest_date set: rows on or before the date are skipped, skipped count logged
- [x] latest_date=None: all rows included
- [x] dry_run=False: session.post called once per pending transaction
- [x] skipped > 0: "Hoppade over" log line emitted
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 14 characterisation tests covering all acceptance criteria. Mocks
`requests.Session` to avoid real HTTP calls; uses `autouse` fixture to keep
`BLOCK_TRANSACTION_POSTS` False during all tests.
**Files changed:**
- `tests/unit/test_process_csv.py` — created
- `docs/tasks/TASK-008-tests-process-csv.md` — modified
**Stage:** `git add tests/unit/test_process_csv.py docs/tasks/TASK-008-tests-process-csv.md`
**Commit:** `git commit -m "Add characterisation tests for process_csv"`
