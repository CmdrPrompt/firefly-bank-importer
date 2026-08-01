# TASK-064 Retire local web UI; scope repo to CLI plus importable service layer

## Status
done

## Requirements
**Binding:** FR-71, FR-72, FR-73
**BDD mode:** BDD-ABSENT
**Depends on:** none
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As the maintainer, I want this repository to stop running its own web UI and
instead expose a clean, importable service layer, so that a separate
standalone frontend project can serve both this project and other
Firefly-related tools without inheriting this repo's now-diverged, duplicated
web import logic.

## Description
Per the confirmed requirements-document rewrite (`docs/REQUIREMENTS_import_firefly.md`,
2026-08-01): the FastAPI/Jinja2/HTMX web UI (UC-15/16/18/19/20/21/22, FR-38-50,
FR-55-60, and the earlier draft FR-72/74) is out of scope for this repository.
The web frontend will be rebuilt as a standalone application in a separate
repository, consuming this project's core import logic as an importable
service layer (FR-71/72/73) rather than a locally-hosted HTTP UI.

This task covers retiring the local web UI and its now-superseded tasks:

- Remove `src/firefly_bank_importer/web_ui.py` and its test suite.
- Remove the `firefly-import-web` console script and the `fastapi`/`uvicorn`
  dependencies (and related mypy overrides) that existed only to support it.
- Remove the `make web` target.
- Mark TASK-016, TASK-017, TASK-018, TASK-019, TASK-020, TASK-021, TASK-022,
  TASK-023, TASK-025, TASK-033, TASK-043, and TASK-063 as `cancelled`, since
  their scope (the local web UI) no longer applies to this repository.
- Rescope TASK-024 to CLI-only log cleanup (UC-23/FR-37), dropping its web UI
  acceptance criterion.

The service-layer extraction itself (making `process_folder` /
`_run_multi_folder_import` free of stdout/tqdm coupling and packaging it for
external import, per FR-71/73) is tracked separately and is out of scope for
this task — this task only removes the now out-of-scope web UI and syncs task
bookkeeping to match the confirmed requirements.

## Branch
**Branch name:** `task/064-retire-local-web-ui`
**Switch/create:** `git checkout -b task/064-retire-local-web-ui`
**Make target:** `make branch-task f=TASK-064`

## Acceptance criteria (Gherkin)
- [x] Scenario: Local web UI code is removed
      Given `src/firefly_bank_importer/web_ui.py` and `tests/unit/test_web_ui_*.py` existed
      When this task is completed
      Then those files no longer exist in the repository
- [x] Scenario: Web-only dependencies are removed
      Given `pyproject.toml` declared `fastapi`, `uvicorn`, `python-multipart`, and `httpx` as dependencies only used by the web UI
      When this task is completed
      Then those dependencies, the `firefly-import-web` script entry, and the related mypy overrides are removed
- [x] Scenario: Superseded web UI tasks are cancelled
      Given TASK-016, 017, 018, 019, 020, 021, 022, 023, 025, 033, 043, and 063 targeted the removed web UI
      When this task is completed
      Then each of those task files has Status `cancelled` with a note explaining supersession
- [x] Scenario: Log cleanup task is rescoped to CLI-only
      Given TASK-024 originally required both a CLI command and a web UI action
      When this task is completed
      Then TASK-024 only requires the CLI command (UC-23/FR-37), with the web UI acceptance criterion removed
- [x] Scenario: Lint and tests pass without the web UI
      Given the web UI and its tests are removed and dependencies updated
      When `make lint` and `make test` run
      Then both pass with no reference to the removed `web_ui` module

## Out of scope
- Extracting/refactoring the service layer itself (FR-71 implementation) — a separate task.
- Building the new standalone frontend project — a separate repository, out of this workspace's boundary per this project's cross-workspace rule.

## Blockers
None.

## Completion
**Date:** 2026-08-01
**Summary:** Removed `web_ui.py` and its test suite; removed `fastapi`/`uvicorn`/`python-multipart`/`httpx` dependencies, the `firefly-import-web` script entry, and related mypy overrides from `pyproject.toml`; removed the `make web` target. Cancelled TASK-016, 017, 018, 019, 020, 021, 022, 023, 025, 033, 043, and 063 with supersession notes (each already present with exactly one "Superseded (2026-08-01)" note, verified individually). Rescoped TASK-024 to CLI-only (dropped the "Web UI action" acceptance criterion, updated its title/description, added `CHANGELOG.md` to its Stage line per task-file-format rules). Added a `### Removed` CHANGELOG.md entry under Unreleased describing the web UI removal (TASK-064). Verified `make lint` (ruff/mypy/bandit/pymarkdown/complexipy all pass) and `make test` (406 passed, 95.15% coverage) both green with zero remaining references to `web_ui`/`fastapi`/`uvicorn`/`python-multipart`/`httpx`/`firefly-import-web` outside historical CHANGELOG.md entries and the vendored `.butler/` submodule.

