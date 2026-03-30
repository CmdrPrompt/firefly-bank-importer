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
- [x] API endpoint returns account names list
- [x] UI action triggers refresh and shows results
- [x] Results page lists all discovered account names
- [x] New folders created during refresh are reported

## Completion
**Date:** 2026-03-30
**Summary:** Implemented POST /api/refresh-accounts endpoint returning total accounts, new folders, and account names list. Added POST /refresh-accounts HTML result page listing all discovered account names and counts. Changed index button to POST to /refresh-accounts so the user sees a proper result page instead of raw JSON. Added 9 unit tests covering summary, folder creation, skipping existing folders, error handling, index button target, account names in API response, result page content, counts, and back link.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` — modified (RefreshAccountsResult, _perform_refresh_accounts, _render_refresh_result_page, POST /refresh-accounts route, index button target)
- `tests/unit/test_web_ui_refresh_accounts.py` — modified (4 new tests added)
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-21 updated, FR-58 updated, FR-59 updated, FR-60 added)
- `CHANGELOG.md` — modified
**Branch:** `git checkout -b task/023-web-ui-refresh-accounts`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_refresh_accounts.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-023-web-ui-refresh-accounts.md`
**Commit:** `git commit -m "Show account list on refresh-accounts result page"`
