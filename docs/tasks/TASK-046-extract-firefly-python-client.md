# TASK-046 Integrate firefly-python-api and replace inline HTTP calls

## Status
done

## Description

`firefly-python-api` is now a complete, tested library at
`https://github.com/CmdrPrompt/firefly-python-api` that covers all HTTP
operations this project performs:

- Session management (`FireflyClient`)
- Credential loading (`load_config`)
- Connection validation (`validate_connection`)
- Account and transaction methods (`get_asset_accounts`,
  `get_latest_transaction_date`, `create_transaction`)
- Reporting methods (`get_bills`, `get_budgets`, `get_budget_limits`,
  `get_categories`, `get_summary`)

This task adds the library as a git subtree and replaces all inline
`requests.Session` construction and Firefly API calls in `import_firefly.py`,
`web_ui.py`, and `config.py` with the corresponding `FireflyClient` methods.

The bank-importer's own interactive credential flow (`load_firefly_url`,
`load_api_token`, file-based prompting) stays in `config.py` unchanged.

## Branch
**Branch name:** `task/046-integrate-firefly-python-api`
**Switch/create:** `git checkout -b task/046-integrate-firefly-python-api`
**Make target:** `make branch-task f=TASK-046`

## Acceptance criteria

### Subtree integration
- [x] Library added as a git subtree at `libs/firefly-python-api/`:

  ```bash
  git subtree add --prefix=libs/firefly-python-api \
    https://github.com/CmdrPrompt/firefly-python-api main --squash
  ```

- [x] `pyproject.toml` declares `firefly-python-api` as a dependency with
  uv local source:
  
```toml
  [project]
  dependencies = [
      ...,
      "firefly-python-api",
  ]

  [tool.uv.sources]
  firefly-python-api = { path = "libs/firefly-python-api" }
  ```

### import_firefly.py
- [x] Inline `requests.Session` construction replaced by `FireflyClient`
- [x] `fetch_accounts_from_firefly()` uses `client.get_asset_accounts()`
- [x] `get_latest_transaction_date()` uses
  `client.get_latest_transaction_date(account_id)`
- [x] `create_transaction()` uses `client.create_transaction(payload)`

### web_ui.py
- [x] Inline `requests.Session` construction replaced by `FireflyClient`
- [x] Account and transaction calls use the corresponding `FireflyClient` methods

### config.py
- [x] `validate_firefly_url()` delegates to
  `FireflyClient(url, token).validate_connection()` instead of calling
  `requests.get` directly

### Quality
- [x] `docs/REQUIREMENTS_import_firefly.md` updated to note that the HTTP
  session layer and all Firefly API calls are delegated to `firefly-python-api`
- [x] `make lint && make test` pass

## Completion
**Date:** 2026-04-30
**Summary:** Lade till `firefly-python-api` som git subtree under `libs/firefly-python-api/` och ersatte alla inline `requests.Session`-konstruktioner och Firefly API-anrop i `import_firefly.py`, `web_ui.py` och `config.py` med motsvarande `FireflyClient`-metoder. Tester uppdaterade för ny signatur och exception-baserad felhantering.
**Files changed:** pyproject.toml, uv.lock, src/firefly_bank_importer/import_firefly.py, src/firefly_bank_importer/web_ui.py, src/firefly_bank_importer/config.py, docs/REQUIREMENTS_import_firefly.md, CHANGELOG.md, tests/unit/test_build_account_map.py, tests/unit/test_config.py, tests/unit/test_coverage_wins.py, tests/unit/test_date_parsing.py, tests/unit/test_nordea_format.py, tests/unit/test_process_csv.py, tests/unit/test_process_folder.py, tests/unit/test_transaction_payload_log.py, tests/unit/test_web_ui_file_upload.py, tests/unit/test_web_ui_live_import_progress.py
**Branch:** task/046-integrate-firefly-python-api
**Stage:** `git add CHANGELOG.md docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-046-extract-firefly-python-client.md docs/tasks/TASK-048-create-folder-if-not-exists.md pyproject.toml uv.lock src/firefly_bank_importer/config.py src/firefly_bank_importer/import_firefly.py src/firefly_bank_importer/web_ui.py tests/unit/test_build_account_map.py tests/unit/test_config.py tests/unit/test_coverage_wins.py tests/unit/test_date_parsing.py tests/unit/test_nordea_format.py tests/unit/test_process_csv.py tests/unit/test_process_folder.py tests/unit/test_transaction_payload_log.py tests/unit/test_web_ui_file_upload.py tests/unit/test_web_ui_live_import_progress.py`
**Commit:** `git commit -m "Integrate firefly-python-api as subtree and replace all inline Firefly HTTP calls"`
