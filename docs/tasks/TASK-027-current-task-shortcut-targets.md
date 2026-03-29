# TASK-027 Current-task shortcut targets

## Status
done

## Description
Add Makefile shortcut targets that operate on the current task branch without requiring `f=<TASK-ID>`: one for stage, one for commit, and one for creating a pull request.

## Branch
**Branch name:** `task/027-current-task-shortcut-targets`
**Switch/create:** `git checkout -b task/027-current-task-shortcut-targets`
**Make target:** `make branch-task f=TASK-027`

## Acceptance criteria
- [x] A Make target stages files listed by the task file associated with the current branch
- [x] A Make target commits using the commit message from the task file associated with the current branch
- [x] A Make target creates a PR using title/body from the task file associated with the current branch
- [x] Existing `*-task` targets with `f=<TASK-ID>` continue to work unchanged

## Completion
**Date:** 2026-03-29
**Summary:** Added current-branch workflow shortcuts in `Makefile` (`stage-current-task`, `commit-current-task`, `pr-current-task`) that infer `TASK-<NNN>` from the active branch name and delegate to existing task-aware targets. Updated requirements/changelog and verified with linting.
**Files changed:**
- `docs/tasks/TASK-027-current-task-shortcut-targets.md` -- created / modified
- `docs/REQUIREMENTS_import_firefly.md` -- modified
- `Makefile` -- modified
- `CHANGELOG.md` -- modified
**Branch:** `git checkout -b task/027-current-task-shortcut-targets`
**Stage:** `git add docs/tasks/TASK-027-current-task-shortcut-targets.md docs/REQUIREMENTS_import_firefly.md Makefile CHANGELOG.md`
**Commit:** `git commit -m "Add current-task Makefile shortcut targets"`
