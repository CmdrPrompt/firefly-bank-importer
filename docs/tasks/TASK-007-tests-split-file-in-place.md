# TASK-007 Tests for split_file_in_place

## Status
todo

## Description
Add characterisation tests for `split_file_in_place`. Uses `tmp_path` to create real
CSV files on disk without touching the actual bankImports directory.

The function reads an unsplit multi-month CSV export, groups rows by year-month,
normalises amount/balance values to decimal-dot format, sorts each month's rows
chronologically, writes one `YYYY-MM.csv` per month, and removes the source file.

## Acceptance criteria
- [ ] SEB multi-month file: correct YYYY-MM.csv files created, rows sorted by date,
      original file deleted
- [ ] ICA multi-month file: same as above using Datum column
- [ ] Single-month file: one output file created, original deleted
- [ ] Amount normalisation: comma-decimal amounts converted to dot-decimal in output
- [ ] Saldo normalisation: if Saldo column present, values also normalised
- [ ] Unknown format: no output files created, source file untouched, warning logged
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
