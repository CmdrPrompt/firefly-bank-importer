# TASK-033 Fix saknad POST /account-mapping route gör UI-flödet oanvändbart

## Status
todo

## Description
Formuläret på kontovalsssidan postar till `/account-mapping` (rad 1473 i `web_ui.py`),
men ingen route-handler för den sökvägen finns i applikationen. Varje användare som
klickar "Fortsätt med denna mappning" får ett 404- eller 405-svar. Hela flödet
från kontoval till dry-run och live import via web UI är därmed oanvändbart.

## Branch
**Branch name:** `task/033-fix-missing-account-mapping-route`
**Switch/create:** `git checkout -b task/033-fix-missing-account-mapping-route`
**Make target:** `make branch-task f=TASK-033`

## Acceptance criteria
- [ ] En `POST /account-mapping`-handler finns och tar emot formulärdatan korrekt
- [ ] Flödet kontoval → dry-run (eller live import) fungerar end-to-end i web UI
- [ ] Test täcker att routen returnerar korrekt svar vid giltig och ogiltig indata

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/033-fix-missing-account-mapping-route`
**Stage:** `git add docs/tasks/TASK-033-fix-missing-account-mapping-route.md`
**Commit:** `git commit -m "Fix missing POST /account-mapping route"`
