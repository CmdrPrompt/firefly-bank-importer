# TASK-011 Tests for build_account_map

## Status
todo

## Description
Add characterisation tests for `build_account_map`. The function orchestrates cache
loading, optional Firefly API fetching, cache saving, and a `sys.exit(1)` fallback.
Uses `monkeypatch` to stub `load_account_cache`, `fetch_accounts_from_firefly`, and
`save_account_cache` rather than touching real files or HTTP.

## Acceptance criteria
- [ ] `refresh=False`, cache hit: returns account map from cache; fetch is **not**
      called
- [ ] `refresh=True`: cache is skipped; `fetch_accounts_from_firefly` called; cache
      saved
- [ ] `refresh=False`, cache miss, fetch succeeds: fetches from Firefly, saves cache,
      returns map
- [ ] `refresh=False`, cache miss, fetch fails, fallback cache hit: logs error, returns
      fallback cache
- [ ] `refresh=False`, cache miss, fetch fails, no fallback: logs error and calls
      `sys.exit(1)`
- [ ] `refresh=True`, fetch fails, no cache: calls `sys.exit(1)`
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**
**Files changed:**
**Stage:**
**Commit:**
