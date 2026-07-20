# TASK-051 Rensa transaktioner inför omimport

## Status

done

## Description

Lägg till en funktion (CLI, och ev. web UI-knapp om det senare önskas) för att
radera alla transaktioner för antingen samtliga konton eller en angiven lista
på konton, i syfte att kunna återimportera bank-CSV:er från grunden.

Realiserar UC-29 och FR-64 i `docs/REQUIREMENTS_import_firefly.md`.

Flöde:

1. Användaren väljer "alla konton" eller anger en lista på kontonamn
   (matchas mot den upptäckta/cachade kontolistan på samma sätt som vid
   import).
2. Skriptet hämtar samtliga transaktions-ID:n per valt konto via
   `FireflyClient.get_transactions_for_account`.
3. Skriptet visar totalt antal transaktioner som skulle raderas, grupperat
   per konto.
4. Utan `--dry-run` kräver skriptet att användaren skriver `JA` för att
   bekräfta innan radering sker.
5. Skriptet raderar varje transaktion via `FireflyClient.delete_transaction`
   och loggar antal raderade per konto och totalt.
6. Med `--dry-run` listas endast vad som skulle raderas, utan bekräftelseprompt
   och utan radering.

## Branch

**Branch name:** `task/051-clear-transactions`
**Switch/create:** `git checkout -b task/051-clear-transactions`
**Make target:** `make branch-task f=TASK-051`

## Acceptance criteria (Gherkin)

- [x] Scenario: Rensa alla konton
      Given ett antal upptäckta/cachade konton med transaktioner
      When användaren kör rensningsfunktionen med "alla konton" och bekräftar med "JA"
      Then samtliga transaktioner för samtliga konton raderas
      And antal raderade transaktioner per konto och totalt loggas

- [x] Scenario: Rensa en lista på konton
      Given en användarangiven lista på kontonamn som matchar upptäckta/cachade konton
      When användaren kör rensningsfunktionen med listan och bekräftar med "JA"
      Then endast transaktionerna för de angivna kontona raderas
      And övriga konton påverkas inte

- [x] Scenario: Avbryt utan bekräftelse
      Given att rensningsfunktionen visat hur många transaktioner som skulle raderas
      When användaren inte skriver "JA"
      Then inga transaktioner raderas

- [x] Scenario: Dry-run
      Given att `--dry-run` anges
      When rensningsfunktionen körs
      Then transaktionerna som skulle raderas listas
      And ingen bekräftelseprompt visas
      And inga transaktioner raderas

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Justering av kontonas ingående saldo (opening balance) efter rensning —
  hanteras manuellt av användaren.
- Radering av enbart en transaktionstyp (withdrawals/deposits/transfers).

## Blockers

None. TASK-012 i `firefly-python-api` är klar och mergad, och
`libs/firefly-python-api/` här är uppdaterad via `git subtree pull`
(`get_transactions_for_account` och `delete_transaction` finns nu på
`FireflyClient`). TASK-052 (pyproject.toml-regression som blockerade
`make branch-task`) är åtgärdad och mergad separat.

## Completion

**Date:** 2026-07-20
**Summary:** Added `firefly-clear-transactions` CLI command (`src/firefly_bank_importer/clear_transactions.py`) that deletes transactions for either all discovered/cached accounts (`--all`) or a comma-separated list of account names (`--accounts`), via the new `FireflyClient.get_transactions_for_account`/`delete_transaction` methods (TASK-012, pulled in via `git subtree pull` on `libs/firefly-python-api/`). Shows a per-account and total transaction count before acting, requires typing "JA" to confirm unless `--dry-run` is given (which only previews, no prompt, no deletion). Unknown account names abort with an error before any API calls. Registered as a console script in `pyproject.toml`. 30 new tests, 355→385 passing, coverage 90.78%→91.31% (no regression). Also fixed TASK-052 (pyproject.toml regression) as a prerequisite, merged separately via PR #29.
**Files changed:**

- `src/firefly_bank_importer/clear_transactions.py` — added
- `tests/unit/test_clear_transactions.py` — added
- `pyproject.toml` — modified (new `firefly-clear-transactions` console script)
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-29, FR-64)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-051-clear-transactions.md` — modified
- `uv.lock` — modified (lockfile drift from `libs/firefly-python-api` subtree update)

**Branch:** `git checkout task/051-clear-transactions`
**Stage:** `git add src/firefly_bank_importer/clear_transactions.py tests/unit/test_clear_transactions.py pyproject.toml uv.lock docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-051-clear-transactions.md`
**Commit:** `git commit -m "Add firefly-clear-transactions command to clear transactions for reimport (TASK-051)"`
