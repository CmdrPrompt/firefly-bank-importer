# CLAUDE.md - Python Development Guidelines

## Project Context

This project is a CLI tool (`import_firefly.py`) that imports bank transactions from
CSV exports (SEB and ICA formats) into a [Firefly III](https://www.firefly-iii.org/)
instance via its REST API.

Key capabilities:

- Imports transactions from one or more account folders using the API token in `token`.
- Detects and splits multi-month CSV exports into monthly `YYYY-MM.csv` files before import.
- Discovers asset accounts from Firefly and caches them locally in `accounts_cache.json`.
- Resolves folder-to-account mapping by case-insensitive substring matching against cached account names.
- Prevents duplicate imports by skipping rows with dates ≤ the latest transaction date already in Firefly.
- Supports `--dry-run`, `--ignore-latest-date-check`, and `--refresh-accounts` flags.
- Uses a thread pool (`MAX_WORKERS = 5`) for parallel API posting.

Before writing any code, read the requirements specification in `docs/REQUIREMENTS_import_firefly.md`. Use it as the
primary source of truth for what is being built, expected behavior, and scope.

## Spec-Driven Development

All changes and additions to the application must be grounded in the requirements specification.

**Before writing any code for a new feature or change:**

1. Update `docs/REQUIREMENTS_import_firefly.md` with the relevant requirement(s) and use case(s)
2. Present the updated requirement and use case to the user and ask: "Is this what you intended?"
3. Wait for explicit confirmation before proceeding to write any code
4. Only then follow the TDD cycle to implement the confirmed requirement

If a proposed change cannot be clearly expressed as a requirement and use case, it should not be implemented.

## Task Management

Tasks are tracked as individual files in `docs/tasks/`. Each file represents one task.

**File naming:** `TASK-001-short-description.md`

**Task file template:**

```markdown
# TASK-001 Short description

## Status
todo | in-progress | done

## Description
What needs to be done and why.

## Acceptance criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Completion
**Date:** YYYY-MM-DD
**Summary:** What was done, any decisions made, and what was left out and why.
**Files changed:**
- `path/to/file` — created / modified
```

When starting a task, update `Status` to `in-progress`. When done, update `Status` to
`done` and fill in the `Completion` section with date, a brief summary, and a list of
all files that were created or modified before committing.

New tasks can be created by the user, by Claude Code, or by another LLM. Claude Code
should check `docs/tasks/` for open tasks relevant to the current context before starting work.

## Adding Tests to Untested Code

The existing codebase has no unit tests. When adding tests to untested functionality,
follow this workflow rather than the standard TDD cycle:

1. **Analyse** the function or module to understand its current behavior -- do not assume it is correct
2. **Write characterisation tests** that document the current behavior as-is, to establish a safety net
3. **Present the tests** to the user before committing -- note any behavior that looks incorrect or surprising
4. **Refactor** only after characterisation tests are in place and confirmed
5. **Replace** characterisation tests with proper requirement-driven tests during refactoring

**Prioritisation order** for adding tests (highest risk first):

1. Date parsing and duplicate-detection logic
2. CSV parsing and format detection (SEB vs ICA)
3. Account name matching and cache logic
4. API posting and error handling
5. CLI argument handling and flag logic

Use Hypothesis for all parsing and data transformation functions -- generate inputs
rather than hand-picking them.

Create a task file in `docs/tasks/` for each area of untested code before starting work.

## Architecture & Design Principles

### SOLID

- Follow **SOLID** principles and write clean, readable code
- Prefer **composition over inheritance**
- Keep functions and classes small with single responsibilities
- Use **dependency injection** to improve testability and flexibility
- Avoid premature optimization; favor clarity first
- Use **type hints** on all functions and class attributes

## Test-Driven Development (TDD)

Always follow the TDD cycle: **Red -> Green -> Refactor**

1. Write a failing test that describes the intended behavior
2. Write the minimum code to make it pass
3. Refactor while keeping tests green

### Testing conventions

- Use **pytest** as the default test runner
- Use **Hypothesis** for property-based testing of parsing logic, date handling, and data transformations
- Place tests in a `tests/` directory mirroring the `src/` structure
- Name test files `test_<module>.py` and test functions `test_<behavior>`
- Write tests at multiple levels: unit, integration
- Aim for high coverage but prioritize meaningful tests over coverage numbers
- Use fixtures and parametrize to avoid repetition
- Use `@given` and `@settings` from Hypothesis for input fuzzing on parsing and validation logic
- Mock external dependencies (APIs, file system, databases)

```text
tests/
  unit/
    test_<module>.py
  integration/
    test_<feature>.py
```

## Project Structure

```text
firefly-bank-importer/
  src/
    firefly_bank_importer/
      __init__.py
      import_firefly.py    # Main CLI entry point
  tests/
    unit/
    integration/
  docs/                    # Requirements and specifications -- read before coding
  bankImports/             # Input folder for CSV exports
  logs/
  token                    # API token (not committed)
  accounts_cache.json      # Cached Firefly account list (generated, not committed)
  pyproject.toml
  uv.lock
  CLAUDE.md
  .pre-commit-config.yaml
```

## Dependency Management

- Use **uv** with `pyproject.toml` for all dependency management
- Runtime dependencies under `[project.dependencies]`
- Dev dependencies under `[project.optional-dependencies] dev`
- Commit `uv.lock` to Git for reproducible builds
- Add dependencies with `uv add <package>` and dev dependencies with `uv add --dev <package>`
- Never add dependencies without a clear reason tied to requirements

## Code Quality Tools

### ruff

Used for both **linting and formatting**. Configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
```

Run before committing: `ruff check . && ruff format .`

### mypy

Used for **static type checking**. Configuration in `pyproject.toml`:

```toml
[tool.mypy]
strict = true
python_version = "3.11"
```

Run: `mypy src/`

### coverage.py

Track test coverage with a minimum threshold. Configuration in `pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

Run: `pytest --cov=src --cov-report=term-missing`

### pre-commit

Used to **automatically run ruff and mypy before every commit**. If any check fails,
the commit is aborted until the issues are fixed.

Install the tool and activate hooks once per project:

```bash
uv run pre-commit install
```

The hooks are defined in `.pre-commit-config.yaml` in the project root:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.4
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--strict]
        additional_dependencies: []  # add stubs here if needed
```

Add `pre-commit` to dev dependencies: `uv add --dev pre-commit`

> Note: coverage.py is intentionally excluded from pre-commit hooks since running
> the full test suite on every commit is too slow. Run it manually or in CI instead.

## Code Style

- Follow **PEP 8** (enforced by ruff)
- Use **Google-style docstrings** for public functions and classes
- Prefer `pathlib.Path` over `os.path`
- Use `dataclasses` or `pydantic` for structured data
- Avoid wildcard imports (`from x import *`)
- Handle exceptions explicitly -- never use bare `except:`

## Workflow

Pre-commit hooks run ruff and mypy automatically on every `git commit`. Run the full chain manually before pushing:

```bash
uv run ruff check . && uv run ruff format .
uv run mypy src/
uv run pytest --cov=src --cov-report=term-missing
```

Or via Makefile: `make lint && make test`

## What NOT to do

- Do not write code before reading `docs/`
- Do not skip writing tests first (TDD)
- Do not write code before updating and confirming the requirements specification
- Do not commit code that fails ruff, mypy, or pytest
- Do not add dependencies not covered by requirements
- Do not suppress type errors with `# type: ignore` without explanation
