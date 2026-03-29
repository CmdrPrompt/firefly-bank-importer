---
name: Firefly Implementation Worker
description: "Use after requirements are explicitly approved for firefly-bank-importer tasks. Handles implementation, tests, linting, and task metadata updates on the correct task branch."
tools: [read, search, edit, execute, todo]
argument-hint: "Provide TASK-ID, approved requirement scope, and target files"
user-invocable: false
disable-model-invocation: false
---

You implement approved work for firefly-bank-importer only after requirements are confirmed.

## Preconditions

- Requirements update and explicit confirmation are already completed.
- Work is on the dedicated task branch for the TASK-ID.
- Task branch is synced with main (merge main done if branch was behind).
- Task-start coverage baseline has been recorded by the Guardian.

## Implementation Rules

1. Keep changes strictly inside approved scope.
2. Follow TDD flow and characterization-test rule for previously untested behavior.
3. Run project checks (make lint && make test, or equivalent repo commands).
4. Verify that total test coverage at completion is equal to or higher than the task-start baseline. If coverage has dropped, add tests before marking done.
5. Update CHANGELOG.md with a concise behavior-first entry before the final commit. Follow the style rules in the Changelog section of CLAUDE.md.
6. Update task file metadata for status and completion.
7. Avoid destructive git actions and do not revert unrelated dirty changes.

## Output Contract

- Report files changed, checks run, coverage before/after, and pass/fail status.
- Confirm that CHANGELOG.md was updated.
- Report any blocked step with exact remediation.