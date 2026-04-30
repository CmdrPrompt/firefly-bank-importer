# TASK-047 Expand firefly-python-client with account, transaction, and resource methods

## Status

todo

## Description

TASK-046 establishes the core `firefly-python-client` library with session management,
credential loading, and connection validation only. Three additional API operations are
duplicated between `import_firefly.py` and `web_ui.py` and belong in the client library.
`firefly-bills-analyzer` also needs read-only access to bills, budgets, categories, and
summary — none of which are exposed today.

This task adds two layers to the library:

**Layer 1 — account/transaction methods** (eliminates duplication in this project):

- `get_asset_accounts()` — paginated `GET /api/v1/accounts?type=asset`
- `get_latest_transaction_date(account_id)` — `GET /api/v1/accounts/{id}/transactions?limit=1`
- `create_transaction(payload)` — `POST /api/v1/transactions`

**Layer 2 — read-only resource methods** (enables `firefly-bills-analyzer`):

- `get_bills()` — `GET /api/v1/bills`
- `get_budgets()` — `GET /api/v1/budgets`
- `get_budget_limits(budget_id)` — `GET /api/v1/budgets/{id}/limits`
- `get_categories()` — `GET /api/v1/categories`
- `get_summary()` — `GET /api/v1/summary/basic`

All methods belong on `FireflyClient` and must be completed and merged in
`firefly-python-client` before the subtree is pulled into any consumer project.

## Branch

**Branch name:** `task/047-expand-firefly-python-client-api`
**Switch/create:** `git checkout -b task/047-expand-firefly-python-client-api`
**Make target:** `make branch-task f=TASK-047`

## Acceptance criteria

- [ ] TASK-046 is merged and the `libs/firefly-python-client/` subtree is present
- [ ] `FireflyClient.get_asset_accounts()` returns a list of `{"id": int, "name": str}` dicts,
  fetching all pages automatically
- [ ] `FireflyClient.get_latest_transaction_date(account_id)` returns an ISO date string
  (`YYYY-MM-DD`) or `None` if the account has no transactions
- [ ] `FireflyClient.create_transaction(payload)` posts to `/api/v1/transactions` and raises
  `FireflyConnectionError` on non-2xx status
- [ ] `FireflyClient.get_bills()`, `get_budgets()`, `get_budget_limits(budget_id)`,
  `get_categories()`, and `get_summary()` return the raw `data` list (or dict for summary)
  from the Firefly JSON response
- [ ] All new methods have unit tests with ≥90% coverage in the `firefly-python-client` repo
- [ ] Inline `requests.Session` calls for accounts and transactions in `import_firefly.py`
  and `web_ui.py` are replaced with the new `FireflyClient` methods
- [ ] The subtree in `libs/firefly-python-client/` is updated via
  `git subtree pull --prefix=libs/firefly-python-client <repo-url> main --squash`
- [ ] The requirements spec (`docs/REQUIREMENTS_import_firefly.md`) is updated to reflect
  that account and transaction HTTP calls are delegated to `firefly-python-client`
- [ ] `make lint && make test` pass

## Completion

<!-- Fill in when done -->
**Date:**
**Summary:**
**Files changed:**
**Branch:**
**Stage:**
**Commit:**
