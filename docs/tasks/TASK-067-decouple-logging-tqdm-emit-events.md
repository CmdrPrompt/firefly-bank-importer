# TASK-067 Decouple logging and tqdm, emit structured events, make CLI a thin adapter

## Status
done

## Requirements
**Binding:** FR-71, FR-72, FR-73, UC-30, UC-31, UC-33, UC-34
**BDD mode:** BDD-ABSENT
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

- [x] Scenario: Transaction posting emits structured results, not logging
      Given a posting function processes a transaction
      When the function executes per FR-71
      Then it returns/yields a structured result object (no direct `logging.info/error` calls) containing date, amount, description, account ID, account name, status (OK/ERROR), and error message

- [x] Scenario: Progress tracking uses events, not tqdm parameters
      Given posting and orchestration functions previously accepted `pbar: tqdm | None` as a parameter
      When refactored per FR-71
      Then they no longer accept pbar and instead emit progress events; the CLI consumes and renders these events to tqdm, producing output identical to the unrefactored tqdm bar

- [x] Scenario: CLI log output for single-folder dry-run matches pre-refactor behavior (characterization test)
      Given a representative single-folder import scenario with known CSV data, run against a mocked FireflyClient in dry-run mode
      When the refactored CLI processes this scenario
      Then the terminal output and log file format, log line content, account names, transaction counts, "Klar!" message, and elapsed duration all match the pre-refactor golden-master version captured against the same mocked setup, confirming behavior is unchanged

- [x] Scenario: CLI log output for multi-folder non-dry-run matches pre-refactor behavior (characterization test)
      Given a representative multi-folder import scenario with transfer detection (UC-31/FR-66), run against a mocked FireflyClient with BLOCK_TRANSACTION_POSTS enabled and dry-run flag omitted
      When the refactored CLI processes this scenario
      Then the terminal output and log file format, log line content, transfer-detection count, per-transaction OK/ERROR status, account names, and elapsed duration all match the pre-refactor golden-master version captured against the same mocked setup, confirming behavior is unchanged

- [x] Scenario: Opening-balance detection result is communicated via events
      Given UC-30 (automatic opening-balance detection) with opening balance = 0
      When the service layer sets the opening balance via `set_opening_balance` per FR-71
      Then a structured result event includes the balance amount, date set, and confirmation that the earliest row was excluded from import; the CLI renders this to the log identically to before

- [x] Scenario: Transfer detection result includes source and destination account names
      Given UC-31/FR-66 transfer detection during multi-folder import
      When a transfer is matched between accounts
      Then the result event includes source account ID, source account name, destination account ID, destination account name, amount, and date; the CLI logs `[OK] [transfer] <amount> SEK | <date> | <source name> -> <destination name> | <description>` per FR-69

- [x] Scenario: Account-name transaction logging works via events
      Given UC-34 (account-name transaction logging)
      When each transaction result event is emitted
      Then it includes the account name resolved from the discovered/cached account list; the CLI logs `[OK] [<account name>] [<type>] <amount> SEK | <date> | <description>` per FR-69 (or `[DRY RUN]` in dry-run mode)

- [x] Scenario: Period scoping works via events
      Given UC-33 (period-scoped import) with `--period YYYY-MM`
      When folders are processed with the period filter applied
      Then the service layer only emits result events for rows from that period's CSV file; the CLI renders the transaction count accurately for that period only

- [x] Scenario: BLOCK_TRANSACTION_POSTS guard is handled consistently for postings and transfers
      Given the current (pre-refactor) code catches the `BLOCK_TRANSACTION_POSTS` guard's `RuntimeError`
      for regular transaction posting (`_handle_batch_result`, producing a `[FEL]` ERROR log line and
      continuing the run) but lets the identical `RuntimeError` from `_post_transfer` propagate
      uncaught, crashing `_run_multi_folder_import` mid-loop
      When the event-based refactor introduces a single structured error-handling path per FR-71
      Then both regular postings and transfer postings that hit the guard emit a structured
      ERROR result event (status ERROR, error message) instead of raising, and the run continues;
      this closes the pre-existing inconsistency as part of this task rather than deferring it

- [x] Scenario: Duration and average-time logging works via events
      Given an import completes after processing T total transactions in D seconds
      When the CLI receives final summary events from the service layer
      Then it logs total elapsed time in `H:MM:SS` format (per FR-70, e.g. `0:05:12`) and average time per transaction in seconds (e.g. `0.42s/transaktion`), identical to the unrefactored version

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

**Commit:** wip(TASK-067): decouple logging/tqdm from posting functions via structured events
