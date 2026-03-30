# TASK-026 Reduce cognitive complexity

## Status
done

## Description
Reduce cognitive complexity in the codebase by prioritizing functions flagged by the linting complexity checks (Complexipy) and implementing safe refactors that preserve existing behavior.

## Initial complexity baseline (2026-03-29)
Result from `make lint` / Complexipy at task start:

- `src/firefly_bank_importer/web_ui.py` -- `create_app` (158, failed)
- `src/firefly_bank_importer/web_ui.py` -- `_build_dry_run_summary` (63, failed)
- `src/firefly_bank_importer/config.py` -- `load_firefly_url` (19, failed)

`make lint` currently fails due to these complexity violations.

## Cognitive complexity note
- Complexipy uses Sonar-style cognitive complexity scoring.
- Score increases with control-flow breaks (`if`, loops, `except`, boolean chains) and with nesting depth.
- In this repository, functions above the enforced threshold fail `make lint` (current observed gate: 15).

## Branch
**Branch name:** `task/026-reduce-cognitive-complexity`
**Switch/create:** `git checkout -b task/026-reduce-cognitive-complexity`
**Make target:** `make branch-task f=TASK-026`

## Acceptance criteria
- [x] `make lint` has been run at task start and Complexipy output has been reviewed and documented in this task
- [x] A focused complexity-reduction change is implemented for one or more flagged functions without behavior regressions
- [x] Lint and tests pass after the refactor

## Completion
**Date:** 2026-03-29
**Summary:** Refactored cognitive-complexity hotspots by splitting `load_firefly_url`, extracting dry-run summary helpers, and restructuring the web UI app into router-based endpoints plus focused live-import helpers. Complexipy now passes for all functions (`create_app` reduced from 158 to 1, `_build_dry_run_summary` from 63 to 3, and `load_firefly_url` from 19 to 4) with `make lint` and `make test` both passing.
**Files changed:**
- `docs/tasks/TASK-026-reduce-cognitive-complexity.md` -- created / modified
- `docs/REQUIREMENTS_import_firefly.md` -- modified
- `CHANGELOG.md` -- modified
- `src/firefly_bank_importer/config.py` -- modified
- `src/firefly_bank_importer/web_ui.py` -- modified
**Branch:** `git checkout -b task/026-reduce-cognitive-complexity`
**Stage:** `git add docs/tasks/TASK-026-reduce-cognitive-complexity.md docs/REQUIREMENTS_import_firefly.md CHANGELOG.md src/firefly_bank_importer/config.py src/firefly_bank_importer/web_ui.py`
**Commit:** `git commit -m "Reduce cognitive complexity in targeted functions"`
