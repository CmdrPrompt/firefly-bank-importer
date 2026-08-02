# TASK-066 Define service-layer event types and extract side-effect-free transfer helpers

## Status
todo

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
- [ ] Scenario: Service layer module imports without CLI dependencies
      Given a new service-layer module is created
      When external code imports it
      Then no import errors occur and no CLI-only dependencies (argparse, tqdm, sys.exit, direct stdout/print) are introduced into the importing context

- [ ] Scenario: Transfer-matching helpers are extracted with identical behavior
      Given transfer-matching functions are moved to the service-layer module
      When the existing test suite runs
      Then all tests pass unchanged, confirming behavior is identical

- [ ] Scenario: Structured result types are defined and inspectable
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
