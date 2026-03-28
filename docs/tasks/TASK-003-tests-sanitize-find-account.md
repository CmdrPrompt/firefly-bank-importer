# TASK-003 Tests for sanitize_folder_name and find_account_id

## Status
done

## Description
Add characterisation tests for `sanitize_folder_name` and `find_account_id`.
Both are pure functions with no I/O, making them easy to test with parametrize and Hypothesis.

`sanitize_folder_name` transliterates Swedish characters (å→a, ä→a, ö→o) and replaces
special/reserved characters with underscores.

`find_account_id` performs case-insensitive substring matching between a folder name
and a dict of account names, strips the `kontoutdrag_` prefix, and picks the longest
match when multiple accounts match.

## Acceptance criteria
- [x] Tests for `sanitize_folder_name`: å/ä/ö/Å/Ä/Ö transliteration, special chars replaced,
      spaces replaced, leading/trailing underscores stripped
- [x] Hypothesis test for `sanitize_folder_name`: output never contains Swedish letters or
      reserved path characters
- [x] Tests for `find_account_id`: exact match, no match → None, single substring match,
      multiple matches → returns longest, `kontoutdrag_` prefix stripped before matching
- [x] Tests pass with `make test`

## Completion
**Date:** 2026-03-28
**Summary:** 37 characterisation tests written in tests/unit/test_account_matching.py.
Covers all Swedish letter transliterations, each reserved path char individually,
space/control-char/underscore edge cases, 4 Hypothesis invariants (no Swedish chars,
no reserved chars, no leading/trailing underscore, idempotency), and 8 find_account_id
cases (no match, prefix stripping, substring both ways, Swedish chars in account name,
multiple matches → longest wins). All 37 tests pass, ruff clean.
**Files changed:**
- `tests/unit/test_account_matching.py` — created
**Stage:** `git add tests/unit/test_account_matching.py docs/tasks/TASK-003-tests-sanitize-find-account.md`
**Commit:** `git commit -m "Add characterisation tests for sanitize_folder_name and find_account_id"`
