# TASK-046 Extract shared Firefly HTTP client to firefly-python-client

## Status
todo

## Description
The HTTP session creation (requests.Session + Bearer auth) and URL validation against
`/api/v1/about` are duplicated inline across `import_firefly.py` and `web_ui.py`.
`firefly-bills-analyzer` also needs the same primitives.

Extract these into a new standalone package `firefly-python-client` that both projects
can depend on. The package owns only the HTTP session lifecycle and credential loading
from environment variables; the bank-importer's own interactive config flow
(`load_firefly_url`, `load_api_token`, file-based prompting) stays in `config.py`.

## Branch
**Branch name:** `task/046-extract-firefly-python-client`
**Switch/create:** `git checkout -b task/046-extract-firefly-python-client`
**Make target:** `make branch-task f=TASK-046`

## Acceptance criteria

- [ ] New GitHub repository `https://github.com/CmdrPrompt/firefly-python-client` exists with its own `pyproject.toml`
- [ ] Repository is integrated into this project as a git subtree at `libs/firefly-python-client/`:
  `git subtree add --prefix=libs/firefly-python-client https://github.com/CmdrPrompt/firefly-python-client main --squash`
- [ ] Package exposes three public symbols:
  - `FireflyClient(url: str, token: str)` — wraps `requests.Session` with `Authorization: Bearer <token>` and `Accept: application/json` headers
  - `load_config(env_path)` — reads `FIREFLY_URL` and `FIREFLY_TOKEN` from environment or `.env` file; returns `(url, token)`
  - `FireflyClient.validate_connection()` — `GET /api/v1/about`; raises `FireflyConnectionError` on failure
- [ ] Package has no runtime dependencies beyond `requests` and `python-dotenv`
- [ ] Package has unit tests with ≥90% coverage of its own code
- [ ] Inline `requests.Session` construction in `import_firefly.py` and `web_ui.py` is replaced by `FireflyClient`
- [ ] `validate_firefly_url` in `config.py` delegates to `FireflyClient.validate_connection()` instead of calling requests directly
- [ ] `firefly-python-client` is referenced as a local path dependency in `pyproject.toml`:
  `firefly-python-client = { path = "libs/firefly-python-client" }`
- [ ] The requirements spec (`docs/REQUIREMENTS_import_firefly.md`) documents that the HTTP session layer uses `firefly-python-client`
- [ ] `make lint && make test` pass

## Completion
<!-- Fill in when done -->
**Date:**
**Summary:**
**Files changed:**
**Branch:**
**Stage:**
**Commit:**
