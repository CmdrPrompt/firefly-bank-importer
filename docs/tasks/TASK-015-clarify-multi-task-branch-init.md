# TASK-015 Clarify multi-task branch initialization workflow

## Status
done

## Description
Clarify in CLAUDE.md that when multiple tasks are created for a larger initiative, all task files should be created first and each task branch should be created/switched before implementation starts.

## Acceptance criteria
- [x] CLAUDE.md explicitly defines a workflow for multi-task initiatives
- [x] Workflow states that task files are created first and branches initialized for each task before coding begins
- [x] Existing single-task workflow remains valid and unambiguous

## Completion
**Date:** 2026-03-28
**Summary:** Added an explicit multi-task initiative workflow to CLAUDE.md that requires creating all task files first and initializing a dedicated branch per task before implementation starts.
**Files changed:**
- `CLAUDE.md` — modified
- `docs/tasks/TASK-015-clarify-multi-task-branch-init.md` — created
**Branch:** `git checkout -b task/015-clarify-multi-task-branch-init`
**Stage:** `git add CLAUDE.md docs/tasks/TASK-015-clarify-multi-task-branch-init.md`
**Commit:** `git commit -m "Clarify multi-task branch initialization workflow"`
