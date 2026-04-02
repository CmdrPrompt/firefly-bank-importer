.PHONY: all help setup install lint fix stage branch-task stage-task commit-task \
        pr-task merge-pr stage-current-task commit-current-task pr-current-task \
        merge-current-task test clean clean-complexity

TASKS_DIR ?= docs/tasks

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
	@echo "    make lint     -- Run ruff, mypy, bandit, pymarkdown and complexipy"
	@echo "    make fix      -- Auto-fix ruff and pymarkdown issues"
	@echo "    make stage    -- Auto-fix and re-stage all staged changes"
	@echo "    make test     -- Run pytest with coverage"
	@echo ""
	@echo "  Task workflow (explicit task ID):"
	@echo "    make branch-task f=TASK-001  -- Create/switch to task branch"
	@echo "    make stage-task f=TASK-001   -- Fix + stage files listed in task"
	@echo "    make commit-task f=TASK-001  -- Commit with message from task file"
	@echo "    make pr-task f=TASK-001      -- Open PR on GitHub"
	@echo "    make merge-pr f=TASK-001     -- Squash-merge PR, pull main"
	@echo ""
	@echo "  Task workflow (current branch):"
	@echo "    make stage-current-task      -- Fix + stage files for current task"
	@echo "    make commit-current-task     -- Commit for current task"
	@echo "    make pr-current-task         -- Open PR for current task"
	@echo "    make merge-current-task      -- Squash-merge PR, pull main"
	@echo ""

