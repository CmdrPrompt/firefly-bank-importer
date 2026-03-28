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

## Architecture & Design Principles

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
- Place tests in a `tests/` directory mirroring the `src/` structure
- Name test files `test_<module>.py` and test functions `test_<behavior>`
- Write tests at multiple levels: unit, integration
- Aim for high coverage but prioritize meaningful tests over coverage numbers
- Use fixtures and parametrize to avoid repetition
- Mock external dependencies (APIs, file system, databases)

```
tests/
  unit/
    test_<module>.py
  integration/
    test_<feature>.py
```

## Project Structure

```
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