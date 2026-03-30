# TASK-029 Fix URL validation not called on startup

## Status
todo

## Description
`load_firefly_url` is called in `import_firefly.py` without passing `validate_fn`,
so `_is_url_valid` always returns `True` immediately (rad 100 i `config.py`).
This means an incorrect Firefly URL is accepted and saved without being validated
against the API (`/api/v1/about`), as required by FR-29 and UC-12.

The fix is to pass the real validation function (`validate_firefly_url`) at the
call site in `import_firefly.py`.

## Branch
**Branch name:** `task/029-fix-url-validation-not-called`
**Switch/create:** `git checkout -b task/029-fix-url-validation-not-called`
**Make target:** `make branch-task f=TASK-029`

## Acceptance criteria
- [ ] `load_firefly_url` is called with an explicit `validate_fn` in `import_firefly.py`
- [ ] An invalid URL causes the user to be re-prompted rather than accepted silently
- [ ] Existing tests pass; new test covers the validation-at-startup path

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/029-fix-url-validation-not-called`
**Stage:** `git add docs/tasks/TASK-029-fix-url-validation-not-called.md`
**Commit:** `git commit -m "Fix URL validation never called on startup"`
