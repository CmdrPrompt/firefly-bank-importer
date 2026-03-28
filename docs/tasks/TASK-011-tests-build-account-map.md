# TASK-011 Tests for build_account_map

## Status
done

## Description
Add characterisation tests for `build_account_map`. The function orchestrates cache
loading, optional Firefly API fetching, cache saving, and a `sys.exit(1)` fallback.
Uses `monkeypatch` to stub `load_account_cache`, `fetch_accounts_from_firefly`, and
`save_account_cache` rather than touching real files or HTTP.

## Acceptance criteria
- [x] `refresh=False`, cache hit: returns account map from cache; fetch is **not**
      called
- [x] `refresh=True`: cache is skipped; `fetch_accounts_from_firefly` called; cache
      saved
- [x] `refresh=False`, cache miss, fetch succeeds: fetches from Firefly, saves cache,
      returns map
- [x] `refresh=False`, cache miss, fetch fails, fallback cache hit: logs error, returns
      fallback cache
- [x] `refresh=False`, cache miss, fetch fails, no fallback: logs error and calls
      `sys.exit(1)`
- [x] `refresh=True`, fetch fails, no cache: calls `sys.exit(1)`
- [x] Tests pass with `make test`

## Completion
**Date:** 2025-07-14
**Summary:** Added 9 characterisation tests covering all acceptance criteria. Stubs
`load_account_cache`, `fetch_accounts_from_firefly`, and `save_account_cache` via
`unittest.mock.patch.object`. Coverage rose from 79% to 85%.
**Files changed:**
- `tests/unit/test_build_account_map.py` — created
- `docs/tasks/TASK-011-tests-build-account-map.md` — modified
**Stage:** `git add tests/unit/test_build_account_map.py docs/tasks/TASK-011-tests-build-account-map.md`
**Commit:** `git commit -m "Add characterisation tests for build_account_map"`
