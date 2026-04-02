# TASK-044 Add GitHub Actions CI pipeline

## Status
in-progress

## Description
No CI pipeline exists. Every PR against main should automatically run lint, tests,
and dependency audit. Implements NFR-11.

## Branch
**Branch name:** `task/044-ci-pipeline`
**Switch/create:** `git checkout -b task/044-ci-pipeline`
**Make target:** `make branch-task f=TASK-044`

## Acceptance criteria
- [x] `.github/workflows/ci.yml` runs `make lint && make test` on every PR to main
- [x] Pipeline fails if lint or tests fail
- [x] `pip-audit` runs and fails on CVEs of severity moderate or higher
- [x] Workflow uses `uv` for dependency installation to match local setup

## Completion
**Date:** 2026-04-02
**Summary:** Added `.github/workflows/ci.yml` with two jobs: `lint-and-test` (ruff, mypy, pytest) and `dependency-audit` (pip-audit). Added `pip-audit` to `[dependency-groups] dev` in `pyproject.toml`. Local audit confirms no vulnerabilities.
**Files changed:**
- `.github/workflows/ci.yml` — created
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-044-ci-pipeline.md` — created
**Branch:** `git checkout task/044-ci-pipeline`
**Stage:** `git add .github/workflows/ci.yml pyproject.toml docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-044-ci-pipeline.md`
**Commit:** `git commit -m "Add GitHub Actions CI pipeline with lint, test, and dependency audit"`
