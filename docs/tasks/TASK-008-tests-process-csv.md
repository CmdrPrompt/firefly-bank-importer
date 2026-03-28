# TASK-008 Tests for process_csv

## Status
todo

## Description
Add characterisation tests for `process_csv`. Uses `tmp_path` for CSV files and
`unittest.mock` for the HTTP session so no real API calls are made.

`process_csv` orchestrates: format detection, index resolution, row collection with
deduplication, and either dry-run logging or threaded import via `_run_threaded_import`.

## Acceptance criteria
- [ ] SEB CSV file + dry_run=True: correct transactions logged, no POST calls made
- [ ] ICA CSV file + dry_run=True: type column appended to description, no POST calls
- [ ] Unknown-format CSV: logs error and returns without calling session.post
- [ ] latest_date set: rows on or before the date are skipped, skipped count logged
- [ ] latest_date=None: all rows included
- [ ] dry_run=False: session.post called once per pending transaction
- [ ] skipped > 0: "Hoppade over" log line emitted
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
