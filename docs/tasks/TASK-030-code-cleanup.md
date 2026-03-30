# TASK-030 Kodstädning

## Status
todo

## Description
Samlar upp mindre kodstädningsuppgifter som inte motiverar egna tasks men som förbättrar
läsbarhet och korrekthet.

## Branch
**Branch name:** `task/030-code-cleanup`
**Switch/create:** `git checkout -b task/030-code-cleanup`
**Make target:** `make branch-task f=TASK-030`

## Acceptance criteria
- [ ] `config.py` rad 75 & 165: ta bort `KeyError` från `except`-klausulerna — `json.loads()` kastar aldrig `KeyError`
- [ ] `import_firefly.py`: ta bort dead code `detect_csv_format()` (rad 273–276) — anropas aldrig, all format-resolving sker via `_resolve_column_mapping()`
- [ ] `import_firefly.py`: ta bort dead code `_get_csv_indices()` (rad 352–358) — anropas aldrig
- [ ] `web_ui.py` rad 153–154: ta bort `[:10]`-slice före `strptime` — accepterar tyst datetime-strängar som `"2024-01-01T12:00:00"`, inkonsekvent med övrig datumhantering
- [ ] `web_ui.py` rad 211/218–227: catch-all-varning "Kunde inte läsa Firefly-inställningar" visas även när filen lästes OK men värdet var tomt — formulera om till korrekt meddelande
- [ ] `web_ui.py` rad 371–372: tom fil behandlas som varning (ej blockerande) men okänt format som fel (blockerande) — dokumentera eller jämna ut beteendet
- [ ] `web_ui.py` rad 980: `_build_live_import_description` gör ingen intern bounds-check på `description_idx` — fragil API om funktionen anropas utanför `_handle_live_import_row`
- [ ] `web_ui.py` rad 1054–1055: tom fil i live import behandlas som varning (konsekvent med dry-run men överraskande) — dokumentera designbeslutet

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/030-code-cleanup`
**Stage:** `git add docs/tasks/TASK-030-code-cleanup.md`
**Commit:** `git commit -m "Code cleanup"`
