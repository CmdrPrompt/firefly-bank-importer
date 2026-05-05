# TASK-048 Skapa mapp om den inte finns; felhantering för filsökväg

## Status
cancelled

## Description

`firefly-import <sökväg>` kraschar med `os.mkdir`-fel när användaren
råkar ange en befintlig fil istället för en katalog.  Dessutom saknas stöd
för att automatiskt skapa en ny katalog om sökvägen inte finns ännu.

**Ersatt av TASK-049** — kravet omdefinierades till ett namnbaserat filfilter
(FR-63) efter diskussion 2026-05-05.

Implementera de två nya feltillstånden i `main()` i `import_firefly.py`
(se krav 8 i `docs/REQUIREMENTS_import_firefly.md`):

1. **Sökväg pekar på en fil** → logga fel och avsluta med kod 1.
2. **Sökväg finns inte** → skapa katalogen (inklusive föräldrar) och
   fortsätt normalt.

## Branch
**Branch name:** `task/048-create-folder-if-not-exists`
**Make target:** `make branch-task f=TASK-048`

## Acceptance criteria

- [ ] Om `<sökväg>` är en befintlig fil loggas
  `"Fel: '<sökväg>' är en fil, inte en mapp. Ange en mappsökväg."` och
  skriptet avslutar med kod 1.
- [ ] Om `<sökväg>` inte existerar skapas katalogen (med `mkdir -p`-semantik)
  och skriptet fortsätter normalt.
- [ ] `make lint && make test` passerar.

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:**
**Stage:**
**Commit:**
