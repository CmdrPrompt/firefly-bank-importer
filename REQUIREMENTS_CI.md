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

## Acceptance criteria

- [ ] `.github/workflows/ci.yml`'s `uses:` line points at
      `CmdrPrompt/python-butler/.github/workflows/python-ci.yml@main`.
- [ ] The `with:` inputs are unchanged.
- [ ] A PR against this repo runs the `ci` job successfully end-to-end.
