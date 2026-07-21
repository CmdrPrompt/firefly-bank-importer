# TASK-016 Transaction fetching by type (generalized) and TASK-015 revert

## Status

done

## Requirements

**Binding:** REQ-011 (new); REQ-002 (revert of UC-002-6 / TASK-015 change)
**BDD mode:** BDD-ABSENT
**Depends on:** none
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)

As a consumer application (firefly-bank-importer), I want a reliable way to
fetch the latest withdrawal/deposit transaction date for a specific account,
because TASK-015's `transaction_type` parameter on
`get_latest_transaction_date` turned out to have no effect: verified against
a real Firefly III instance, `GET /api/v1/accounts/{id}/transactions` ignores
the `type` query parameter entirely (any value, including nonsense ones,
returns the same unfiltered latest transaction). The global
`GET /api/v1/transactions?type=...` endpoint, by contrast, was verified to
filter correctly, including with a comma-separated type list
(`"withdrawal,deposit"`). This task generalizes the existing
`get_withdrawal_transactions` machinery to any type list, and reverts the
now-known-ineffective TASK-015 change.

## Description

**Part A — revert TASK-015:**
Remove the `transaction_type` parameter from
`FireflyClient.get_latest_transaction_date(account_id, transaction_type=None)`,
restoring its original signature `get_latest_transaction_date(account_id)`
and the unfiltered `GET .../transactions?limit=1&page=1` call. Remove the
now-obsolete unit tests added for that parameter in
`tests/test_api_methods.py`.

**Part B — add `get_transactions_by_type`:**
Add `FireflyClient.get_transactions_by_type(transaction_type, start, end, on_page=None)
-> list[TransactionRead]`, generalizing the existing
`get_withdrawal_transactions(start, end, on_page=None)`: same pagination
loop and split-flattening, but the `type` query parameter value comes from
the new `transaction_type` argument instead of being hardcoded to
`"withdrawal"`. Reimplement `get_withdrawal_transactions` as a thin wrapper
calling `get_transactions_by_type("withdrawal", start, end, on_page)`, with
no change to its own signature, docstring behavior, or return semantics.

**Part C — add `destination_id` to `TransactionRead`:**
Add `destination_id: str | None` to the `TransactionRead` `TypedDict` in
`_types.py`, and populate it in `_split_to_transaction_read` from
`split.get("destination_id")`, defaulting to `None` when absent — same rule
as `source_id`, `source_name`, `destination_name`, `category_name`. This
lets callers identify deposit transactions belonging to a given account
(where the account is the destination, not the source).

## Branch

**Branch name:** `task/016-transactions-by-type`
**Switch/create:** `git checkout -b task/016-transactions-by-type`
**Make target:** `make branch-task f=TASK-016`

## Acceptance criteria (Gherkin)

Scenarios are inline (BDD-ABSENT) and lift-ready for `.feature` extraction if
BDD tooling is adopted later.

- [x] Scenario: `get_latest_transaction_date` reverted to its original signature
      Given the TASK-015 `transaction_type` parameter
      When TASK-016 is complete
      Then `get_latest_transaction_date(account_id)` takes no `transaction_type`
      argument, and the request is `GET /api/v1/accounts/{account_id}/transactions?limit=1&page=1`
      with no `type` parameter, matching pre-TASK-015 behavior exactly