Process notes:
- Status/Completion on this file, and the `in-progress`/`done` transitions on TASK-016/017/018/019/020/021/022/023/025/033/043/063, were originally set by the user directly rather than through Workflow Guardian, which is a process violation the user flagged and asked to be corrected. I independently re-verified every claim in this task with my own tool calls (file existence, `pyproject.toml`/`Makefile` diffs, per-file Status greps, `make lint`, `make test`) before accepting Status `done` and checking off the acceptance criteria myself; I did not take the user's or my predecessor's word for any of it.
- Did not have a pre-implementation coverage baseline to compare against, since the code changes existed uncommitted in the working tree before I was engaged (the coverage non-regression gate's "record baseline immediately before implementation" step was not possible retroactively). Current coverage is 95.15% (406 tests passing), well above the 80% project floor, and the change is a pure deletion of dead code together with its own tests, so a regression is implausible — but this is a known process gap, not a full baseline comparison.
- README.md still describes a web UI (`README.md:5,14,26,33`, including a stale `uv run firefly-web` command) and `docs/REQUIREMENTS_import_firefly.md:545` (NFR-13) still lists `web_ui.py` among the files required to route HTTP calls through `firefly-python-api`. Neither is part of FR-71/72/73 or this task's acceptance criteria, and fixing the requirements line requires a Requirements Drafter round + user confirmation rather than a direct edit by Workflow Guardian, so both are left as follow-up items rather than fixed here.
- Task files use Status `cancelled` for the twelve superseded tasks. That value is not one of the four enumerated in the task-file-format skill (`todo | in-progress | blocked | done`) but is otherwise clear in effect (excluded from active work); flagged here rather than silently accepted or hand-rewritten.
**Files changed:**
- `src/firefly_bank_importer/web_ui.py` — deleted
- `tests/unit/test_web_ui_account_matching.py` — deleted
- `tests/unit/test_web_ui_dry_run_preview.py` — deleted
- `tests/unit/test_web_ui_file_upload.py` — deleted
- `tests/unit/test_web_ui_folder_selection.py` — deleted
- `tests/unit/test_web_ui_import_history.py` — deleted
- `tests/unit/test_web_ui_live_import_progress.py` — deleted
- `tests/unit/test_web_ui_refresh_accounts.py` — deleted
- `tests/unit/test_web_ui_settings.py` — deleted
- `pyproject.toml` — modified
- `Makefile` — modified
- `docs/tasks/TASK-016-web-ui-folder-selection.md` — modified
- `docs/tasks/TASK-017-web-ui-account-matching.md` — modified
- `docs/tasks/TASK-018-web-ui-dry-run-preview.md` — modified
- `docs/tasks/TASK-019-web-ui-live-import-progress.md` — modified
- `docs/tasks/TASK-020-web-ui-file-upload.md` — modified
- `docs/tasks/TASK-021-web-ui-settings-firefly-config.md` — modified
- `docs/tasks/TASK-022-web-ui-import-history-logs.md` — modified
- `docs/tasks/TASK-023-web-ui-refresh-accounts.md` — modified
- `docs/tasks/TASK-025-tests-web-ui-coverage-gap.md` — modified
- `docs/tasks/TASK-033-fix-missing-account-mapping-route.md` — modified
- `docs/tasks/TASK-043-fix-web-ui-folder-selection-tests.md` — modified
- `docs/tasks/TASK-063-web-ui-cli-parity-gap.md` — created/modified
- `docs/tasks/TASK-024-log-cleanup-command-and-ui.md` — modified (rescoped to CLI-only)
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `CHANGELOG.md` — modified (new `### Removed` entry)
**Branch:** `git checkout task/064-retire-local-web-ui`
**Stage:** `pyproject.toml Makefile docs/tasks/TASK-016-web-ui-folder-selection.md docs/tasks/TASK-017-web-ui-account-matching.md docs/tasks/TASK-018-web-ui-dry-run-preview.md docs/tasks/TASK-019-web-ui-live-import-progress.md docs/tasks/TASK-020-web-ui-file-upload.md docs/tasks/TASK-021-web-ui-settings-firefly-config.md docs/tasks/TASK-022-web-ui-import-history-logs.md docs/tasks/TASK-023-web-ui-refresh-accounts.md docs/tasks/TASK-025-tests-web-ui-coverage-gap.md docs/tasks/TASK-033-fix-missing-account-mapping-route.md docs/tasks/TASK-043-fix-web-ui-folder-selection-tests.md docs/tasks/TASK-063-web-ui-cli-parity-gap.md docs/tasks/TASK-024-log-cleanup-command-and-ui.md docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-064-retire-local-web-ui.md uv.lock`
**Commit:** `git commit -m "Retire local web UI in favor of an importable service layer"`
