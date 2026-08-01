# TASK-021 Web UI Firefly settings

## Status
cancelled

## Description
Implement UC-15 in the web UI: configure Firefly URL and token from settings page with validation and persistence.

## Acceptance criteria
- [x] UI form saves URL and token
- [x] API validates URL against Firefly
- [x] Values persist to config/secrets files

## Completion
**Date:** 2026-03-29
**Summary:** Added `GET /settings` endpoint returning current Firefly URL and token-present indicator (without exposing token value), and `POST /api/settings` endpoint that validates URL against Firefly `/api/v1/about` before persisting to `config.json` and `secrets.json`. Validation failures return HTTP 422 without modifying files. Both first-time setup and updates are supported. Added settings navigation link in the index page. Implemented with TDD (13 new unit tests). Merged main into task branch before implementation to pick up full web UI base. Added UC-15 and FR-47..50 to requirements spec.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` — modified
- `tests/unit/test_web_ui_settings.py` — created
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `docs/tasks/TASK-021-web-ui-settings-firefly-config.md` — modified
**Branch:** `git checkout -b task/021-web-ui-settings-firefly-config`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_settings.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-021-web-ui-settings-firefly-config.md`
**Commit:** `git commit -m "Implement web UI settings endpoint for Firefly URL and token"`

> **Superseded (2026-08-01):** The web UI (`web_ui.py` and its tests) has been removed from this repository. The web frontend is being rebuilt as a standalone application in a separate repository, consuming this project's service layer as a library. This task's original status was `done`; its scope no longer applies here.
