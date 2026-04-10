# python-commons

Shared infrastructure for Python projects — Makefile targets, and Claude Code agents.

## What's included

- **`Makefile`** — task workflow, linting, testing, and git targets built on [uv](https://github.com/astral-sh/uv)
- **`.github/agents/`** — Claude Code agents for spec-driven, TDD development

## Adopting in a project

Add as a subtree (one-time):

```bash
git subtree add --prefix=.commons \
  https://github.com/CmdrPrompt/python-commons.git main --squash
```

Then in your project's `Makefile`:

```makefile
include .commons/Makefile
```

Pull updates later:

```bash
git subtree pull --prefix=.commons \
  https://github.com/CmdrPrompt/python-commons.git main --squash
```

## Agents

| Agent | Purpose |
|---|---|
| `workflow-guardian` | Enforces requirements-first flow, task branches, TDD, and commit discipline |
| `implementation-worker` | Implements approved work inside the correct task branch |
| `bug-triage` | Hunts for bugs without fixing them — produces prioritised task files |
| `characterization-test-writer` | Documents existing untested behavior before refactoring |

## Governance Templates

The `.commons/templates/` folder contains shared templates for:

- `CLAUDE.md`
- `.github/copilot-instructions.md`

Generate project files from these templates:

```bash
make generate-governance-files
```

Override project-context values when needed:

```bash
make generate-governance-files \
  PROJECT_NAME="your-project" \
  PROJECT_DESCRIPTION="Describe your project context." \
  REQUIREMENTS_PATH="docs/REQUIREMENTS.md" \
  PROJECT_MAKE_TARGET="make web -- start local web server"
```

Generated files include a short header comment showing the template source and generation command.

## Conventions

- Tasks live in `docs/tasks/TASK-<NNN>-short-description.md`
- Every task runs on its own `task/<NNN>-short-description` branch
- Commits via `make commit-current-task` only — never `git commit` directly
- General workflow rules live in `~/.claude/CLAUDE.md`
