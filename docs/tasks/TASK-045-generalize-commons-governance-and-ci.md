# TASK-045 Generalize .commons governance and reusable CI baseline

## Status
done

## Description
Extract reusable governance rules into `.commons` so related repositories can share the
same workflow and AI-instruction baseline. Keep project-level differences limited to
explicit context values and a thin local CI wrapper.

## Branch
**Branch name:** `task/045-generalize-commons-governance-and-ci`
**Switch/create:** `git checkout -b task/045-generalize-commons-governance-and-ci`
**Make target:** `make branch-task f=TASK-045`

## Acceptance criteria
- [x] Shared templates exist for `CLAUDE.md` and `.github/copilot-instructions.md` with project-context placeholders only.
- [x] Repository docs explain how to generate project files from `.commons` templates.
- [x] `.github/workflows/ci.yml` is structured as a thin wrapper that can call a reusable CI workflow.
- [x] The requirements spec documents reusable-governance and reusable-CI behavior.
- [x] `make lint && make test` pass.

## Completion
**Date:** 2026-04-10
**Summary:** Added shared governance templates and a reproducible generation target in `.commons`, regenerated local governance files with template-source headers, and converted CI into a thin reusable-workflow wrapper.
**Files changed:**
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `.commons/README.md` — modified
- `.commons/Makefile` — modified
- `.commons/templates/CLAUDE.md.tmpl` — added
- `.commons/templates/copilot-instructions.md.tmpl` — added
- `.github/workflows/ci.yml` — modified
- `.github/copilot-instructions.md` — modified
- `CLAUDE.md` — modified
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-045-generalize-commons-governance-and-ci.md` — modified
**Branch:** `git checkout task/045-generalize-commons-governance-and-ci`
**Stage:** `git add docs/REQUIREMENTS_import_firefly.md .commons/README.md .commons/Makefile .commons/templates/CLAUDE.md.tmpl .commons/templates/copilot-instructions.md.tmpl .github/workflows/ci.yml .github/copilot-instructions.md CLAUDE.md CHANGELOG.md docs/tasks/TASK-045-generalize-commons-governance-and-ci.md`
**Commit:** `git commit -m "Generalize commons governance templates and reusable CI baseline"`