## Install uv if missing (run once per machine)
setup:
	@which uv > /dev/null 2>&1 && echo "✓ uv already installed" || \
		(curl -LsSf https://astral.sh/uv/install.sh | sh && echo "✓ uv installed")

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
	uv run pymarkdown --config .pymarkdown scan \
		$(shell find . -name "*.md" -not -path "./.venv/*" -not -path "./.github/*")
	uv run complexipy src/ -mx 15 -s desc -j || \
		(uv run python scripts/explain_complexipy_failures.py --max 15 && exit 1)

## Auto-fix ruff and pymarkdown issues
fix:
	uv run ruff check --fix .
	uv run ruff format .
	uv run pymarkdown --config .pymarkdown fix \
		$(shell find . -name "*.md" -not -path "./.venv/*" -not -path "./.github/*")

## Auto-fix and re-stage already-staged files (run before git commit)
stage:
	@STAGED=$$(git diff --name-only --cached); \
	uv run ruff check --fix .; \
	uv run ruff format .; \
	uv run pymarkdown --config .pymarkdown fix \
		$$(find . -name "*.md" -not -path "./.venv/*"); \
	[ -n "$$STAGED" ] && echo "$$STAGED" | xargs git add -- || true; \
	git update-index -q --refresh

## Create/switch task branch from task file: make branch-task f=TASK-001
branch-task:
	@[ -n "$(f)" ] || (echo "Usage: make branch-task f=<task-id>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	CMD=$$(grep '\*\*Switch/create:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	[ -n "$$CMD" ] || CMD=$$(grep '\*\*Branch:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	[ -n "$$CMD" ] || (echo "No **Switch/create:** or **Branch:** line found in $$TASK_FILE"; exit 1); \
	echo "Running: $$CMD"; \
	if eval "$$CMD"; then true; else \
		ALT=$$(echo "$$CMD" | sed 's/^git checkout -b /git checkout /'); \
		[ "$$ALT" != "$$CMD" ] && eval "$$ALT" || exit 1; \
	fi

## Auto-fix and stage files listed in a task file: make stage-task f=TASK-001
stage-task:
	@[ -n "$(f)" ] || (echo "Usage: make stage-task f=<task-id>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	CMD=$$(grep '\*\*Stage:\*\*' "$$TASK_FILE" | sed 's/.*`\(git add[^`]*\)`.*/\1/'); \
	[ -n "$$CMD" ] || (echo "No **Stage:** line found in $$TASK_FILE"; exit 1); \
	uv run ruff check --fix .; \
	uv run ruff format .; \
	uv run pymarkdown --config .pymarkdown fix \
		$$(find . -name "*.md" -not -path "./.venv/*"); \
	echo "Running: $$CMD"; \
	eval "$$CMD"; \
	git update-index -q --refresh

## Commit using message from task file: make commit-task f=TASK-001
commit-task:
	@[ -n "$(f)" ] || (echo "Usage: make commit-task f=<task-id>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	MSG=$$(grep '\*\*Commit:\*\*' "$$TASK_FILE" | sed 's/.*`git commit -m "\(.*\)"`.*/\1/'); \
	[ -n "$$MSG" ] || (echo "No **Commit:** line found in $$TASK_FILE"; exit 1); \
	echo "Running: git commit -m \"$$MSG\""; \
	git commit -m "$$MSG"

## Auto-fix and stage files for the current task branch
stage-current-task:
	@BRANCH=$$(git branch --show-current); \
	NUM=$$(echo "$$BRANCH" | sed -n 's#^task/\([0-9][0-9][0-9]\)-.*#\1#p'); \
	[ -n "$$NUM" ] || (echo "Not on a task branch (expected task/<NNN>-...)"; exit 1); \
	$(MAKE) stage-task f=TASK-$$NUM

## Commit using task file metadata for the current task branch
commit-current-task:
	@BRANCH=$$(git branch --show-current); \
	NUM=$$(echo "$$BRANCH" | sed -n 's#^task/\([0-9][0-9][0-9]\)-.*#\1#p'); \
	[ -n "$$NUM" ] || (echo "Not on a task branch (expected task/<NNN>-...)"; exit 1); \
	$(MAKE) commit-task f=TASK-$$NUM

## Open a GitHub PR using task title and description: make pr-task f=TASK-001
pr-task:
	@[ -n "$(f)" ] || (echo "Usage: make pr-task f=<task-id>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	CMD=$$(grep '\*\*Switch/create:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	[ -n "$$CMD" ] || CMD=$$(grep '\*\*Branch:\*\*' "$$TASK_FILE" | sed 's/.*`\(git checkout[^`]*\)`.*/\1/' | head -1); \
	if [ -n "$$CMD" ]; then \
		eval "$$CMD" || eval "$$(echo "$$CMD" | sed 's/^git checkout -b /git checkout /')"; \
	fi; \
	TITLE=$$(head -1 "$$TASK_FILE" | sed 's/^# //'); \
	BODY=$$(awk '/^## Description/{f=1} /^## Completion/{f=0} f{print}' "$$TASK_FILE"); \
	[ -n "$$TITLE" ] || (echo "Could not extract title from $$TASK_FILE"; exit 1); \
	echo "Creating PR: $$TITLE"; \
	git push -u origin HEAD; \
	gh pr create --title "$$TITLE" --body "$$BODY" --base main; \
	git checkout main

## Open PR using task file metadata for the current task branch
pr-current-task:
	@BRANCH=$$(git branch --show-current); \
	NUM=$$(echo "$$BRANCH" | sed -n 's#^task/\([0-9][0-9][0-9]\)-.*#\1#p'); \
	[ -n "$$NUM" ] || (echo "Not on a task branch (expected task/<NNN>-...)"; exit 1); \
	$(MAKE) pr-task f=TASK-$$NUM

## Squash-merge the open PR for a task branch: make merge-pr f=TASK-001
merge-pr:
	@[ -n "$(f)" ] || (echo "Usage: make merge-pr f=<task-id>"; exit 1)
	@TASK_FILE=$$(find $(TASKS_DIR) -name "$(f)*.md" | head -1); \
	[ -n "$$TASK_FILE" ] || (echo "No task file found matching '$(f)' in $(TASKS_DIR)"; exit 1); \
	BRANCH=$$(echo "$$(basename "$$TASK_FILE" .md)" | \
		sed 's/^\(TASK-[0-9]*\)-/task\/\1-/' | tr '[:upper:]' '[:lower:]'); \
	PR=$$(gh pr list --head "$$BRANCH" --json number --jq '.[0].number' 2>/dev/null); \
	[ -n "$$PR" ] || (echo "No open PR for branch $$BRANCH"; exit 1); \
	STATE=$$(gh pr view "$$PR" --json mergeable --jq '.mergeable'); \
	[ "$$STATE" = "MERGEABLE" ] || (echo "PR #$$PR not mergeable ($$STATE)"; exit 1); \
	gh pr merge "$$PR" --squash --delete-branch; \
	git checkout main; \
	git pull

## Squash-merge the open PR for the current task branch, then pull main
merge-current-task:
	@BRANCH=$$(git branch --show-current); \
	NUM=$$(echo "$$BRANCH" | sed -n 's#^task/\([0-9][0-9][0-9]\)-.*#\1#p'); \
	[ -n "$$NUM" ] || (echo "Not on a task branch (expected task/<NNN>-...)"; exit 1); \
	$(MAKE) merge-pr f=TASK-$$NUM

## Run tests with coverage
test:
	uv run pytest --cov=src --cov-report=term-missing

## Remove generated complexipy artifacts
clean-complexity:
	rm -rf .complexipy_cache
	rm -f complexipy_results_*.json
	@echo "✓ Removed complexipy artifacts"

## Remove venv and cache
clean:
	$(MAKE) clean-complexity
	rm -rf .venv
	find . -type d \( -name "__pycache__" -o -name ".mypy_cache" \
		-o -name ".ruff_cache" -o -name ".pytest_cache" -o -name "*.egg-info" \) \
		-exec rm -rf {} +
	@echo "✓ Done"
