# TASK-006 Tests for load_account_cache

## Status
todo

## Description
Add characterisation tests for `load_account_cache`. Uses `tmp_path` and monkeypatching
to avoid touching the real `accounts_cache.json`.

The function reads a JSON cache file, validates its structure, and returns a list of
Account TypedDicts — or None on any error path (missing file, invalid JSON, wrong types).

## Acceptance criteria
- [ ] Cache file does not exist → returns None
- [ ] Valid cache with one or more accounts → returns correct list of Account dicts
- [ ] Cache with invalid JSON → returns None
- [ ] Cache where `accounts` field is not a list → returns None
- [ ] Cache with items missing `id`, `name`, or wrong types → those items skipped,
      valid items still returned
- [ ] `type` field defaults to `"asset"` when absent from an item
- [ ] `fetched_at` field is absent → does not crash (defaults to "okänt")
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
