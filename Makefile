.PHONY: all help setup install lint fix stage stage-task commit-task test clean

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
	@echo "    make lint        -- Run ruff, mypy, pymarkdown and radon (cognitive complexity)"
	@echo "    make fix         -- Auto-fix ruff and pymarkdown issues"
	@echo "    make stage       -- Auto-fix and re-stage all staged changes (run before git commit)"
	@echo "    make stage-task  -- Auto-fix and stage files listed in task file: make stage-task f=TASK-001"
	@echo "    make commit-task -- Commit using message from task file: make commit-task f=TASK-001"
	@echo "    make test        -- Run pytest with coverage"
	@echo "    make clean       -- Remove venv and cache"
	@echo ""
	@echo "  Commit workflow for a task:"
	@echo "    make stage-task f=TASK-001   # fix + stage files listed in task"
	@echo "    git diff --staged            # optional: review before committing"
	@echo "    make commit-task f=TASK-001  # commit with message from task file"
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
	uv run pymarkdown --config .pymarkdown scan $(shell find . -name "*.md" -not -path "./.venv/*")
	uv run radon cc src/ --min C --show-complexity

## Auto-fix ruff and pymarkdown issues
fix:
	uv run ruff check --fix .
	uv run ruff format .
	uv run pymarkdown --config .pymarkdown fix $(shell find . -name "*.md" -not -path "./.venv/*")

## Auto-fix and re-stage already-staged files (run before git commit)
stage:
	@STAGED=$$(git diff --name-only --cached); \
	uv run ruff check --fix .; \
	uv run ruff format .; \
	uv run pymarkdown --config .pymarkdown fix $$(find . -name "*.md" -not -path "./.venv/*"); \
	[ -n "$$STAGED" ] && echo "$$STAGED" | xargs git add -- || true; \
	git update-index -q --refresh

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