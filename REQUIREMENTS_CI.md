# Requirements: CI reusable workflow reference

## Context

`.github/workflows/ci.yml` calls a reusable workflow via:

```yaml
jobs:
  ci:
    uses: CmdrPrompt/python-commons/.github/workflows/python-ci.yml@main
```

`CmdrPrompt/python-commons` was renamed to `CmdrPrompt/python-butler`. GitHub's
repository-rename redirect does not reliably resolve for reusable-workflow
`uses:` references, so calls intermittently fail with "Invalid workflow
file ... workflow was not found" even though the underlying repo and file
still exist under the new name.

`python-butler` added `.github/workflows/python-ci.yml` (TASK-058, merged)
as a `workflow_call` reusable workflow with the same input contract this
repo already passes, specifically so consumer repos could repoint their
`uses:` line without changing their `with:` block.

## Goal

Repoint this repo's `uses:` target from the renamed `python-commons` repo to
`python-butler`, eliminating the intermittent "workflow was not found"
failure.

## Requirement 1: `ci.yml` calls the reusable workflow at its current location

**Description:** `.github/workflows/ci.yml`'s `ci` job uses
`CmdrPrompt/python-butler/.github/workflows/python-ci.yml@main` instead of
the `python-commons` path. The `with:` block (`python-version`,
`install-command`, `lint-command`, `test-command`, `audit-command`) is
unchanged.

**Use case:** A pull request is opened against `main`. The `ci` job resolves
`uses:` against `python-butler` (the repo's current name), runs
checkout → install → lint → test → audit, and no longer fails with a
"workflow file issue" caused by stale-name resolution.

## Requirement 2: `pip-audit` is installed for the Audit step

**Description:** `ci.yml`'s `audit-command` (`uv run pip-audit
--progress-spinner=off`) requires `pip-audit` to be resolvable by `uv run`,
which only sees packages declared in this project's dependencies.
`pyproject.toml`'s `[project.optional-dependencies] dev` list adds
`pip-audit` alongside `ruff`, `mypy`, `bandit`, `pymarkdownlnt`, and
`complexipy`, so `uv sync --extra dev` (the `install-command`) installs it
before the Audit step runs.

**Use case:** A pull request runs the reusable workflow's Audit step. `uv
run pip-audit --progress-spinner=off` finds `pip-audit` already installed
and runs the audit instead of failing with `Failed to spawn: pip-audit
... No such file or directory`.

## Requirement 3: Known-vulnerable transitive dependencies are patched

**Description:** With `pip-audit` runnable (Requirement 2), it reports 14
known vulnerabilities across 5 packages — `click` (8.3.1 → 8.3.3), `idna`
(3.11 → 3.15), `pytest` (9.0.2 → 9.0.3), `starlette` (1.0.0 → 1.3.1), and
`urllib3` (2.6.3 → 2.7.0). None of these are version-pinned in
`pyproject.toml` (they're transitive, or direct-but-unconstrained like
`"pytest"`), so `uv.lock` is upgraded to resolve each to at least its fix
version, with no `pyproject.toml` changes needed.

**Use case:** The CI Audit step (`uv run pip-audit --progress-spinner=off`)
runs against the locked dependency set and reports zero known
vulnerabilities, so the `ci` job's Audit step — and therefore the whole
`ci` job — passes.

## Acceptance criteria

- [ ] `.github/workflows/ci.yml`'s `uses:` line points at
      `CmdrPrompt/python-butler/.github/workflows/python-ci.yml@main`.
- [ ] The `with:` inputs are unchanged.
- [ ] A PR against this repo runs the `ci` job successfully end-to-end.
- [ ] `pyproject.toml`'s `dev` extra includes `pip-audit`, and `uv run
      pip-audit --progress-spinner=off` runs without a "Failed to spawn"
      error.
- [ ] `uv run pip-audit --progress-spinner=off` reports zero known
      vulnerabilities, and `uv.lock` pins `click>=8.3.3`, `idna>=3.15`,
      `pytest>=9.0.3`, `starlette>=1.3.1`, `urllib3>=2.7.0`.
