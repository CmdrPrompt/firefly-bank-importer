# TASK-002 Configurable Firefly URL and token

## Status

done

## Description

The Firefly III base URL is currently hardcoded in `import_firefly.py`.
The API token is read from a plain `token` file.
Both should instead be stored in local files that are created interactively
on first run, so the user never needs to edit source code.

Relevant requirements: UC-12, FR-1 (updated), FR-29, FR-30, FR-31.

## Acceptance criteria

- [x] Firefly URL is read from `config.json` at startup.
- [x] If `config.json` is missing or contains no URL, the script prompts the user
  interactively, validates the URL against `/api/v1/about`, and saves it.
- [x] API token is read from `secrets.json` at startup.
- [x] If `secrets.json` is missing, the script falls back to the legacy `token` file.
- [x] If neither exists, the script prompts the user with hidden input and saves the
  token to `secrets.json`.
- [x] `--configure` flag forces the interactive flow for both URL and token,
  overwriting existing values.
- [x] `secrets.json` is listed in `.gitignore`.
- [x] `FIREFLY_URL` constant is removed from source code.
- [x] All new code passes `make lint` and `make test`.

## Completion

**Date:** 2026-03-28
**Summary:** Created `config.py` module with `validate_firefly_url`, `load_firefly_url`,
and `load_api_token` functions using dependency injection for testability. Removed the
hardcoded `FIREFLY_URL` constant and `get_token()` from `import_firefly.py`; threaded
`firefly_url: str` through all API-calling functions. Added `--configure` flag to
`_parse_cli_args` (now returns a 5-tuple). Updated all affected tests. Added both
`secrets.json` and `config.json` to `.gitignore`. 27 new config tests written TDD.
**Files changed:**
- `src/firefly_bank_importer/config.py` — created
- `src/firefly_bank_importer/import_firefly.py` — modified
- `tests/unit/test_config.py` — created
- `tests/unit/test_cli_args.py` — modified
- `tests/unit/test_build_account_map.py` — modified
- `tests/unit/test_date_parsing.py` — modified
- `tests/unit/test_process_csv.py` — modified
- `tests/unit/test_process_folder.py` — modified
- `.gitignore` — modified
**Stage:** `git add src/firefly_bank_importer/config.py src/firefly_bank_importer/import_firefly.py tests/unit/test_config.py tests/unit/test_cli_args.py tests/unit/test_build_account_map.py tests/unit/test_date_parsing.py tests/unit/test_process_csv.py tests/unit/test_process_folder.py .gitignore docs/tasks/TASK-002-configurable-url-and-token.md`
**Commit:** `git commit -m "Add configurable Firefly URL and token via config.json and secrets.json"`
