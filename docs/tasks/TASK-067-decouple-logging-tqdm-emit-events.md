# TASK-067 Decouple logging and tqdm, emit structured events, make CLI a thin adapter

## Status
done

## Requirements
**Binding:** FR-71, FR-72, FR-73, UC-30, UC-31, UC-33, UC-34
**BDD mode:** BDD-ACTIVE
**Feature files:** tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature
**Depends on:** TASK-066
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a developer, I want the posting and orchestration functions to communicate results
via structured events instead of calling logging.info/error and passing tqdm progress
bars as parameters, and I want the CLI to become a thin adapter that consumes those
events and renders them to the terminal/log/progress bar exactly as before, so that
the service layer can be imported and used independently by external applications and
the CLI can be tested against mocked clients without behavior change.

## Description
FR-71 requires a service layer with no dependency on terminal libraries. FR-72
requires the CLI to be a thin adapter delegating business logic to the service layer.
This task refactors the posting and orchestration functions to emit structured events
instead of calling logging.info/error and accepting tqdm progress bars. The CLI (`main`,
event rendering loop) becomes a pure adapter: it receives events, renders them to
stdout/log/tqdm identically to the unrefactored version, and is verified by
characterization tests that compare pre- and post-refactor log output line-for-line.

This is the highest-risk step because the code paths being refactored handle live
transaction posting and cross-account transfer matching (UC-31/FR-66). Acceptance
criteria include characterization tests that prove the CLI's visible behavior
(log format, account names, transaction counts, duration, tqdm progress output, exit
codes) is unchanged.

## Branch
**Branch name:** `task/067-decouple-logging-tqdm-emit-events`
**Switch/create:** `git checkout -b task/067-decouple-logging-tqdm-emit-events`
**Make target:** `make branch-task f=TASK-067`

## Acceptance criteria (Gherkin)

**Test Safety Constraint:** All acceptance criteria scenarios — including those exercising the non-dry-run code path — run against a mocked `FireflyClient` per the existing test suite's pattern (MagicMock, monkeypatch), with zero real HTTP calls to any Firefly instance. This mocking requirement is a testing-hygiene principle: tests must be deterministic and runnable without a live, reachable Firefly instance available. Even read-only API calls (e.g. `get_latest_transaction_date`) that would not mutate data are mocked, consistent with the established convention in the existing test suite (e.g. `test_process_folder.py`'s docstring: "monkeypatches get_latest_transaction_date to avoid real HTTP calls"). The module-level `BLOCK_TRANSACTION_POSTS` guard (lines 26, 418, 811, 921/937 in import_firefly.py) must be preserved, enabled for non-dry-run scenarios, and verified by tests to prevent accidental POSTs. This is consistent with the existing test suite's 406 tests, all of which mock the client.

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Transaction posting emits structured results, not logging

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Progress tracking uses events, not tqdm parameters

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: CLI log output for single-folder dry-run matches pre-refactor behavior

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: CLI log output for multi-folder non-dry-run matches pre-refactor behavior

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Opening-balance detection result is communicated via events

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Transfer detection result includes source and destination account names

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Account-name transaction logging works via events

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Period scoping works via events

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: BLOCK_TRANSACTION_POSTS guard is handled consistently for postings and transfers

- [x] See tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature: Scenario: Duration and average-time logging works via events

## Out of scope
- Changes to bank-format packages or CSV parsing logic.
- Changes to account discovery or cache loading.
- Refactoring of account-mapping or folder-resolution logic (those are independent).
- Any new HTTP server or web-framework code in this repository.

## Blockers
None

## Completion

Posting and orchestration functions (`create_transaction`, `_apply_auto_opening_balance`,
`_post_transfer`, `_run_threaded_import`, `_run_multi_folder_import`) no longer call
`logging.info/error` or take a `tqdm` progress bar parameter; they return/yield structured
result objects (`TransactionResult`, `OpeningBalanceResult`, `TransferResult`,
`TransferDetectionSummary`) defined in `firefly_bank_importer.service`. New CLI-side render
functions (`_render_transaction_result`, `_render_opening_balance_result`,
`_render_transfer_result`, `_render_multi_folder_import`, `_UnmatchedGroupRenderer`) own all
`logging` calls and the single shared `tqdm` bar, reproducing the pre-refactor log output
line-for-line. The `BLOCK_TRANSACTION_POSTS` guard now produces a structured ERROR result for
both regular postings and transfers (previously the transfer path let the `RuntimeError`
propagate uncaught), closing that inconsistency per the acceptance criteria.

`tests/unit/test_task_067_event_contracts.py` (17 tests) verifies the structured-result
contracts and that no logging occurs in the service-layer functions.
`tests/unit/test_task_067_golden_master.py` (7 tests) captures the CLI's line-for-line log
output for representative single-folder dry-run and multi-folder non-dry-run scenarios and
asserts it is byte-identical to the documented pre-refactor behavior.
`tests/unit/test_auto_opening_balance.py` (the pre-existing UC-30 characterization suite) was
updated to assert against the new `OpeningBalanceResult`/`_opening_balance_floor` contract and
the "no logging inside `_apply_auto_opening_balance`" invariant, replacing its old
assumption that warnings were logged directly inside that function.

`process_csv` was split into `_run_dry_run_csv_import`/`_run_live_csv_import` and
`_render_multi_folder_import`'s per-account grouping was extracted into a
`_UnmatchedGroupRenderer` helper class to keep both functions under the project's complexity
threshold after the event-based refactor added branching.

**Checks:** `make lint` and `make test` both pass. 440/440 unit tests pass (up from the
pre-task 424, plus the 17 contract tests and 7 golden-master tests, with 2 pre-existing
`test_auto_opening_balance.py` scenarios split/renamed to match the new contract). Coverage
95.55% (task-start baseline ~95.53%) — no regression.

**BDD retrofit:** `pytest-bdd` was added as a dev dependency and `tests/bdd/` is now collected
by pytest (`testpaths`). All ten Gherkin scenarios above were lifted verbatim into
`tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature` and bound to the
already-implemented service layer / CLI adapter via
`tests/bdd/steps/test_task_067_steps.py`, reusing the mocked-`FireflyClient` pattern from
`tests/unit/test_task_067_event_contracts.py` and `tests/unit/test_task_067_golden_master.py`.
All 10 scenarios pass (`uv run pytest tests/bdd/ -v`). Total suite is now 450/450 passing;
`make lint` and `make test` both pass; coverage remains 95.55%, no regression.

**Stage:** `pyproject.toml uv.lock tests/bdd/ docs/tasks/TASK-067-decouple-logging-tqdm-emit-events.md`
**Commit:** `git commit -m "wip(TASK-067): decouple logging/tqdm from posting functions via structured events"`
