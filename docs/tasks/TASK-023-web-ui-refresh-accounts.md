# TASK-023 Web UI refresh accounts

## Status
done

## Description
Implement UC-21 in the web UI: trigger account refresh from Firefly and show refresh summary.

## Branch
**Branch name:** `task/023-web-ui-refresh-accounts`
**Switch/create:** `git checkout -b task/023-web-ui-refresh-accounts`
**Make target:** `make branch-task f=TASK-023`

## Acceptance criteria
- [x] API endpoint refreshes accounts cache
- [x] UI action triggers refresh and shows results
- [x] New folders created during refresh are reported

## Completion
**Date:** 2026-03-30
**Summary:** Implemented POST /api/refresh-accounts endpoint that triggers live account discovery, updates the local cache, creates missing import folders, and returns a summary. Added "Uppdatera konton" button on the index page. Added 5 unit tests covering summary response, folder creation, skipping existing folders, error handling, and index page link.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified (refresh endpoint and index link)
- `tests/unit/test_web_ui_refresh_accounts.py` -- created
- `docs/REQUIREMENTS_import_firefly.md` -- modified (UC-21, FR-58, FR-59)
- `CHANGELOG.md` -- modified
**Branch:** `git checkout -b task/023-web-ui-refresh-accounts`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_refresh_accounts.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-023-web-ui-refresh-accounts.md`
**Commit:** `git commit -m "Implement web UI account refresh"`
