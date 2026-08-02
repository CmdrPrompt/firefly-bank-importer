# TASK-068 Finalize stable, documented service-layer interface for external consumption

## Status
todo

## Requirements
**Binding:** FR-71, FR-72, FR-73
**BDD mode:** BDD-ACTIVE
**Depends on:** TASK-067
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As an external application developer (e.g. a separate web frontend project), I want a
stable, well-documented public interface to the service layer that I can import and
use independently, with clear documentation of function signatures, parameters,
return types, and event types, so that I can integrate this importer's logic into
my own application without being forced to depend on the CLI or re-implement the
business logic myself.

## Description
FR-73 requires the service layer to be "importable as a Python library by an external
application via a stable module path and function/class signatures, without this
repository running its own HTTP server." This task finalizes that interface after
TASK-067 completes the refactor. Specifically:

1. Define the public module path (e.g. `firefly_bank_importer.service` or similar).
2. Document all public functions, classes, event types, and their parameters,
   return types, and exceptions with clear docstrings and/or an interface guide.
3. Verify that the service layer has no dependency on web frameworks (Flask, FastAPI)
   or HTTP servers (uvicorn, gunicorn, waitress).
4. Confirm that external applications provide their own `FireflyClient` instance
   (constructed in their own code, real in production, mocked in tests) rather than
   the service layer constructing the client.

The result is a stable, importable library interface suitable for consumption by
projects outside this repository.

## Branch
**Branch name:** `task/068-finalize-service-layer-interface`
**Switch/create:** `git checkout -b task/068-finalize-service-layer-interface`
**Make target:** `make branch-task f=TASK-068`

## Acceptance criteria (Gherkin)
- [ ] Scenario: Service layer has stable, documented public interface
      Given the refactored service layer from TASK-067
      When external documentation (docstrings, interface guide, or README section) describes the importable module path and public functions/classes per FR-71/FR-73
      Then the public functions, classes, event types, and their parameters, return types, and exceptions are clearly documented so an external application can use them

- [ ] Scenario: Service layer can be imported and used without CLI code
      Given an external application (not this repo) imports the service layer per FR-73
      When it instantiates a FireflyClient separately (or provides a mocked one for testing) and calls a public service-layer function with configuration (folder paths, flags, client instance)
      Then the import succeeds, the function runs without argparse or sys.exit logic, and all results are delivered through return values and event objects (not logging or stdout)

- [ ] Scenario: Service layer has no web framework or HTTP server dependency
      Given the service-layer module and its test suite
      When the module dependencies are analyzed (import statements, pyproject.toml dependencies)
      Then no web framework (Flask, FastAPI, Django) or HTTP server (uvicorn, gunicorn, waitress) appears as a dependency or import within the service layer itself; only `firefly-python-api` and standard library are used for HTTP

- [ ] Scenario: Service layer results are communicated via return values and event objects
      Given an external application calls service-layer functions
      When it provides a callback or event listener for progress/result events
      Then all transaction results, folder summaries, and progress updates are delivered through those event objects and return values, with no reliance on globals, direct logging configuration, or stdout/stderr redirection from the calling environment

## Out of scope
- Building an actual web frontend or HTTP API in this repository (that belongs to the consuming project).
- Creating a separate Python package or PyPI publication (the service layer is used via internal import from within the repo or via git subtree in consuming projects).
- Documentation of how the consuming project should implement HTTP APIs or web UIs on top of the service layer.

## Blockers
None

## Completion

**Date:** 2026-08-02
**Summary:** Moved the already event-pure functions identified in TASK-067
(`fetch_accounts_from_firefly`, `create_transaction` + private helpers,
opening-balance detection + private helpers, transfer posting + private
helper, and the multi-folder-import orchestration + private helpers) from
`import_firefly.py` into `firefly_bank_importer.service`, renaming the
genuine public entry points to drop their leading underscore
(`_apply_auto_opening_balance` -> `apply_auto_opening_balance`,
`_post_transfer` -> `post_transfer`, `_run_multi_folder_import` ->
`run_multi_folder_import`) while keeping true implementation-detail helpers
private. `import_firefly.py` now imports all of these back under their new
names and keeps every other function (CLI-only code and the still
logging-coupled orchestration functions) unchanged.

