# TASK-043 Fix web UI folder selection tests

## Status
in-progress

## Description
Two test quality issues found in the web UI folder selection tests:

1. `test_index_renders_folder_table_and_selection_works` did not mock `load_account_cache`,
   so it always hit the error path instead of testing the happy path ("selection works").
2. `test_selection_page_marks_unresolved_folders` had a weak, three-way OR assertion with
   a typo ("diabled") that accepted any of three strings instead of verifying the exact
   rendered output.

## Branch
**Branch name:** `task/043-fix-web-ui-folder-selection-tests`
**Switch/create:** `git checkout -b task/043-fix-web-ui-folder-selection-tests`
**Make target:** `make branch-task f=TASK-043`

## Acceptance criteria
- [x] `test_index_renders_folder_table_and_selection_works` mocks account cache and tests the happy path
- [x] `test_selection_page_marks_unresolved_folders` asserts exactly `"unresolved"` and `"⚠ Ej matchad"`
- [x] All tests pass (`make test`)

## Completion
**Date:** 2026-04-02
**Summary:** Fixed `test_index_renders_folder_table_and_selection_works` to mock `load_account_cache`
via `imf.ACCOUNT_CACHE_FILE` so the selection page renders the account mapping form instead of the
error page. Tightened the unresolved-folder assertion to check for the exact CSS class and status text
rendered by the production code.
**Files changed:**
- `tests/unit/test_web_ui_folder_selection.py` — modified
- `tests/unit/test_web_ui_account_matching.py` — modified
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-043-fix-web-ui-folder-selection-tests.md` — created
**Branch:** `git checkout task/043-fix-web-ui-folder-selection-tests`
**Stage:** `git add tests/unit/test_web_ui_folder_selection.py tests/unit/test_web_ui_account_matching.py CHANGELOG.md docs/tasks/TASK-043-fix-web-ui-folder-selection-tests.md`
**Commit:** `git commit -m "Fix web UI folder selection tests to cover happy path and tighten assertions"`
