# TASK-022 Web UI import history and logs

## Status
done

## Description
Implement UC-20 in the web UI: show prior import runs and detailed logs for audit and troubleshooting.

## Branch
**Branch name:** `task/022-web-ui-import-history-logs`
**Switch/create:** `git checkout -b task/022-web-ui-import-history-logs`
**Make target:** `make branch-task f=TASK-022`

## Acceptance criteria
- [x] API returns import history list
- [x] UI displays history entries with status and timestamp
- [x] Detailed log view is available per run

## Completion
**Date:** 2026-03-30
**Summary:** Implemented web UI import history and per-run log views with corresponding API endpoints and tests. Added missing test dependency for FastAPI TestClient and validated feature tests pass.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified (history APIs and pages)
- `tests/unit/test_web_ui_import_history.py` -- created
- `docs/REQUIREMENTS_import_firefly.md` -- modified (implementation status)
- `CHANGELOG.md` -- modified
- `pyproject.toml` -- modified (web runtime deps)
**Branch:** `git checkout -b task/022-web-ui-import-history-logs`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_import_history.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md pyproject.toml docs/tasks/TASK-022-web-ui-import-history-logs.md`
**Commit:** `git commit -m "Implement web UI import history and logs"`
