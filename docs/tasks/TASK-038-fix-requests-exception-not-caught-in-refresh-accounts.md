# TASK-038 Fix requests.RequestException fångas inte i refresh-accounts och ger okontrollerad 500

## Status
todo

## Description
I `api_refresh_accounts()` och `refresh_accounts_page()` (rad 1384 och 1410–1413 i
`web_ui.py`) fångas `RuntimeError` och omvandlas till ett strukturerat HTTP-svar,
men `requests.RequestException` (t.ex. `ConnectionError`, `Timeout`) fångas inte.
`fetch_accounts_from_firefly()` kan kasta dessa vid nätverksfel, och de propagerar
som okontrollerade 500-svar med generisk FastAPI-felkropp istället för det
strukturerade `{"error": ...}`-format som UI:t förväntar sig.

## Branch
**Branch name:** `task/038-fix-requests-exception-not-caught-in-refresh-accounts`
**Switch/create:** `git checkout -b task/038-fix-requests-exception-not-caught-in-refresh-accounts`
**Make target:** `make branch-task f=TASK-038`

## Acceptance criteria
- [ ] `requests.RequestException` fångas i båda route-handlers och omvandlas till ett strukturerat felsvar
- [ ] Nätverksfel vid kontouppfriskning ger ett läsbart felmeddelande i UI:t, inte ett 500-svar
- [ ] Test täcker att `ConnectionError` och `Timeout` returnerar strukturerat felsvar

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/038-fix-requests-exception-not-caught-in-refresh-accounts`
**Stage:** `git add docs/tasks/TASK-038-fix-requests-exception-not-caught-in-refresh-accounts.md`
**Commit:** `git commit -m "Fix requests.RequestException not caught in refresh-accounts routes"`
