# TASK-037 Fix rader med ogiltigt datum försvinner spårlöst i dry-run preview

## Status
todo

## Description
I `_process_preview_row()` (rad 337–345 i `web_ui.py`) kastas ett `ValueError` vid
ett oparsbart datum, en varning läggs till, och funktionen returnerar tidigt. Raden
räknas varken som kandidat eller som duplicate-skip. Inga totaler uppdateras.
Från användarperspektiv försvinner raden utan att synas i sammanfattningen, vilket
strider mot FR-39 ("parsing/validation warnings ska vara synliga i preview").
En användare kan inte se hur många rader som tappades bort på grund av datumfel.

## Branch
**Branch name:** `task/037-fix-bad-date-rows-silently-dropped`
**Switch/create:** `git checkout -b task/037-fix-bad-date-rows-silently-dropped`
**Make target:** `make branch-task f=TASK-037`

## Acceptance criteria
- [ ] Rader med ogiltigt datum räknas i en synlig räknare (t.ex. `parse_errors`) i dry-run-sammanfattningen
- [ ] Antalet datumfelrader visas i preview-UI:t per fil
- [ ] Test täcker att en CSV med ogiltiga datum visar korrekt antal fel i preview

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/037-fix-bad-date-rows-silently-dropped`
**Stage:** `git add docs/tasks/TASK-037-fix-bad-date-rows-silently-dropped.md`
**Commit:** `git commit -m "Fix bad-date rows silently dropped from dry-run preview totals"`
