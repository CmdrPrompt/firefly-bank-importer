# TASK-028 Complexity tooling cleanup

## Status
done

## Description
Separate and finalize non-TASK-022 cleanup/tooling changes:
- replace remaining radon references with complexipy in tooling
- improve complexity lint feedback and artifact cleanup workflow
- keep unrelated cleanup isolated from feature task branches

## Branch
**Branch name:** `task/028-complexity-tooling-cleanup`
**Switch/create:** `git checkout -b task/028-complexity-tooling-cleanup`
**Make target:** `make branch-task f=TASK-028`

## Acceptance criteria
- [x] Make lint uses complexipy only
- [x] Complexipy failure output is actionable
- [x] Generated complexipy artifacts are ignored/cleanable
- [x] Cleanup/task metadata is documented

## Completion
**Date:** 2026-03-30
**Summary:** Replaced remaining radon usage with complexipy in lint workflow, added actionable failure explanations, and added cleanup/ignore handling for complexipy artifacts.
**Files changed:**
- `.gitignore` -- modified (ignore complexipy result files and cache)
- `Makefile` -- modified (complexipy lint, explanation hook, clean-complexity target)
- `docs/tasks/TASK-001-add-tests-for-existing-functionality.md` -- modified (wording cleanup)
- `docs/tasks/TASK-028-complexity-tooling-cleanup.md` -- created / modified
- `pyproject.toml` -- modified (complexipy dependency swap and related dev deps)
- `scripts/explain_complexipy_failures.py` -- created
- `src/firefly_bank_importer/config.py` -- modified (complexity refactor)
**Branch:** `git checkout -b task/028-complexity-tooling-cleanup`
**Stage:** `git add .gitignore Makefile docs/tasks/TASK-001-add-tests-for-existing-functionality.md docs/tasks/TASK-028-complexity-tooling-cleanup.md pyproject.toml scripts/explain_complexipy_failures.py src/firefly_bank_importer/config.py`
**Commit:** `git commit -m "Finalize complexity tooling cleanup"`
