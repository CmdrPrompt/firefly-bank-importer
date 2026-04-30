# TASK-046 Integrate firefly-python-api and replace inline HTTP calls

## Status
todo

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
- [ ] Library added as a git subtree at `libs/firefly-python-api/`:
  ```bash
  git subtree add --prefix=libs/firefly-python-api \
    https://github.com/CmdrPrompt/firefly-python-api main --squash
  ```
- [ ] `pyproject.toml` declares `firefly-python-api` as a dependency with
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
- [ ] Inline `requests.Session` construction replaced by `FireflyClient`
- [ ] `fetch_accounts_from_firefly()` uses `client.get_asset_accounts()`
- [ ] `get_latest_transaction_date()` uses
  `client.get_latest_transaction_date(account_id)`
- [ ] `create_transaction()` uses `client.create_transaction(payload)`

### web_ui.py
- [ ] Inline `requests.Session` construction replaced by `FireflyClient`
- [ ] Account and transaction calls use the corresponding `FireflyClient` methods

### config.py
- [ ] `validate_firefly_url()` delegates to
  `FireflyClient(url, token).validate_connection()` instead of calling
  `requests.get` directly

### Quality
- [ ] `docs/REQUIREMENTS_import_firefly.md` updated to note that the HTTP
  session layer and all Firefly API calls are delegated to `firefly-python-api`
- [ ] `make lint && make test` pass

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:**
**Stage:**
**Commit:**
