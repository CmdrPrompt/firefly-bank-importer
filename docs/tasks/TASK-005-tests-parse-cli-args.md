# TASK-005 Tests for _parse_cli_args

## Status
done

## Description
Add characterisation tests for `_parse_cli_args`. It is a pure function over
`argv: list[str]` with no side effects.

The function extracts a positional folder path and three boolean flags
(`--dry-run`, `--ignore-latest-date-check`, `--refresh-accounts`) from an argv list,
and raises `ValueError` if the argv is too short or the path is missing.

## Acceptance criteria
- [x] Tests for valid input: folder path only, path + each flag individually,
      path + all flags combined, flags before or after the path
- [x] Tests for invalid input: empty argv → ValueError, only flags and no path → ValueError
- [x] Parametrized test covering all flag combinations (8 combinations)
- [x] Hypothesis test: any argv containing a non-flag string at position ≥ 1 extracts
      correct folder and flags
- [x] Tests pass with `make test`

## Completion
**Date:** 2026-03-28
**Summary:** 20 characterisation tests in tests/unit/test_cli_args.py. Covers folder-only,
each flag individually, all flags combined, flags before/after path, all 8 flag combinations
via parametrize, invalid inputs (empty argv, prog-only, flags-only), and 2 Hypothesis
invariants (folder always extracted, dry-run flag always detected). All 20 tests pass.
**Files changed:**
- `tests/unit/test_cli_args.py` — created
**Stage:** `git add tests/unit/test_cli_args.py docs/tasks/TASK-005-tests-parse-cli-args.md`
**Commit:** `git commit -m "Add characterisation tests for _parse_cli_args"`