- [x] Scenario: `get_transactions_by_type` filters by the given type(s)
      Given a date range with transactions of multiple types
      When `get_transactions_by_type("withdrawal,deposit", start, end)` is called
      Then the request is `GET /api/v1/transactions?type=withdrawal,deposit&start=...&end=...&page=N`
      And the returned list contains only the flattened splits from the API response
      (the client does not additionally filter by type; it trusts Firefly's own filtering)

- [x] Scenario: Pagination and `on_page` behave as in `get_withdrawal_transactions`
      Given a multi-page result set
      When `get_transactions_by_type(...)` is called with an `on_page` callback
      Then all pages are fetched and flattened, and `on_page(page, total_pages)`
      is invoked once per completed page, matching `get_withdrawal_transactions`'s
      existing behavior (REQ-008)

- [x] Scenario: `get_withdrawal_transactions` behavior is unchanged
      Given the existing `get_withdrawal_transactions` test suite
      When `get_withdrawal_transactions` is reimplemented on top of
      `get_transactions_by_type`
      Then all existing tests for `get_withdrawal_transactions` pass unmodified

- [x] Scenario: `TransactionRead.destination_id` present and defaulted
      Given a transaction split with and without a `destination_id` field
      When it is flattened via `_split_to_transaction_read`
      Then `destination_id` is the field's value when present, and `None`
      when absent

- [x] Scenario: Integration test against a real Firefly III instance
      Given a real Firefly III instance reachable via `FIREFLY_URL`/`FIREFLY_TOKEN`
      (skipped automatically when absent, per the existing pattern in
      `tests/integration/test_integration.py`)
      When `get_transactions_by_type("withdrawal,deposit", start, end)` is called
      Then it returns a list of `TransactionRead` dicts, each containing a
      `destination_id` key (`str | None`), without raising

- [x] Scenario: Type checking and quality gates pass
      Given the completed implementation
      When `mypy --strict` is run on `src/`, and `make lint && make test` are run
      Then `mypy --strict` passes, `make lint && make test` pass, and unit
      test coverage does not drop below the task-start baseline

## Out of scope

- Any change to `get_transactions_for_account` or other unrelated methods.
- The firefly-bank-importer-side change consuming `get_transactions_by_type`
  to fix TASK-057's still-broken duplicate-import check (tracked separately
  in that repo's own requirements/task docs).
- Validating `transaction_type` against Firefly III's actual set of allowed
  filter values — forwarded as-is, as already established for the
  (now-reverted) TASK-015 parameter and for `get_withdrawal_transactions`.

## Blockers

None.

## Completion

**Date:** 2026-07-21
**Summary:** Reverted the TASK-015 `transaction_type` parameter on
`get_latest_transaction_date` (confirmed against a real Firefly III instance
that the per-account endpoint ignores `type` entirely). Added
`get_transactions_by_type(transaction_type, start, end, on_page=None)`,
generalizing the pagination/flattening logic previously hardcoded to
`"withdrawal"`; `get_withdrawal_transactions` is now a thin wrapper over it
with unchanged public behavior. Added `destination_id` to `TransactionRead`,
populated the same way as the other optional split fields. Added Hypothesis
coverage for `destination_id` defaulting/preservation in
`_split_to_transaction_read`, and two integration tests
(`test_get_transactions_by_type_returns_list_of_transaction_read`,
`test_get_withdrawal_transactions_still_works_after_refactor`) run against a
real Firefly III instance per user request, both passing. One pre-existing,
unrelated integration test failure was observed
(`test_get_opening_balance_returns_balance_and_date` — the real instance
returns a full ISO datetime instead of `YYYY-MM-DD` for
`opening_balance_date`); left untouched as out of scope for this task.

**Files changed:**

- `src/firefly_python_api/_client.py` - modified (reverted `get_latest_transaction_date`; added `get_transactions_by_type`; `get_withdrawal_transactions` reimplemented as a wrapper; `_split_to_transaction_read` populates `destination_id`)
- `src/firefly_python_api/_types.py` - modified (`TransactionRead` gains `destination_id`)
- `tests/test_api_methods.py` - modified (removed obsolete `transaction_type` tests for `get_latest_transaction_date`; added `TestGetTransactionsByType`; updated `TestGetWithdrawalTransactions` expected dicts for `destination_id`)
- `tests/test_transaction_flatten.py` - modified (Hypothesis coverage for `destination_id`)
- `tests/integration/test_integration.py` - modified (integration tests for `get_transactions_by_type` and `get_withdrawal_transactions` against a real instance)
- `docs/REQUIREMENTS.md` - modified (UC-002-2/UC-002-6 revert, new REQ-011)
- `docs/tasks/TASK-016-transactions-by-type.md` - created

**Branch:** `git checkout task/016-transactions-by-type`
**Stage:** `git add src/firefly_python_api/_client.py src/firefly_python_api/_types.py tests/test_api_methods.py tests/test_transaction_flatten.py tests/integration/test_integration.py docs/REQUIREMENTS.md docs/tasks/TASK-016-transactions-by-type.md CHANGELOG.md`
**Commit:** `git commit -m "Add get_transactions_by_type and revert ineffective get_latest_transaction_date filter"`

**Note (post-completion):** TASK-017 (integration tests for
`get_transactions_for_account` and `get_budget_limits`) was built on top of
this same `task/016-transactions-by-type` branch, at the user's explicit
choice, rather than starting a fresh branch from `main` — this branch was
not yet merged when TASK-017 began. See `docs/tasks/TASK-017-remaining-read-integration-tests.md`.
