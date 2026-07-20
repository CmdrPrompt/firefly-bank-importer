# TASK-052 Fix pyproject.toml regression from .butler submodule migration

## Status

in-progress

## Description

Commit `e291ea3` ("feat: add submodule for .butler and update project
dependencies") overwrote `pyproject.toml` with a generic `.butler` scaffold
template, silently dropping project-critical configuration:

- `dependencies` (fastapi, firefly-python-api, httpx, python-multipart,
  requests, uvicorn) — was reduced to an empty list.
- `[tool.uv.sources]` pointing `firefly-python-api` at the local
  `libs/firefly-python-api` subtree.
- `[project.scripts]` CLI entry points (`firefly-import`,
  `firefly-import-web`).
- `[[tool.mypy.overrides]]` for fastapi/uvicorn/firefly_python_api and
  `[tool.coverage.*]` settings.

It also introduced a TOML syntax error (`project.optional-dependencies]`
missing its leading `[`), which broke `uv pip install -e .` and therefore
`make install` / `make branch-task` entirely, and silently dropped
`tool.ruff.line-length` from 120 to 100, which made `make lint` fail with
104 pre-existing line-length violations across the codebase.

Discovered while preparing to branch for TASK-051 (`make branch-task` failed
because `uv pip install -e .` could not parse `pyproject.toml`).

Fix: restore the dropped configuration, merged with the new `.butler`-added
dev dependencies (bandit, pymarkdownlnt, complexipy pinning) and the new
setuptools-based build backend, which are kept as-is.

## Branch

**Branch name:** `task/052-fix-pyproject-regression`
**Switch/create:** `git checkout -b task/052-fix-pyproject-regression`
**Make target:** `make branch-task f=TASK-052`

## Acceptance criteria

- [x] `pyproject.toml` is valid TOML and `uv pip install -e .` succeeds.
- [x] `dependencies`, `[tool.uv.sources]`, `[project.scripts]`,
  `[[tool.mypy.overrides]]`, and `[tool.coverage.*]` are restored.
- [x] `make install` succeeds and installs firefly-python-api, requests,
  fastapi, uvicorn, httpx, python-multipart into the venv.
- [x] `make test` passes with no regression.
- [x] `make lint` passes with no regression.

## Blockers

None

## Completion

**Date:** 2026-07-20
**Summary:** Restored dependencies, `[tool.uv.sources]`, CLI entry points, mypy overrides, coverage config, and `tool.ruff.line-length` (120) in `pyproject.toml` that were accidentally dropped when `.butler` was integrated (commit e291ea3), and fixed the resulting TOML syntax error that broke `uv`/`make install`/`make branch-task`. Kept the `.butler`-added dev dependencies and setuptools build backend.
**Files changed:**

- `pyproject.toml` — modified
- `uv.lock` — modified

**Branch:** `git checkout task/052-fix-pyproject-regression`
**Stage:** `git add pyproject.toml uv.lock docs/tasks/TASK-052-fix-pyproject-regression.md`
**Commit:** `git commit -m "Restore dependencies and config lost in pyproject.toml regression (TASK-052)"`
