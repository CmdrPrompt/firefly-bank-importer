# TASK-006 Tests for load_account_cache

## Status
done

## Description
Add characterisation tests for `load_account_cache`. Uses `tmp_path` and monkeypatching
to avoid touching the real `accounts_cache.json`.

The function reads a JSON cache file, validates its structure, and returns a list of
Account TypedDicts — or None on any error path (missing file, invalid JSON, wrong types).

## Acceptance criteria
- [x] Cache file does not exist → returns None
- [x] Valid cache with one or more accounts → returns correct list of Account dicts
- [x] Cache with invalid JSON → returns None
- [x] Cache where `accounts` field is not a list → returns None
- [x] Cache with items missing `id`, `name`, or wrong types → those items skipped,
      valid items still returned
- [x] `type` field defaults to `"asset"` when absent from an item
- [x] `fetched_at` field is absent → does not crash (defaults to "okänt")
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 13 characterisation tests covering all acceptance criteria. Monkeypatches
`ACCOUNT_CACHE_FILE` global via `tmp_path` fixture to avoid touching real cache file.
**Files changed:**
- `tests/unit/test_account_cache.py` — created
- `docs/tasks/TASK-006-tests-load-account-cache.md` — modified
**Stage:** `git add tests/unit/test_account_cache.py docs/tasks/TASK-006-tests-load-account-cache.md`
**Commit:** `git commit -m "Add characterisation tests for load_account_cache"`
