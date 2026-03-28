.PHONY: all help setup install lint fix test clean

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
	@echo "    make lint     -- Run ruff, mypy, pymarkdown and radon (cognitive complexity)"
	@echo "    make fix      -- Auto-fix ruff and pymarkdown issues"
	@echo "    make test     -- Run pytest with coverage"
	@echo "    make clean    -- Remove venv and cache"
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