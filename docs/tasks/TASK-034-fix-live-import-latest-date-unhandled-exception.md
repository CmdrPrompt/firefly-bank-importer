# TASK-034 Fix ohanterat undantag från get_latest_transaction_date avbryter live import-jobb

## Status
todo

## Description
I `_process_live_import_folder()` (rad 1101 i `web_ui.py`) anropas
`get_latest_transaction_date()` utan `try/except`. Ett nätverksfel, HTTP-fel eller
oväntat API-svar kastar ett undantag som propagerar upp i bakgrundstråden och fångas
av den yttre `except Exception`-klausulen (rad 1189), vilket markerar hela jobbet som
misslyckat. Alla kataloger som bearbetats innan felet räknas, men jobbet avbryts i
förtid utan att en varning loggas per katalog. Detta bryter NFR-3 (robusthet) —
ett misslyckat datum-uppslagning bör logga en varning och fortsätta, inte avbryta
hela importen.

## Branch
**Branch name:** `task/034-fix-live-import-latest-date-unhandled-exception`
**Switch/create:** `git checkout -b task/034-fix-live-import-latest-date-unhandled-exception`
**Make target:** `make branch-task f=TASK-034`

## Acceptance criteria
- [ ] `get_latest_transaction_date()` i `_process_live_import_folder` omsluts av `try/except`
- [ ] Vid undantag loggas en varning per katalog och importen fortsätter utan senaste-datum-filtrering (eller med datum=None)
- [ ] Hela jobbet avbryts inte på grund av ett misslyckat datum-uppslagning
- [ ] Test täcker scenariot att datum-uppslagning kastar undantag under pågående jobb

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/034-fix-live-import-latest-date-unhandled-exception`
**Stage:** `git add docs/tasks/TASK-034-fix-live-import-latest-date-unhandled-exception.md`
**Commit:** `git commit -m "Fix unhandled exception from get_latest_transaction_date in live import"`
