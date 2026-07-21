# TASK-017 Integration tests for remaining read methods

## Status

done

## Requirements

**Binding:** REQ-004 (UC-004-5, new)
**BDD mode:** BDD-ABSENT
**Depends on:** TASK-016
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)

As a developer maintaining this library, I want every read-only method on
`FireflyClient` to have an integration test against a real Firefly III
instance, so that a regression in request shape or response parsing is
caught before it reaches a consumer project. `get_transactions_for_account`
and `get_budget_limits` were the last two read methods without integration
coverage.

## Description

Add two integration tests to `tests/integration/test_integration.py`,
following the existing `@skip_if_no_credentials` pattern:

- `get_transactions_for_account(account_id)`, called with the first account
  ID from `get_asset_accounts()`; asserts a `list[str]` is returned.
- `get_budget_limits(budget_id)`, called with the first budget ID from
  `get_budgets()`; skipped (via `pytest.skip`) when no budget exists on the
  instance; asserts a `list` is returned.

No production code changes are needed — both methods already exist and are
unit-tested; this task closes the integration-test gap only.

## Branch

**Branch name:** `task/016-transactions-by-type` (continued from TASK-016;
not yet merged to `main` at the time this task was started — see TASK-016's
Completion notes)
**Switch/create:** already on the branch; no new branch created
**Make target:** n/a (branch already checked out)

## Acceptance criteria (Gherkin)

- [x] Scenario: `get_transactions_for_account` integration coverage
      Given a real Firefly III instance reachable via `FIREFLY_URL`/`FIREFLY_TOKEN`
      (skipped automatically when absent)
      When `get_transactions_for_account(account_id)` is called with the
      first account from `get_asset_accounts()`
      Then it returns a `list[str]` without raising

- [x] Scenario: `get_budget_limits` integration coverage
      Given a real Firefly III instance and at least one budget
      When `get_budget_limits(budget_id)` is called with the first budget
      from `get_budgets()`
      Then it returns a `list` without raising
      And the test is skipped (not failed) when no budget exists

- [x] Scenario: Quality gates pass
      Given the completed implementation
      When `make lint && make test` are run
      Then both pass, and unit test coverage does not drop below the
      task-start baseline

## Out of scope

- Any change to `get_transactions_for_account` or `get_budget_limits`
  themselves.
- Integration tests for write operations (`create_transaction`,
  `delete_transaction`, `create_bill`, `set_opening_balance`) — REQ-004
  explicitly excludes write operations.

## Blockers

None.

## Completion

**Date:** 2026-07-21
**Summary:** Added `test_get_transactions_for_account_returns_list_of_ids`
and `test_get_budget_limits_returns_list` to
`tests/integration/test_integration.py`, run against a real Firefly III
instance. `get_transactions_for_account` passed. `get_budget_limits` skipped
(no budgets exist on the configured instance), which is the specified
behavior rather than a failure. No production code changed. Confirmed the
pre-existing, unrelated `test_get_opening_balance_returns_balance_and_date`
failure (real instance returns a full ISO datetime instead of `YYYY-MM-DD`)
still reproduces and is untouched, same as noted in TASK-016.
**Files changed:**

- `tests/integration/test_integration.py` - modified (two new integration tests)
- `docs/REQUIREMENTS.md` - modified (REQ-004 gains UC-004-5)
- `docs/tasks/TASK-017-remaining-read-integration-tests.md` - created
- `docs/tasks/TASK-016-transactions-by-type.md` - modified (post-completion note about this task sharing its branch)

**Branch:** `git checkout task/016-transactions-by-type`
**Stage:** `git add tests/integration/test_integration.py docs/REQUIREMENTS.md docs/tasks/TASK-017-remaining-read-integration-tests.md docs/tasks/TASK-016-transactions-by-type.md CHANGELOG.md`
**Commit:** `git commit -m "Add integration tests for get_transactions_for_account and get_budget_limits"`
