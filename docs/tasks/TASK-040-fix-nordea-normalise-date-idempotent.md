# TASK-040 Fix normalise_date crash on already-ISO dates in split Nordea files

## Status
done

## Description
After `split_file_in_place` runs, the output monthly files have dates in ISO 8601
format (`YYYY-MM-DD`). When `process_csv` subsequently reads those files and calls
`normalise_date` via `_collect_pending_rows`, it tries to parse the already-normalised
date string using the bank format's `date_format` (e.g. `%Y/%m/%d` for Nordea). This
causes a `ValueError` crash.

Example traceback:

```text
ValueError: time data '2025-01-01' does not match format '%Y/%m/%d'
```

The fix: make `normalise_date` idempotent. If parsing with `self.date_format` fails,
fall back to `%Y-%m-%d` (ISO). If the date is already ISO it is returned unchanged; if
it is in the bank's original format it is converted. Any other format still raises.

## Branch

**Branch name:** `task/040-fix-nordea-normalise-date-idempotent`
**Switch/create:** `git checkout -b task/040-fix-nordea-normalise-date-idempotent`
**Make target:** `make branch-task f=TASK-040`

## Acceptance criteria

- [x] `normalise_date` returns the correct ISO date when given Nordea's `YYYY/MM/DD` format.
- [x] `normalise_date` returns the correct ISO date when given an already-normalised `YYYY-MM-DD` date.
- [x] Running `uv run firefly-import <nordea-folder> --dry-run` does not crash on split Nordea files.
- [x] Existing tests pass without regressions.
- [x] New regression test added: `normalise_date` with already-ISO input returns the same date.
- [x] `make lint` and `make test` pass with coverage not lower than at task start.

## Completion

**Date:** 2026-03-30

**Summary:** Made `normalise_date` in `HeaderBankFormat` idempotent by adding an ISO 8601 fallback: if parsing with `self.date_format` raises `ValueError`, it retries with `%Y-%m-%d`. This fixes the crash when `process_csv` reads already-split Nordea files whose dates were normalised to ISO by `split_file_in_place`. Added 3 new tests (2 direct + 1 Hypothesis property test).

**Files changed:**

- `src/firefly_bank_importer/bank_formats/base.py` — modified (`normalise_date` ISO fallback)
- `tests/unit/test_nordea_format.py` — modified (3 new regression tests)
- `docs/tasks/TASK-040-fix-nordea-normalise-date-idempotent.md` — modified
- `CHANGELOG.md` — modified

**Branch:** `git checkout task/040-fix-nordea-normalise-date-idempotent`

**Stage:** `git add src/firefly_bank_importer/bank_formats/base.py tests/unit/test_nordea_format.py docs/tasks/TASK-040-fix-nordea-normalise-date-idempotent.md CHANGELOG.md`

**Commit:** `git commit -m "Fix normalise_date crash on already-ISO dates in split Nordea files"`
