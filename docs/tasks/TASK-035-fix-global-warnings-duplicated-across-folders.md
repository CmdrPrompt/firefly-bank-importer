# TASK-035 Fix global_warnings dupliceras till alla mappar i dry-run preview

## Status
todo

## Description
I `_summarize_preview_folder()` (rad 403/422 i `web_ui.py`) läggs `global_warnings`
till i varje mapps varningslista. `global_warnings` innehåller bl.a. per-kontomeddelanden
som "Kunde inte hämta senaste transaktionsdatum för konto 42". Om två mappar mappas
till olika konton och datum-uppslagningen för ett konto misslyckas, visas det felet
i *båda* mapparnas varningslista — även den mapp vars konto lyckades. Användaren
ser vilseledande och duplicerade varningar i preview-sammanfattningen.

## Branch
**Branch name:** `task/035-fix-global-warnings-duplicated-across-folders`
**Switch/create:** `git checkout -b task/035-fix-global-warnings-duplicated-across-folders`
**Make target:** `make branch-task f=TASK-035`

## Acceptance criteria
- [ ] Per-kontovarningar visas bara i den mapp vars `account_id` matchade kontot som misslyckades
- [ ] Genuint globala varningar (t.ex. "Ingen API-token") visas fortfarande i alla mappar
- [ ] Test täcker scenariot att två mappar har olika konton och ett konto misslyckas

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/035-fix-global-warnings-duplicated-across-folders`
**Stage:** `git add docs/tasks/TASK-035-fix-global-warnings-duplicated-across-folders.md`
**Commit:** `git commit -m "Fix global_warnings duplicated to all folders in dry-run preview"`