Investigation surfaced a dependency conflict not anticipated by the
original plan: `run_multi_folder_import`'s pre-existing gather step
(`_gather_folder_pending` and its collaborators) directly called
`logging.*` and depended on CLI-only functions (`find_account_id`,
`get_latest_transaction_date`, `auto_split_folder`) that must stay behind
per this task's narrow scope, and `service.py` cannot import from
`import_firefly.py` without a circular import. Resolved by giving
`run_multi_folder_import` its own self-contained, logging-free gather
implementation in `service.py` (`_gather_folder_pending`,
`_account_id_for_folder`, `_latest_transaction_date`,
`_collect_csv_pending_rows`, `_compute_latest_date_floor`) distinct from
`import_firefly.py`'s own logging-emitting versions of the same shape
(unchanged, still used by the CLI's single-folder `process_folder` path),
and factoring the transfer-detection-and-posting tail (shared by both
paths) into a new private `_post_transfer_and_unmatched_events` generator
in `service.py` that `import_firefly._render_multi_folder_import` now
calls directly with its own CLI-gathered rows. This keeps the CLI's
golden-master log output byte-for-byte unchanged while making
`run_multi_folder_import` genuinely logging-free for external callers, at
the cost of the self-contained gather step not supporting the CLI's
auto-split-non-monthly-CSV convenience (a known, documented limitation for
external callers using this entry point directly).

`BLOCK_TRANSACTION_POSTS`/`BLOCK_GUARD_MESSAGE` moved to `service.py`
alongside `create_transaction`/`post_transfer` (since Python resolves a
function's module-level names in its own defining module); ~15 existing
test files that toggle this test-safety guard via
`monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", ...)` were updated
to target `firefly_bank_importer.service` directly where the guard's
effect is actually asserted (most "reset to False" fixtures needed no
change since the guard's default is already False and monkeypatch restores
values after each test regardless of which module's copy is patched).

Added `src/firefly_bank_importer/__init__.py` re-exporting the public
surface (5 functions + 9 event/result types) with `__all__`, and
`docs/SERVICE_LAYER_INTERFACE.md` documenting the module path, every
public function's signature/params/returns/raises, the event/result type
table, and a usage example for an external caller. Linked the new doc from
`README.md`. Added `docs/tasks/TASK-069-decouple-remaining-orchestration-logging.md`
(file only, no implementation) tracking the remaining logging-coupled
orchestration functions (`process_csv`, `process_folder`,
`build_account_map`, `find_account_id`, `create_import_folders`,
`_resolve_folder_account_and_files`, `_collect_csv_pending_rows`, and
`get_latest_transaction_date`'s leftover warning) as the known gap before
they can join the public surface.

Added `tests/unit/test_task_068_service_gather.py` characterizing the new
private silent-gather helpers (connection-error handling, ambiguous/no
account match, unresolvable CSV format, empty folders, period filtering,
opening-balance-floor precedence) to close coverage gaps the move
introduced, and updated ~10 existing test files
(`test_account_name_logging.py`, `test_auto_opening_balance.py`,
`test_coverage_wins.py`, `test_progress_bar.py`,
`test_task_067_event_contracts.py`, `test_task_067_golden_master.py`,
`test_task_067_steps.py`) to import the renamed public functions from
`firefly_bank_importer.service`/`import_firefly`'s re-export and to
configure `client.get_transactions_by_type` directly instead of patching
`import_firefly.get_latest_transaction_date` where they exercise
`run_multi_folder_import` directly (that patch target no longer has any
effect on the service layer's self-contained gather step).

Verification: `uv run pytest tests/bdd/steps/test_task_068_steps.py -v`
(4/4 scenarios pass, no assertions weakened); `make lint` passes; `make
test` passes (467 tests, coverage 95.94%, up from the TASK-067 baseline of
95.55%); `make bdd` passes (15/15 scenarios across both TASK-067 and
TASK-068 feature files); manual import check
(`from firefly_bank_importer.service import run_multi_folder_import,
create_transaction, apply_auto_opening_balance, post_transfer,
fetch_accounts_from_firefly`) succeeds; `grep` for web-framework/HTTP-server
names in `pyproject.toml`/`service.py` returns nothing.
**Files changed:**
- `src/firefly_bank_importer/service.py` - modified (moved/renamed public functions + private helpers, added self-contained silent gather path, `_post_transfer_and_unmatched_events`, `BLOCK_TRANSACTION_POSTS`/`BLOCK_GUARD_MESSAGE`, `Account` TypedDict)
- `src/firefly_bank_importer/import_firefly.py` - modified (removed moved definitions, imports renamed public surface from `.service`, `_gather_folder_pending`/`_render_multi_folder_import` updated to call the shared `_post_transfer_and_unmatched_events` core)
- `src/firefly_bank_importer/__init__.py` - modified (public re-exports + `__all__`)
- `docs/SERVICE_LAYER_INTERFACE.md` - created
- `README.md` - modified (link to the new interface doc)
- `docs/tasks/TASK-069-decouple-remaining-orchestration-logging.md` - created
- `tests/unit/test_task_068_service_gather.py` - created
- `tests/unit/test_account_name_logging.py` - modified
- `tests/unit/test_auto_opening_balance.py` - modified
- `tests/unit/test_coverage_wins.py` - modified
- `tests/unit/test_progress_bar.py` - modified
- `tests/unit/test_task_067_event_contracts.py` - modified
- `tests/unit/test_task_067_golden_master.py` - modified
- `tests/bdd/steps/test_task_067_steps.py` - modified
- `tests/bdd/features/TASK-068-finalize-service-layer-interface.feature` - added (red phase, pre-existing)
- `tests/bdd/steps/test_task_068_steps.py` - added (red phase, pre-existing)
- `CHANGELOG.md` - modified

**Branch:** `git checkout task/068-finalize-service-layer-interface`

**Stage:** `src/firefly_bank_importer/service.py src/firefly_bank_importer/import_firefly.py src/firefly_bank_importer/__init__.py docs/SERVICE_LAYER_INTERFACE.md README.md docs/tasks/TASK-068-finalize-service-layer-interface.md docs/tasks/TASK-069-decouple-remaining-orchestration-logging.md tests/unit/test_task_068_service_gather.py tests/unit/test_account_name_logging.py tests/unit/test_auto_opening_balance.py tests/unit/test_coverage_wins.py tests/unit/test_progress_bar.py tests/unit/test_task_067_event_contracts.py tests/unit/test_task_067_golden_master.py tests/bdd/steps/test_task_067_steps.py tests/bdd/features/TASK-068-finalize-service-layer-interface.feature tests/bdd/steps/test_task_068_steps.py CHANGELOG.md`

**Commit:** `git commit -m "Finalize documented public service-layer interface (TASK-068)"`
