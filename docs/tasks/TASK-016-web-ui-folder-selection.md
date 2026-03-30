# TASK-016 Web UI folder selection

## Status
done

## Description
Implement UC-16 in the web UI: list import folders and show file previews so users can choose folders without CLI paths. Include a convenient Make target for starting the web UI during development.

## Acceptance criteria
- [x] Web page lists folders under bankImports/
- [x] Each folder shows file count and basic metadata
- [x] User can select one or more folders for next step
- [x] Make target `web` starts `firefly-import-web`

## Completion
**Date:** 2026-03-28
**Summary:** Implemented FastAPI-based web UI for folder selection with HTML + JSON API endpoints. Folder listing detects CSV format, computes row counts and date ranges. Multi-select checkboxes enable folder selection. Added `make web` target for convenient development startup. All 4 acceptance criteria verified: folder listing ✓, metadata display ✓, multi-select working ✓, make target functional ✓. Unit tests (3/3) passing and live tested on <http://127.0.0.1:8000>.
**Files changed:**
- `Makefile` -- modified
- `pyproject.toml` -- modified
- `src/firefly_bank_importer/web_ui.py` -- created
- `tests/unit/test_web_ui_folder_selection.py` -- created
- `docs/tasks/TASK-016-web-ui-folder-selection.md` -- modified
**Branch:** `git checkout -b task/016-web-ui-folder-selection`
**Stage:** `git add Makefile pyproject.toml src/firefly_bank_importer/web_ui.py tests/unit/test_web_ui_folder_selection.py docs/tasks/TASK-016-web-ui-folder-selection.md`
**Commit:** `git commit -m "Implement web UI folder selection"`
