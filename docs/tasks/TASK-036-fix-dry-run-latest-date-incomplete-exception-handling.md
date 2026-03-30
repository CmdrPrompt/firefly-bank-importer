# TASK-036 Fix ofullständig undantagshantering för get_latest_transaction_date i dry-run

## Status
todo

## Description
I `_fetch_latest_dates()` (rad 247–254 i `web_ui.py`) fångas bara
`requests.RequestException` och `ValueError` från `get_latest_transaction_date()`.
Funktionen kan även kasta `KeyError` (vid oväntat API-responsformat) och
`json.JSONDecodeError` (vid icke-JSON-svar). Dessa propagerar ohanterade och kraschar
preview-endpointen med ett okontrollerat 500-svar istället för att visas som en
varning i dry-run-sammanfattningen.

## Branch
**Branch name:** `task/036-fix-dry-run-latest-date-incomplete-exception-handling`
**Switch/create:** `git checkout -b task/036-fix-dry-run-latest-date-incomplete-exception-handling`
**Make target:** `make branch-task f=TASK-036`

## Acceptance criteria
- [ ] `except`-klausulen i `_fetch_latest_dates` täcker alla undantag som `get_latest_transaction_date` kan kasta (inkl. `KeyError`, `json.JSONDecodeError`)
- [ ] Alternativt: `get_latest_transaction_date` garanterar att den bara kastar `RequestException` och `ValueError`
- [ ] Test täcker att `KeyError` och `JSONDecodeError` hanteras som varningar, inte 500-svar

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/036-fix-dry-run-latest-date-incomplete-exception-handling`
**Stage:** `git add docs/tasks/TASK-036-fix-dry-run-latest-date-incomplete-exception-handling.md`
**Commit:** `git commit -m "Fix incomplete exception handling for get_latest_transaction_date in dry-run"`
