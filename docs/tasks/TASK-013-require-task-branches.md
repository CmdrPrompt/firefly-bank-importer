# TASK-013 Require dedicated branch per task

## Status
done

## Description
Update the project workflow instructions so it is explicit that every task must be
done on its own Git branch rather than directly on `main`.

## Acceptance criteria
- [x] `CLAUDE.md` clearly states that every task must live on its own branch.
- [x] `CLAUDE.md` includes a recommended branch naming pattern tied to the task id.
- [x] The task template in `CLAUDE.md` includes branch information.
- [x] The instructions explain what to do if task work is found on `main`.
- [x] `Makefile` includes a task helper target that creates/switches branch from task file branch metadata.

## Completion
**Date:** 2026-03-28
**Summary:** Updated `CLAUDE.md` to require a dedicated Git branch for every task, added a recommended branch naming convention, ensured the task template includes branch metadata at task-start level (`## Branch`), and documented the recovery rule for task work discovered on `main`. Added `make branch-task` in `Makefile`, following the same task-file-driven pattern as `stage-task` and `commit-task`, so branch create/switch can be executed from the task file metadata.
**Files changed:**
- `CLAUDE.md` — modified
- `Makefile` — modified
- `docs/tasks/TASK-013-require-task-branches.md` — created
**Branch:** `git checkout -b task/013-require-task-branches`
**Stage:** `git add CLAUDE.md Makefile docs/tasks/TASK-013-require-task-branches.md`
**Commit:** `git commit -m "Require dedicated branch for each task"`
