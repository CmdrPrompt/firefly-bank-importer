# TASK-026 Refactor to reduce cyclomatic complexity

## Status
todo

## Description
Reduce cyclomatic complexity in functions flagged by Radon. As of task creation, the following functions exceed recommended thresholds:

- `config.py::load_firefly_url` -- C (cyclomatic 11)
- `web_ui.py::_build_dry_run_summary` -- E (cyclomatic 35, excessive)
- `web_ui.py::_load_web_firefly_settings` -- C (cyclomatic 11)
- `web_ui.py::_handle_csv_upload` -- C (cyclomatic 11)

Refactoring should follow SOLID principles: extract helper functions, reduce decision branches, and keep functions to a single responsibility.

**Note:** When starting this task, run `make lint` to check whether the reported complexity levels have changed since task creation. Document this in the completion summary.

## Acceptance criteria
- [ ] All flagged functions reduced below C (cyclomatic 8 or less)
- [ ] Radon reports no functions at C or above for src/firefly_bank_importer/
- [ ] All tests passing (make test)
- [ ] All linting checks passing (make lint)
- [ ] Refactored functions have improved readability with docstrings and type hints

## Branch
**Branch name:** `task/026-refactor-reduce-cyclomatic-complexity`
**Switch/create:** `git checkout -b task/026-refactor-reduce-cyclomatic-complexity`
**Make target:** `make branch-task f=TASK-026`

## Completion
(To be filled in when task is done)
