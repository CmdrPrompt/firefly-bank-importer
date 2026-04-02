# TASK-042 Trim CLAUDE.md and move task template to workflow guardian agent

## Status
in-progress

## Description
CLAUDE.md had grown to 374 lines with sections that duplicate config files, contain
stale content, or describe generic practices Claude already follows. Trim it to only
process rules that are non-obvious or project-specific, and move the task file template
into the Firefly Workflow Guardian agent where it belongs.

## Branch
**Branch name:** `task/042-trim-claude-md`
**Switch/create:** `git checkout -b task/042-trim-claude-md`
**Make target:** `make branch-task f=TASK-042`

## Acceptance criteria
- [x] "Adding Tests to Untested Code" section removed (stale — project now has tests)
- [x] "Architecture & Design Principles / SOLID" section removed (generic)
- [x] "Project Structure" tree removed (derivable from code)
- [x] "Dependency Management" section removed (standard uv usage)
- [x] "Code Quality Tools" section with toml/yaml snippets removed (DRY — already in config files)
- [x] "Testing conventions" bullet list removed (mostly derivable)
- [x] Task file template moved to firefly-workflow-guardian.agent.md
- [x] CLAUDE.md reduced to process rules, workflow commands, changelog style, and prohibitions
- [x] bug-triage agent trimmed: task template replaced with reference to Guardian, step prose condensed (126 → 81 lines)
- [x] characterization-test-writer agent trimmed: duplicate prioritization list removed, step prose condensed (84 → 58 lines)

## Completion
**Date:** 2026-04-02
**Summary:** Reduced CLAUDE.md from 374 to 81 lines by removing stale, generic, and duplicate
content. Moved the task file template to the Workflow Guardian agent. Condensed bug-triage
and characterization-test-writer agents (370 → 299 lines total) without removing functionality.
**Files changed:**
- `CLAUDE.md` — modified: major trim
- `.github/agents/firefly-workflow-guardian.agent.md` — modified: added Task File Format section with template
- `.github/agents/firefly-bug-triage.agent.md` — modified: condensed, task template replaced with reference to Guardian
- `.github/agents/firefly-characterization-test-writer.agent.md` — modified: condensed
- `docs/tasks/TASK-042-trim-claude-md.md` — created
**Branch:** `git checkout task/042-trim-claude-md`
**Stage:** `git add CLAUDE.md .github/agents/firefly-workflow-guardian.agent.md .github/agents/firefly-bug-triage.agent.md .github/agents/firefly-characterization-test-writer.agent.md docs/tasks/TASK-042-trim-claude-md.md`
**Commit:** `git commit -m "Trim CLAUDE.md and condense agent files"`
