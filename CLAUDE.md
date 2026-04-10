<!-- Generated from .commons/templates/CLAUDE.md.tmpl via make generate-governance-files. -->

# CLAUDE.md - firefly-bank-importer

## Project Context

This project imports bank transactions from CSV exports (SEB, ICA, Nordea) into a [Firefly III](https://www.firefly-iii.org/) instance via its REST API.

**Primary source of truth:** `docs/REQUIREMENTS_import_firefly.md` - read it before
writing any code.

## Project-Specific Rules

- Do not write code before reading `docs/REQUIREMENTS_import_firefly.md`.
- Use the **Firefly Workflow Guardian** agent for task enforcement.
- Use the **Firefly Bug Triage** agent to hunt for bugs without fixing them.

## Project-Specific Make Targets

- `make web -- start firefly-import-web on http://127.0.0.1:8000`

<!-- All other workflow rules (TDD, task management, changelog, branch policy)
     are in ~/.claude/CLAUDE.md -->
