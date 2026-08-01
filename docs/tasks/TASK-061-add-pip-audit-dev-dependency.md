# TASK-061 Add pip-audit as a dev dependency so the CI Audit step can run

## Status
done

## Requirements
**Binding:** Requirement 2 (REQUIREMENTS_CI.md)
**BDD mode:** BDD-ABSENT
**Depends on:** TASK-060
**Precedence:** The requirements document is the binding definition of this task.
The story and scenarios below are derived from it. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a maintainer of this repo, I want `pip-audit` installed as part of the
`dev` extra, so that the CI Audit step (`uv run pip-audit
--progress-spinner=off`) can actually run instead of failing because the
tool isn't installed.

## Description
PR #38 (TASK-060), after the `uv`/submodule fixes landed in `python-butler`
(TASK-075, TASK-076), progressed all the way through Checkout → Install →
Lint → Test, then failed at Audit with `Failed to spawn: pip-audit ... No
such file or directory`. `pyproject.toml`'s `[project.optional-dependencies]
dev` list doesn't include `pip-audit`, so `uv sync --extra dev` never
installs it. Add `pip-audit` to that list.

## Branch
**Branch name:** `task/061-add-pip-audit-dev-dependency`
**Switch/create:** `git checkout -b task/061-add-pip-audit-dev-dependency`
**Make target:** `make branch-task f=TASK-061`

## Acceptance criteria (Gherkin)

- [x] Scenario: pip-audit is installed by the dev extra
      Given `pyproject.toml`'s `[project.optional-dependencies] dev` list
      When `uv sync --extra dev` runs
      Then `pip-audit` is installed and `uv run pip-audit --progress-spinner=off` runs without a "Failed to spawn" error

## Out of scope
- Any change to the reusable workflow itself (already fixed, TASK-075/076
  in `python-butler`).
- Acting on any vulnerabilities `pip-audit` reports once it runs — this task
  only makes the tool runnable.

## Blockers
None

## Completion
**Date:** 2026-08-01
**Summary:** Added `pip-audit` to `pyproject.toml`'s `dev` extra. `uv sync --extra dev` now installs it, and `uv run pip-audit --progress-spinner=off` runs (exit 1, due to real dependency vulnerabilities it found — acting on those is explicitly out of scope for this task). `make lint` and `make test` both pass.
**Files changed:**
- `pyproject.toml` - modified
**Branch:** `git checkout task/061-add-pip-audit-dev-dependency`
**Stage:** `git add pyproject.toml uv.lock CHANGELOG.md REQUIREMENTS_CI.md docs/tasks/TASK-061-add-pip-audit-dev-dependency.md`
**Commit:** `git commit -m "Add pip-audit as a dev dependency so the CI Audit step can run"`
