# TASK-025 Tests for web UI coverage gap

## Status
done

## Description
Add characterization tests for currently untested branches in `src/firefly_bank_importer/web_ui.py` so that `make test` passes the repository coverage threshold again.

## Branch
**Branch name:** `task/025-tests-web-ui-coverage-gap`
**Switch/create:** `git checkout -b task/025-tests-web-ui-coverage-gap`
**Make target:** `make branch-task f=TASK-025`

## Acceptance criteria
- [x] Characterization tests cover untested web UI helper/error branches without changing production behavior
- [x] `make test` passes with total coverage at or above 80%

## Completion
**Date:** 2026-03-29
**Summary:** Added characterization tests for web UI settings helpers, upload validation failures, and live-import error branches. The changes raised `web_ui.py` coverage from 73% to 90% and restored `make test` to passing with total coverage at 87%.
**Files changed:**
- `docs/tasks/TASK-025-tests-web-ui-coverage-gap.md` -- created / modified
- `tests/unit/test_web_ui_file_upload.py` -- modified
- `tests/unit/test_web_ui_live_import_progress.py` -- modified
**Branch:** `git checkout -b task/025-tests-web-ui-coverage-gap`
**Stage:** `git add docs/tasks/TASK-025-tests-web-ui-coverage-gap.md tests/unit/test_web_ui_file_upload.py tests/unit/test_web_ui_live_import_progress.py`
**Commit:** `git commit -m "Add web UI coverage characterization tests"`
