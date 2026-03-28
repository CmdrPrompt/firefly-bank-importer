# TASK-017 Web UI account matching

## Status
done

## Description
Implement UC-17 in the web UI: allow interactive mapping between selected folders and Firefly accounts.

## Acceptance criteria
- [x] API provides account candidates for each folder
- [x] UI allows selecting/overriding account mapping per folder
- [x] Mapping validation prevents continuing with unresolved folders

## Completion
**Date:** 2026-03-28
**Summary:** Implemented account matching page with candidates from Firefly cache using sanitize_folder_name matching logic. Selection page shows account dropdown for each folder with status indicator (✓ Matchad / ⚠ Ej matchad). Added /api/account-candidates endpoint returning best_match and all matching candidates. Added 6 unit tests validating form rendering, error handling, API response structure. Test coverage improved to 84%, all 264 tests passing.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified
- `tests/unit/test_web_ui_account_matching.py` -- created
- `docs/tasks/TASK-017-web-ui-account-matching.md` -- modified
**Branch:** `git checkout -b task/017-web-ui-account-matching`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_account_matching.py docs/tasks/TASK-017-web-ui-account-matching.md`
**Commit:** `git commit -m "Implement web UI account matching (UC-17)"`
