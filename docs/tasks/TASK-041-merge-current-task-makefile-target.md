# TASK-041 Add merge-pr and merge-current-task Makefile targets

## Status
done

## Description
Add Makefile targets for squash-merging an open PR without conflicts and pulling main,
so the full task commit workflow can be completed without leaving the terminal.

`make merge-pr f=TASK-001` resolves the task branch from the task file, finds the open
PR via `gh pr list`, checks `mergeable == "MERGEABLE"`, runs `gh pr merge --squash
--delete-branch`, then `git checkout main && git pull`.

`make merge-current-task` derives the task ID from the current branch name and delegates
to `merge-pr`.

Also document the new targets in `CLAUDE.md` (task commit workflow section) and in
`.github/agents/firefly-workflow-guardian.agent.md` (gate list step 13).

## Branch
**Branch name:** `task/041-merge-current-task-makefile-target`
**Switch/create:** `git checkout -b task/041-merge-current-task-makefile-target`
**Make target:** `make branch-task f=TASK-041`

## Acceptance criteria
- [x] `make merge-pr f=TASK-NNN` squash-merges the open PR for the resolved branch and pulls main
- [x] `make merge-pr` exits non-zero with a clear message when PR is not mergeable
- [x] `make merge-current-task` delegates to `make merge-pr` using the current branch task ID
- [x] `CLAUDE.md` task commit workflow includes `make merge-current-task` step
- [x] `firefly-workflow-guardian.agent.md` gate list includes merge step after PR step
- [x] `CLAUDE.md` and `firefly-workflow-guardian.agent.md` document that `make commit-current-task` is mandatory for all task-branch commits (no direct `git commit`)

## Completion
**Date:** 2026-03-30
**Summary:** Added `merge-pr` and `merge-current-task` targets to Makefile; updated CLAUDE.md
and firefly-workflow-guardian.agent.md to document the new merge step and to enforce that
all task-branch commits must use `make commit-current-task` (no direct `git commit`).
**Files changed:**
- `Makefile` — modified: added `merge-pr` and `merge-current-task` targets
- `CLAUDE.md` — modified: added `make merge-current-task` to task commit workflow; added mandatory commit rule
- `.github/agents/firefly-workflow-guardian.agent.md` — modified: added step 13 for merge; added "Commit via Makefile" gate
- `docs/tasks/TASK-041-merge-current-task-makefile-target.md` — created
**Branch:** `git checkout task/041-merge-current-task-makefile-target`
**Stage:** `git add Makefile CLAUDE.md .github/agents/firefly-workflow-guardian.agent.md docs/tasks/TASK-041-merge-current-task-makefile-target.md`
**Commit:** `git commit -m "Add merge-pr and merge-current-task Makefile targets and enforce commit-current-task rule"`
