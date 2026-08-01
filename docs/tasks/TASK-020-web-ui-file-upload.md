# TASK-020 Web UI file upload

## Status
cancelled

## Description
Implement UC-22 in the web UI: upload CSV files through the interface and place them in import folders.

## Acceptance criteria
- [x] UI accepts CSV uploads
- [x] API validates supported bank format
- [x] Uploaded files are saved to selected import folder with feedback

## Completion
**Date:** 2026-03-29
**Summary:** Implemented web UI CSV upload flow with a dedicated upload page and multipart upload API endpoint. Added per-file validation for CSV extension, UTF-8 decoding, non-empty header, and supported bank format resolution via header detection. Valid files are saved to selected import folder while rejected files return user-visible reason and status in both API and HTML feedback.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified
- `tests/unit/test_web_ui_file_upload.py` -- created
- `pyproject.toml` -- modified
- `docs/tasks/TASK-020-web-ui-file-upload.md` -- modified
**Branch:** `git checkout -b task/020-web-ui-file-upload`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_file_upload.py pyproject.toml docs/tasks/TASK-020-web-ui-file-upload.md`
**Commit:** `git commit -m "Implement web UI file upload"`

> **Superseded (2026-08-01):** The web UI (`web_ui.py` and its tests) has been removed from this repository. The web frontend is being rebuilt as a standalone application in a separate repository, consuming this project's service layer as a library. This task's original status was `done`; its scope no longer applies here.
