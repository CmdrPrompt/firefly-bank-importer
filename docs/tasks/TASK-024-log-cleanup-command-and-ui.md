# TASK-024 Log cleanup command (CLI-only)

## Status
todo

## Description
Implement UC-23 and FR-37: clear import logs (all or older than N days) with explicit confirmation, available through the CLI. Originally also required a web UI action, but the local web UI has been retired (see TASK-064); this task is now CLI-only.

## Acceptance criteria
- [ ] CLI supports deleting all logs or logs older than retention days
- [ ] Destructive operation requires explicit confirmation

## Completion
**Date:** YYYY-MM-DD
**Summary:**
**Files changed:**
- `path/to/file` -- created / modified
**Branch:** `git checkout -b task/024-log-cleanup-command-and-ui`
**Stage:** `git add path/to/file1 path/to/file2 CHANGELOG.md`
**Commit:** `git commit -m "Implement log cleanup command"`
