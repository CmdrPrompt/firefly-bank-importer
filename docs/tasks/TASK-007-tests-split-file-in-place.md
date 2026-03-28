# TASK-007 Tests for split_file_in_place

## Status
done

## Description
Add characterisation tests for `split_file_in_place`. Uses `tmp_path` to create real
CSV files on disk without touching the actual bankImports directory.

The function reads an unsplit multi-month CSV export, groups rows by year-month,
normalises amount/balance values to decimal-dot format, sorts each month's rows
chronologically, writes one `YYYY-MM.csv` per month, and removes the source file.

## Acceptance criteria
- [x] SEB multi-month file: correct YYYY-MM.csv files created, rows sorted by date,
      original file deleted
- [x] ICA multi-month file: same as above using Datum column
- [x] Single-month file: one output file created, original deleted
- [x] Amount normalisation: comma-decimal amounts converted to dot-decimal in output
- [x] Saldo normalisation: if Saldo column present, values also normalised
- [x] Unknown format: no output files created, source file untouched, warning logged
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 15 characterisation tests covering all acceptance criteria. Helper
functions for writing and reading CSV files in tmp_path keep test code concise.
**Files changed:**
- `tests/unit/test_split_file_in_place.py` — created
- `docs/tasks/TASK-007-tests-split-file-in-place.md` — modified
**Stage:** `git add tests/unit/test_split_file_in_place.py docs/tasks/TASK-007-tests-split-file-in-place.md`
**Commit:** `git commit -m "Add characterisation tests for split_file_in_place"`
