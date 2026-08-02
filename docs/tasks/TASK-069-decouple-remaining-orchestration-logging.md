# TASK-069 Decouple remaining orchestration functions from direct logging

## Status
todo

## Requirements
**Binding:** FR-71, FR-72, FR-73
**BDD mode:** BDD-PLANNED
**Depends on:** TASK-068
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As an external application developer, I want the remaining folder/account
orchestration logic (folder-to-account resolution, CSV format detection,
account discovery/caching) to communicate exclusively through return values
and event objects, so that I can use the full CSV-import pipeline -- not just
the posting/transfer/opening-balance primitives -- from my own application
without inheriting this repository's `logging` configuration.

## Description
TASK-068 finalized and documented the subset of the service layer that was
already event-pure as of TASK-067 (`fetch_accounts_from_firefly`,
`create_transaction`, `apply_auto_opening_balance`, `post_transfer`,
`run_multi_folder_import`, plus the event/result types), moving them into
`firefly_bank_importer.service`.

Investigation during TASK-068 found that several other orchestration
functions still call `logging.*` directly and remain internal to
`firefly_bank_importer.import_firefly` (the CLI module), rather than being
part of the public, documented service-layer surface:

- `process_csv` -- logs the detected bank format, the "Senaste i Firefly"
  cutoff message, unknown-format errors, and the skipped-row count.
- `process_folder` -- logs "Inget konto hittat", "Inga CSV-filer", per-folder
  progress lines ("Konto ID ...", "Bearbetar: ...").
- `build_account_map` -- logs cache hits/misses and Firefly-fetch errors, and
  calls `sys.exit(1)` on an unrecoverable fetch failure with no cache
  fallback.
- `find_account_id` -- logs an info line when an ambiguous folder-name match
  is resolved by preferring the longest account name.
- `create_import_folders` -- logs per-folder creation and a summary count.
- `_resolve_folder_account_and_files` -- logs "Inget konto hittat"/"Inga
  CSV-filer" (same messages as `process_folder`).
- `_collect_csv_pending_rows` -- logs the detected bank format and
  unknown-format errors.
- `get_latest_transaction_date` -- has a leftover `logging.warning` on a
  `FireflyConnectionError` from the Firefly API call.

This task converts each of the above to communicate its outcomes via
return values and/or a structured event type (extending the existing
`ProgressEvent`/`FolderResult`/`TransactionResult` family in
`firefly_bank_importer.service` as needed, e.g. an `AccountResolutionEvent`
or similar for the "account not found"/"ambiguous match" cases and a
`CacheEvent` or similar for `build_account_map`'s cache hit/miss/fetch-error
outcomes), moves the resulting logging-free functions into
`firefly_bank_importer.service`, and updates `import_firefly.py`'s CLI
adapter functions to render the new event types to the log identically to
today's output (characterization tests must continue to pass unchanged).
`build_account_map`'s `sys.exit(1)` call must also be replaced with a
raised exception or an ERROR-status result, since the service layer must
never call `sys.exit` (FR-72).

No implementation is performed in this task -- file only, per user
decision recorded during TASK-068.

## Branch
**Branch name:** `task/069-decouple-remaining-orchestration-logging`
**Switch/create:** `git checkout -b task/069-decouple-remaining-orchestration-logging`
**Make target:** `make branch-task f=TASK-069`

## Acceptance criteria (Gherkin)
- [ ] 1. Scenario: process_csv and process_folder communicate via return values and events only
      Given `process_csv` and `process_folder` currently call `logging.info`/`logging.error`/`logging.warning` directly
      When they are converted to the event-based contract per FR-71
      Then they return/yield structured result or progress event objects instead of logging directly, and the CLI adapter renders those events to the log with output identical to today's characterization tests

- [ ] 2. Scenario: build_account_map communicates account discovery/cache outcomes via events, without sys.exit
      Given `build_account_map` currently logs cache hits/misses/fetch errors and calls `sys.exit(1)` on an unrecoverable fetch failure
      When it is converted to the event-based contract per FR-71/FR-72
      Then it returns a structured result (success with accounts, or an ERROR-status/raised-exception outcome) instead of calling `sys.exit`, and the CLI adapter renders the outcome and exits with the same code as today when appropriate

- [ ] 3. Scenario: find_account_id, create_import_folders, and the CSV-format-detection helpers communicate via events only
      Given `find_account_id`, `create_import_folders`, `_resolve_folder_account_and_files`, and `_collect_csv_pending_rows` currently call `logging.*` directly
      When they are converted to the event-based contract per FR-71
      Then they return/yield structured event objects instead of logging directly, and the CLI adapter renders those events to the log with output identical to today's characterization tests

- [ ] 4. Scenario: get_latest_transaction_date's connection-error path is logging-free
      Given `get_latest_transaction_date` currently logs a warning on `FireflyConnectionError`
      When it is converted to the event-based contract per FR-71
      Then it returns `None` (or a structured error result) without calling `logging.warning`, and the CLI adapter renders the same warning message when appropriate

- [ ] 5. Scenario: the newly event-pure functions join the public service-layer surface
      Given the functions above have been converted per criteria 1-4
      When `docs/SERVICE_LAYER_INTERFACE.md` and `firefly_bank_importer/__init__.py` are updated
      Then the converted functions (renamed to drop any leading underscore where they become public entry points) are documented and re-exported alongside the existing TASK-068 public surface

## Out of scope
- Building an actual web frontend or HTTP API in this repository.
- Changing the CLI's observable log output for any of the affected functions (characterization tests must continue to pass unchanged).
- Any further logging/CLI decoupling beyond the functions explicitly listed above.

## Blockers
None

## Completion
