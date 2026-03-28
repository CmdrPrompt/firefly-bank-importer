# TASK-014 Checkout main after pr-task

## Status
done

## Description
Update the `make pr-task` target to automatically checkout `main` branch after creating and pushing the GitHub PR. This ensures the user is returned to the main branch after the PR workflow completes.

## Branch
**Branch name:** `task/014-pr-task-checkout-main`
**Switch/create:** `git checkout -b task/014-pr-task-checkout-main`
**Make target:** `make branch-task f=TASK-014`

## Acceptance criteria
- [x] `make pr-task` creates and pushes PR to GitHub
- [x] `make pr-task` automatically checks out `main` after PR is created

## Completion
**Date:** 2026-03-28
**Summary:** Added `git checkout main` as the final step in the pr-task target. This ensures users are returned to the main branch after creating a PR from a task branch, completing the workflow cleanly.
**Files changed:**
- `Makefile` — modified
**Branch:** `task/014-pr-task-checkout-main`
**Stage:** `git add Makefile`
**Commit:** `git commit -m "Auto-checkout main after pr-task creates PR"`
