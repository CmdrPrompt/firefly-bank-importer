# TASK-018 Web UI dry-run preview

## Status
cancelled

## Description
Implement UC-18 in the web UI: provide dry-run preview for selected folders and account mappings before live import.

## Acceptance criteria
- [x] API endpoint returns dry-run preview summary
- [x] UI shows counts, date range, and duplicate skips
- [x] Errors/warnings are visible before user can run live import

## Completion
**Date:** 2026-03-28
**Summary:** Implemented dry-run preview in web UI via `GET /api/dry-run-preview` and `GET /preview`. Preview computes per-folder and total candidate transactions, duplicate skips based on latest-date lookup, date range, and warnings/errors. Added blocking guard (`can_continue`) when unresolved errors exist so live import can be prevented. Added unit tests for API summary content, duplicate counting, error blocking, and HTML preview rendering.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified
- `tests/unit/test_web_ui_dry_run_preview.py` -- created
- `docs/tasks/TASK-018-web-ui-dry-run-preview.md` -- modified
**Branch:** `git checkout -b task/018-web-ui-dry-run-preview`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_dry_run_preview.py docs/tasks/TASK-018-web-ui-dry-run-preview.md`
**Commit:** `git commit -m "Implement web UI dry-run preview"`

> **Superseded (2026-08-01):** The web UI (`web_ui.py` and its tests) has been removed from this repository. The web frontend is being rebuilt as a standalone application in a separate repository, consuming this project's service layer as a library. This task's original status was `done`; its scope no longer applies here.
