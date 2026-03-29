.PHONY: all help setup install lint fix stage branch-task stage-task commit-task pr-task web test clean

TASKS_DIR := docs/tasks

all: help

## Show this help text
help:
	@echo ""
	@echo "Available commands:"
	@echo ""
	@echo "  First time on a new machine:"
	@echo "    make setup    -- Install uv (if missing)"
	@echo "    make install  -- Create venv, install dependencies and activate pre-commit"
	@echo ""
	@echo "  Daily use:"
	@echo "    make lint        -- Run ruff, mypy, bandit, pymarkdown and complexipy (cognitive complexity)"
	@echo "    make fix         -- Auto-fix ruff and pymarkdown issues"
	@echo "    make stage       -- Auto-fix and re-stage all staged changes (run before git commit)"
	@echo "    make branch-task -- Create/switch task branch from task file: make branch-task f=TASK-001"
	@echo "    make stage-task  -- Auto-fix and stage files listed in task file: make stage-task f=TASK-001"
	@echo "    make commit-task -- Commit using message from task file: make commit-task f=TASK-001"
	@echo "    make pr-task     -- Switch to task branch and open GitHub PR: make pr-task f=TASK-001"
	@echo "    make web         -- Start firefly-import-web on http://127.0.0.1:8000"
	@echo "    make test        -- Run pytest with coverage"
	@echo "    make clean       -- Remove venv and cache"
	@echo ""
	@echo "  Commit workflow for a task:"
	@echo "    make branch-task f=TASK-001  # create/switch to task branch from task file"
	@echo "    make stage-task f=TASK-001   # fix + stage files listed in task"
	@echo "    git diff --staged            # optional: review before committing"
	@echo "    make commit-task f=TASK-001  # commit with message from task file"
	@echo "    make pr-task f=TASK-001      # open PR on GitHub with task title + body"
	@echo ""

## Install uv if missing (run once per machine)
setup:
	@which uv > /dev/null 2>&1 && echo "✓ uv already installed" || (curl -LsSf https://astral.sh/uv/install.sh | sh && echo "✓ uv installed")

## Create virtual environment and install dependencies
install:
	uv sync --extra dev
	uv run pre-commit install
	@echo "✓ Environment ready"

## Run linters
lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src/
	uv run bandit -r src/ -c pyproject.toml
	uv run pymarkdown --config .pymarkdown scan $(shell find . -name "*.md" -not -path "./.venv/*" -not -path "./.github/*")
	uv run complexipy src/

## Auto-fix ruff and pymarkdown issues
fix:
	uv run ruff check --fix .
	uv run ruff format .
	uv run pymarkdown --config .pymarkdown fix $(shell find . -name "*.md" -not -path "./.venv/*" -not -path "./.github/*")

## Auto-fix and re-stage already-staged files (run before git commit)
stage:
	@STAGED=$$(git diff --name-only --cached); \
	uv run ruff check --fix .; \
	uv run ruff format .; \
	uv run pymarkdown --config .pymarkdown fix $$(find . -name "*.md" -not -path "./.venv/*"); \
	[ -n "$$STAGED" ] && echo "$$STAGED" | xargs git add -- || true; \
	git update-index -q --refresh

## Create/switch task branch from task file: make branch-task f=TASK-001
branch-task:
	@[ -n "$(f)" ] || (echo "Usage: make branch-task f=<task-id-or-filename>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	CMD=$$(grep '\*\*Branch:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	[ -n "$$CMD" ] || (echo "No **Branch:** line found in $$TASK_FILE"; exit 1); \
	echo "Running: $$CMD"; \
	if eval "$$CMD"; then \
		true; \
	else \
		ALT_CMD=$$(echo "$$CMD" | sed 's/^git checkout -b /git checkout /'); \
		if [ "$$ALT_CMD" != "$$CMD" ]; then \
			echo "Branch may already exist. Running: $$ALT_CMD"; \
			eval "$$ALT_CMD"; \
		else \
			exit 1; \
		fi; \
	fi

## Auto-fix and stage files listed in a task file: make stage-task f=TASK-001
stage-task:
	@[ -n "$(f)" ] || (echo "Usage: make stage-task f=<task-id-or-filename>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	CMD=$$(grep '\*\*Stage:\*\*' "$$TASK_FILE" | sed 's/.*`\(git add[^`]*\)`.*/\1/'); \
	[ -n "$$CMD" ] || (echo "No **Stage:** line found in $$TASK_FILE"; exit 1); \
	uv run ruff check --fix .; \
	uv run ruff format .; \
	uv run pymarkdown --config .pymarkdown fix $$(find . -name "*.md" -not -path "./.venv/*"); \
	echo "Running: $$CMD"; \
	eval "$$CMD"; \
	git update-index -q --refresh

## Commit using message from task file: make commit-task f=TASK-001
commit-task:
	@[ -n "$(f)" ] || (echo "Usage: make commit-task f=<task-id-or-filename>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	MSG=$$(grep '\*\*Commit:\*\*' "$$TASK_FILE" | sed 's/.*`git commit -m "\(.*\)"`.*/\1/'); \
	[ -n "$$MSG" ] || (echo "No **Commit:** line found in $$TASK_FILE"; exit 1); \
	echo "Running: git commit -m \"$$MSG\""; \
	git commit -m "$$MSG"

## Open a GitHub PR using task title and description: make pr-task f=TASK-001
pr-task:
	@[ -n "$(f)" ] || (echo "Usage: make pr-task f=<task-id-or-filename>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	BRANCH_CMD=$$(grep '\*\*Branch:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	if [ -n "$$BRANCH_CMD" ]; then \
		echo "Running: $$BRANCH_CMD"; \
		if ! eval "$$BRANCH_CMD"; then \
			ALT_CMD=$$(echo "$$BRANCH_CMD" | sed 's/^git checkout -b /git checkout /'); \
			if [ "$$ALT_CMD" != "$$BRANCH_CMD" ]; then \
				echo "Branch may already exist. Running: $$ALT_CMD"; \
				eval "$$ALT_CMD"; \
			else \
				exit 1; \
			fi; \
		fi; \
	else \
		TASK_BASE=$$(basename "$$TASK_FILE" .md); \
		TARGET_BRANCH=$$(echo "$$TASK_BASE" | sed 's/^TASK-//' | tr '[:upper:]' '[:lower:]' | sed 's#^#task/#'); \
		CURRENT_BRANCH=$$(git branch --show-current); \
		if [ "$$CURRENT_BRANCH" != "$$TARGET_BRANCH" ]; then \
			echo "Switching to inferred task branch: $$TARGET_BRANCH"; \
			git checkout "$$TARGET_BRANCH" || git checkout -b "$$TARGET_BRANCH"; \
		fi; \
	fi; \
	TITLE=$$(head -1 "$$TASK_FILE" | sed 's/^# //'); \
	BODY=$$(awk '/^## Description/{found=1} /^## Completion/{found=0} found{print}' "$$TASK_FILE"); \
	[ -n "$$TITLE" ] || (echo "Could not extract title from $$TASK_FILE"; exit 1); \
	echo "Creating PR: $$TITLE"; \
	gh pr create --title "$$TITLE" --body "$$BODY" --base main; \
	git checkout main

## Start web UI
web:
	uv run firefly-import-web

## Run tests with coverage
test:
	uv run pytest --cov=src --cov-report=term-missing

## Remove venv and cache
clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	@echo "✓ Done"