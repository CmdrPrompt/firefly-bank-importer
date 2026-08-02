# TASK-066 Define service-layer event types and extract side-effect-free transfer helpers

## Status
done

## Requirements
**Binding:** FR-71, FR-72, FR-73
**BDD mode:** BDD-ABSENT
**Depends on:** none
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a developer on this importer, I want to define structured types for import
results and progress events, and extract already side-effect-free transfer-matching
helpers into a dedicated service-layer module, so that the service layer can be
imported by external applications without CLI dependencies and future refactoring can
decouple logging/tqdm from the import logic.

## Description
FR-71 requires a service layer with no dependency on stdout/print, argparse,
process exit codes, or terminal-only libraries (e.g. tqdm). To begin this
refactor safely, this task:

1. Defines structured types (e.g. TransactionResult, FolderResult, ProgressEvent) that
   will be used for communicating results and progress from the service layer.
2. Creates a new service-layer module (e.g. `src/firefly_bank_importer/service.py` or
   similarly named).
3. Extracts the already side-effect-free transfer-matching helper functions into
   the service-layer module:
   - `_match_transfer_pairs`
   - `_choose_candidate`
   - `_choose_among`
   - `_is_amount_and_date_match`
   - `_candidates_for_row`
   - `_resolve_row_choice`
   - `_description_overlap`

This is a mechanical, low-risk refactor: no behavior changes, no new business logic,
and it is verified by the existing test suite continuing to pass unchanged.

## Branch
**Branch name:** `task/066-define-service-layer-events-and-extract-helpers`
**Switch/create:** `git checkout -b task/066-define-service-layer-events-and-extract-helpers`
**Make target:** `make branch-task f=TASK-066`

## Acceptance criteria (Gherkin)
- [x] Scenario: Service layer module imports without CLI dependencies
      Given a new service-layer module is created
      When external code imports it
      Then no import errors occur and no CLI-only dependencies (argparse, tqdm, sys.exit, direct stdout/print) are introduced into the importing context

- [x] Scenario: Transfer-matching helpers are extracted with identical behavior
      Given transfer-matching functions are moved to the service-layer module
      When the existing test suite runs
      Then all tests pass unchanged, confirming behavior is identical

- [x] Scenario: Structured result types are defined and inspectable
      Given the service-layer module defines types for transaction result, folder result, and progress events
      When code constructs these objects with date, amount, account ID, status (OK/ERROR), and error message fields
      Then the objects can be inspected by callers to extract these values without requiring logging calls or side effects

## Out of scope
- Refactoring posting or orchestration functions to emit events (that is TASK-067).
- Decoupling logging.info/error or tqdm from existing code; those changes come later.
- Any changes to CLI entry-point logic or argv handling.
- Changes to `REQUIREMENTS_import_firefly.md`; requirements are already bound.

## Blockers
None

## Completion
**Date:** 2026-08-02
**Summary:** Created `src/firefly_bank_importer/service.py` with no dependency on `tqdm`,
`argparse`, `sys.exit`, or print, verified by an AST-based test. Moved `PendingRow`,
`parse_amount`, `MAX_TRANSFER_DATE_DIFF_DAYS`, and the seven transfer-matching helpers
(`_match_transfer_pairs`, `_choose_candidate`, `_choose_among`, `_is_amount_and_date_match`,
`_candidates_for_row`, `_resolve_row_choice`, `_description_overlap`) into the new module.
`parse_amount` and `PendingRow` were included even though not named in the task's helper
list, because the listed helpers depend on them directly — keeping them in
`import_firefly.py` would have made the service module import CLI-adjacent code and
defeated FR-71's "no dependency on CLI-only concerns" requirement. `import_firefly.py`
now re-imports these names (with `__all__`) so all existing tests continue to pass
unchanged. Defined `TransactionStatus` (OK/ERROR), `TransactionResult` (date, amount,
account_id, status, error_message), `FolderResult`, and `ProgressEvent` as frozen
dataclasses in the service module, per FR-71's structured-event requirement; these types
are not wired into any orchestration logic yet — that is TASK-067. Added
`tests/unit/test_service_layer.py` (10 tests) covering the no-CLI-dependency constraint,
identical behavior of the moved helpers, and construction/inspection of the new structured
types. `make test`: 416 passed (406 pre-existing + 10 new), coverage 95.27% (baseline
95.15%). `make lint`: clean.
**Files changed:**
- `src/firefly_bank_importer/service.py` - created
- `src/firefly_bank_importer/import_firefly.py` - modified (removed extracted definitions, re-imports from service)
- `tests/unit/test_service_layer.py` - created
- `CHANGELOG.md` - modified (new entry under `### Added`)
- `docs/tasks/TASK-066-define-service-layer-events-and-extract-helpers.md` - modified (Status/Completion)
**Branch:** `git checkout task/066-define-service-layer-events-and-extract-helpers`
**Stage:** `src/firefly_bank_importer/service.py src/firefly_bank_importer/import_firefly.py tests/unit/test_service_layer.py CHANGELOG.md docs/tasks/TASK-066-define-service-layer-events-and-extract-helpers.md`
**Commit:** `git commit -m "Define service-layer event types and extract transfer helpers"`
