# TASK-032 Fix ohanterade undantag i trådpool avbryter import

## Status
todo

## Description
I `_run_threaded_import()` (rad 417 i `import_firefly.py`) anropas `fut.result()`
utan `try/except`. Om en worker-tråd kastar ett undantag (t.ex. nätverksfel från
`requests`) re-raisas det omedelbart och avbryter hela import-loopen. Återstående
transaktioner skickas aldrig, och ingen sammanfattning loggas. Detta bryter FR-17
(resultatsammanfattning per fil) och NFR-3 (robusthet).

```python
result = fut.result()  # undantag propagerar okontrollerat
```

## Branch
**Branch name:** `task/032-fix-threadpool-unhandled-exceptions`
**Switch/create:** `git checkout -b task/032-fix-threadpool-unhandled-exceptions`
**Make target:** `make branch-task f=TASK-032`

## Acceptance criteria
- [ ] `fut.result()` omsluts av `try/except` som fångar undantag från worker-trådar
- [ ] Ett undantag i en transaktion loggas som fel och räknas i `errors`, men avbryter inte övriga transaktioner
- [ ] Resultatsammanfattningen (successes/errors) loggas korrekt även när enskilda transaktioner misslyckas
- [ ] Test täcker scenariot att en worker-tråd kastar ett undantag

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/032-fix-threadpool-unhandled-exceptions`
**Stage:** `git add docs/tasks/TASK-032-fix-threadpool-unhandled-exceptions.md`
**Commit:** `git commit -m "Fix unhandled exceptions in thread pool aborting import"`
