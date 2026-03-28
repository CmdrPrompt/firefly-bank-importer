# TASK-019 Web UI live import progress

## Status
done

## Description
Implement UC-19 in the web UI: run live import and stream progress/log output during execution.

## Acceptance criteria
- [x] API starts live import job asynchronously
- [x] UI receives progress updates in real time
- [x] Completion summary includes imported, skipped, and failed counts

## Completion
**Date:** 2026-03-29
**Summary:** Implemented asynchronous live-import jobs in web UI with in-memory job registry, background worker threads, start/status APIs, and a polling-based progress page. Added cumulative imported/skipped/failed counters, per-job event logs, current folder/file context, and completion/error states. Wired dry-run preview page to allow starting live import when preview is non-blocking.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` -- modified
- `tests/unit/test_web_ui_live_import_progress.py` -- created
- `docs/tasks/TASK-019-web-ui-live-import-progress.md` -- modified
**Branch:** `git checkout -b task/019-web-ui-live-import-progress`
**Stage:** `git add src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_live_import_progress.py docs/tasks/TASK-019-web-ui-live-import-progress.md`
**Commit:** `git commit -m "Implement web UI live import progress"`
