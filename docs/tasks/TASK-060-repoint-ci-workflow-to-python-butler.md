# TASK-060 Repoint ci.yml's reusable workflow reference to python-butler

## Status
done

## Requirements
**Binding:** Requirement 1 (REQUIREMENTS_CI.md)
**BDD mode:** BDD-ABSENT
**Depends on:** none
**Precedence:** The requirements document is the binding definition of this task.
The story and scenarios below are derived from it. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a maintainer of this repo, I want `ci.yml` to reference the reusable
workflow at its current repo name (`python-butler`) instead of the renamed
`python-commons`, so that CI stops intermittently failing with "workflow was
not found" and actually runs lint/test/audit on pull requests.

## Description
`CmdrPrompt/python-commons` was renamed to `CmdrPrompt/python-butler`
(confirmed same repo ID via `gh api`). `python-butler` added
`.github/workflows/python-ci.yml` in TASK-058 specifically so this repo could
repoint its `uses:` line. This task makes that one-line change.

## Branch
**Branch name:** `task/060-repoint-ci-workflow-to-python-butler`
**Switch/create:** `git checkout -b task/060-repoint-ci-workflow-to-python-butler`
**Make target:** `make branch-task f=TASK-060`

## Acceptance criteria (Gherkin)

- [ ] Scenario: ci.yml references the renamed repo
      Given `.github/workflows/ci.yml`'s `ci` job previously used `uses: CmdrPrompt/python-commons/.github/workflows/python-ci.yml@main`
      When the fix is applied
      Then the `uses:` line reads `CmdrPrompt/python-butler/.github/workflows/python-ci.yml@main` and the `with:` block is unchanged

## Out of scope
- Any change to `python-butler`'s reusable workflow itself (already merged, TASK-058).
- Changes to lint/test/audit commands or Python version.

## Blockers
None

## Completion
**Date:** 2026-08-01
**Summary:** Repointed `ci.yml`'s `uses:` line from `CmdrPrompt/python-commons/.github/workflows/python-ci.yml@main` to `CmdrPrompt/python-butler/.github/workflows/python-ci.yml@main` (same repo, renamed; `python-butler` added this reusable workflow in TASK-058). `with:` block unchanged.
**Files changed:**
- `.github/workflows/ci.yml` - modified
**Branch:** `git checkout task/060-repoint-ci-workflow-to-python-butler`
**Stage:** `git add .github/workflows/ci.yml CHANGELOG.md REQUIREMENTS_CI.md docs/tasks/TASK-060-repoint-ci-workflow-to-python-butler.md`
**Commit:** `git commit -m "Repoint ci.yml's reusable workflow reference from python-commons to python-butler"`
