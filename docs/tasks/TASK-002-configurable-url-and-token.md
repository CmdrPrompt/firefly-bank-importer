# TASK-002 Configurable Firefly URL and token

## Status

todo

## Description

The Firefly III base URL is currently hardcoded in `import_firefly.py`.
The API token is read from a plain `token` file.
Both should instead be stored in local files that are created interactively
on first run, so the user never needs to edit source code.

Relevant requirements: UC-12, FR-1 (updated), FR-29, FR-30, FR-31.

## Acceptance criteria

- [ ] Firefly URL is read from `config.json` at startup.
- [ ] If `config.json` is missing or contains no URL, the script prompts the user
  interactively, validates the URL against `/api/v1/about`, and saves it.
- [ ] API token is read from `secrets.json` at startup.
- [ ] If `secrets.json` is missing, the script falls back to the legacy `token` file.
- [ ] If neither exists, the script prompts the user with hidden input and saves the
  token to `secrets.json`.
- [ ] `--configure` flag forces the interactive flow for both URL and token,
  overwriting existing values.
- [ ] `secrets.json` is listed in `.gitignore`.
- [ ] `FIREFLY_URL` constant is removed from source code.
- [ ] All new code passes `make lint` and `make test`.

## Completion

**Date:**
**Summary:**
