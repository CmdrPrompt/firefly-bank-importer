# TASK-062 Patch known-vulnerable transitive dependencies flagged by pip-audit

## Status
in-progress

## Requirements
**Binding:** Requirement 3 (REQUIREMENTS_CI.md)
**BDD mode:** BDD-ABSENT
**Depends on:** TASK-061
**Precedence:** The requirements document is the binding definition of this task.
The story and scenarios below are derived from it. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a maintainer of this repo, I want the dependency lock file upgraded past
the known-vulnerable versions `pip-audit` reports, so that the CI Audit step
passes cleanly instead of failing on real CVEs.

## Description
TASK-061 made `pip-audit` runnable; running it now reports 14 known
vulnerabilities in 5 packages: `click` 8.3.1 (fix 8.3.3), `idna` 3.11 (fix
3.15), `pytest` 9.0.2 (fix 9.0.3), `starlette` 1.0.0 (fix 1.3.1), `urllib3`
2.6.3 (fix 2.7.0). None are pinned in `pyproject.toml`, so
`uv lock --upgrade-package click --upgrade-package idna --upgrade-package
pytest --upgrade-package starlette --upgrade-package urllib3` resolves
`uv.lock` to versions at/above each fix, with no `pyproject.toml` edits.

## Branch
**Branch name:** `task/062-patch-vulnerable-dependencies`
**Switch/create:** `git checkout -b task/062-patch-vulnerable-dependencies`
**Make target:** `make branch-task f=TASK-062`

## Acceptance criteria (Gherkin)

- [ ] Scenario: pip-audit reports zero vulnerabilities
      Given `uv.lock` is upgraded per the Description
      When `uv run pip-audit --progress-spinner=off` runs
      Then it exits 0 and reports no known vulnerabilities

- [ ] Scenario: Lint and test still pass after the upgrade
      Given the upgraded `uv.lock`
      When `make lint` and `make test` run
      Then both pass, confirming the version bumps don't break the app

## Out of scope
- Any `pyproject.toml` version constraint changes — the upgrade is a lock
  file resolution only.
- Future vulnerabilities disclosed after this task completes.

## Blockers
None

## Completion
**Date:** 2026-08-01
**Summary:** Ran `uv lock --upgrade-package click --upgrade-package idna --upgrade-package pytest --upgrade-package starlette --upgrade-package urllib3`, resolving `uv.lock` to click 8.4.2, idna 3.18, pytest 9.1.1, starlette 1.3.1, urllib3 2.7.0 (all at/above their fix versions). `uv run pip-audit --progress-spinner=off` now exits 0 with "No known vulnerabilities found". `make lint` and `make test` (462 passed) both still pass; no `pyproject.toml` changes needed.
**Files changed:**
- `uv.lock` - modified
**Branch:** `git checkout task/062-patch-vulnerable-dependencies`
**Stage:** `git add uv.lock CHANGELOG.md REQUIREMENTS_CI.md docs/tasks/TASK-062-patch-vulnerable-dependencies.md`
**Commit:** `git commit -m "Patch known-vulnerable transitive dependencies flagged by pip-audit"`
