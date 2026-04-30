# TASK-048 Fix CLAUDE.md.tmpl in python-butler to use project variable placeholders

## Status

todo

## Note

This task belongs to the **python-butler** project
(`https://github.com/CmdrPrompt/python-butler`), not to firefly-bank-importer.
It is tracked here because the need was discovered during the python-butler subtree
migration in this project.

## Description

`generate-governance-files` in `.butler/Makefile` runs `sed` substitutions for
`{{PROJECT_NAME}}`, `{{PROJECT_DESCRIPTION}}`, `{{REQUIREMENTS_PATH}}`,
`{{WORKFLOW_GUARDIAN_NAME}}`, `{{BUG_TRIAGE_NAME}}`, and `{{PROJECT_MAKE_TARGET}}`
against `.butler/templates/CLAUDE.md.tmpl`. However, the template file currently
contains the python-butler README rather than a project-scoped CLAUDE.md template
with those placeholders.

As a result, running `make generate-governance-files` in any adopting project
overwrites that project's `CLAUDE.md` with the python-butler README.

There is a second problem: even with a correct template, `generate-governance-files`
overwrites `CLAUDE.md` unconditionally. A project that has customised its `CLAUDE.md`
after initial scaffolding will lose those customizations on the next run. The `install`
target already guards against this (`[ -f CLAUDE.md ] || ...`), but
`generate-governance-files` itself does not.

## Acceptance criteria

- [ ] `.butler/templates/CLAUDE.md.tmpl` is a proper project-scoped CLAUDE.md
  template containing all supported placeholders:
  `{{PROJECT_NAME}}`, `{{PROJECT_DESCRIPTION}}`, `{{REQUIREMENTS_PATH}}`,
  `{{WORKFLOW_GUARDIAN_NAME}}`, `{{BUG_TRIAGE_NAME}}`, `{{PROJECT_MAKE_TARGET}}`
- [ ] `generate-governance-files` guards against overwriting an existing `CLAUDE.md`
  (and `copilot-instructions.md`) unless `FORCE=1` is passed:

  ```makefile
  @[ ! -f CLAUDE.md ] || [ "$(FORCE)" = "1" ] || \
      (echo "CLAUDE.md already exists. Run with FORCE=1 to overwrite."; exit 1)
  ```

- [ ] Running `make generate-governance-files PROJECT_NAME="firefly-bank-importer" ...`
  on a fresh project produces a correct, project-specific `CLAUDE.md`
- [ ] Running the same command on a project with an existing `CLAUDE.md` exits with
  the guard message unless `FORCE=1` is set
- [ ] The python-butler README is preserved as `README.md` (unaffected)
- [ ] `make generate-governance-files` is verified end-to-end in at least one
  adopting project (e.g. firefly-bank-importer) before merging

## Branch

**Branch name:** `task/048-fix-butler-claude-md-template`
**Switch/create:** `git checkout -b task/048-fix-butler-claude-md-template`
**Make target:** `make branch-task f=TASK-048`

## Completion

<!-- Fill in when done -->
**Date:**
**Summary:**
**Files changed:**
**Branch:**
**Stage:**
**Commit:**
