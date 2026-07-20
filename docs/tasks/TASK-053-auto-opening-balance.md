# TASK-053 Automatisk startsaldo-detektering vid import

## Status

done

## Description

Lägg till automatisk detektering och sättning av opening balance för konton
som har `0` i nuvarande opening balance, baserat på den äldsta raden i
kontots bank-CSV-filer (som redan innehåller en löpande saldokolumn,
"Saldo", för SEB/ICA/Nordea).

Realiserar UC-30 och FR-65 i `docs/REQUIREMENTS_import_firefly.md`.

Flöde:

1. Innan transaktioner importeras för ett konto (UC-1/UC-2), kontrollerar
   skriptet kontots nuvarande opening balance via
   `FireflyClient.get_opening_balance`.
2. Om opening balance är `0` och bank-formatet har ett `balance_header`
   ("Saldo"), bestäms den äldsta daterade raden bland kontots CSV-filer.
3. Skriptet sätter kontots opening balance och opening balance-datum via
   `FireflyClient.set_opening_balance` från den radens saldo- och
   datumvärde, oförändrat.
4. Den äldsta raden exkluderas från de transaktioner som importeras;
   resterande rader (allt daterat efter den äldsta) importeras normalt.
5. Skriptet loggar vilket startsaldo/datum som sattes och att den äldsta
   raden hoppades över.
6. Om opening balance redan skiljer sig från `0`, eller bank-formatet saknar
   `balance_header`, hoppar skriptet över detta steg helt och importerar
   alla rader som idag.
7. Med `--dry-run` loggas vad som skulle sättas och vilken rad som skulle
   exkluderas, utan att `set_opening_balance` anropas eller transaktioner
   postas.

## Branch

**Branch name:** `task/053-auto-opening-balance`
**Switch/create:** `git checkout -b task/053-auto-opening-balance`
**Make target:** `make branch-task f=TASK-053`

## Acceptance criteria (Gherkin)

- [x] Scenario: Startsaldo sätts automatiskt för konto med saldo 0
      Given ett konto vars nuvarande opening balance är `0`
      And kontots CSV-filer innehåller en "Saldo"-kolumn
      When importen körs för kontot
      Then opening balance och opening balance-datum sätts från den äldsta
      radens saldo- och datumvärde
      And den äldsta raden importeras inte som en transaktion
      And övriga rader importeras normalt

- [x] Scenario: Startsaldo sätts inte om kontot redan har ett saldo
      Given ett konto vars nuvarande opening balance inte är `0`
      When importen körs för kontot
      Then `set_opening_balance` anropas inte
      And samtliga rader, inklusive den äldsta, importeras som idag

- [x] Scenario: Bank-format utan saldokolumn
      Given ett konto vars bank-format saknar `balance_header`
      When importen körs för kontot
      Then en varning loggas om att startsaldo inte kunde detekteras
      automatiskt
      And samtliga rader importeras normalt, utan att någon exkluderas

- [x] Scenario: Dry-run visar planerad ändring utan att verkställa
      Given ett konto vars nuvarande opening balance är `0` och vars
      bank-format har `balance_header`
      When importen körs med `--dry-run`
      Then det saldo/datum som skulle sättas, och vilken rad som skulle
      exkluderas, loggas
      And `set_opening_balance` anropas inte
      And inga transaktioner postas

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Manuell/interaktiv sättning av opening balance (den tidigare diskuterade
  fristående kommandot) — ersätts helt av den automatiska detekteringen i
  denna task.
- Överförings-detektering mellan konton (transfer-parning) — separat,
  kommande task som bygger vidare på detta.
- Justering av redan felaktigt satta opening balances (dvs. konton som inte
  har `0`) — användaren ansvarar för att nollställa kontona manuellt innan
  omimport, t.ex. i kombination med TASK-051 (rensa transaktioner).

## Blockers

None. `FireflyClient.get_opening_balance` och `FireflyClient.set_opening_balance`
var klara och mergade i `firefly-python-api` (TASK-013, TASK-014, PR #13 och
#14 på GitHub). `libs/firefly-python-api/` här i det här repot uppdaterades via
`git subtree pull --prefix=libs/firefly-python-api firefly-python-api-upstream
main --squash` innan implementationen påbörjades (samma mönster som i
TASK-051).

## Completion

**Date:** 2026-07-21
**Summary:** Added automatic opening balance detection to `process_folder()`: before importing an account's transactions, `_apply_auto_opening_balance()` checks the account's current opening balance via `FireflyClient.get_opening_balance`. If it is `0` (or unset), `_find_earliest_balance_row()` scans all of the account's CSV files (via `_earliest_balance_row_in_file()`/`_earliest_balance_row_in_rows()`) for the earliest-dated row and, if the bank format has a `balance_header`, calls `FireflyClient.set_opening_balance(account_id, balance, date)` with that row's balance and date as-is. The earliest row's date is then folded into the existing `latest_date` cutoff mechanism (already used by `--ignore-latest-date-check`/duplicate-prevention) so that row — and any other row sharing its exact date — is excluded from the transactions posted, without needing a new per-row exclusion mechanism. Accounts with a non-zero opening balance, or bank formats without a balance column (logged as a warning), are left untouched, importing all rows exactly as before. Under `--dry-run`, the balance/date and excluded row are logged but `set_opening_balance` is never called. Subtree-pulled `libs/firefly-python-api` from GitHub main (TASK-013/014) as a prerequisite. Split the balance-scanning logic into three small functions (`_find_earliest_balance_row` → `_earliest_balance_row_in_file` → `_earliest_balance_row_in_rows`) to stay under the complexipy complexity gate (initial single-function version scored 17 against a limit of 15). Updated `tests/unit/test_process_folder.py`'s `make_client()` fixture to default `get_opening_balance` to a non-zero balance so pre-existing characterization tests are unaffected by the new auto-detection path. 12 new tests in `tests/unit/test_auto_opening_balance.py` (unit-level for `_find_earliest_balance_row`/`_apply_auto_opening_balance`, plus `process_folder()` integration). 397 tests pass (up from 385), coverage 91.31%→91.51% (no regression). `make lint` (ruff, mypy --strict-equivalent, bandit, pymarkdown, complexipy) all clean.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified (`_find_earliest_balance_row`, `_earliest_balance_row_in_file`, `_earliest_balance_row_in_rows`, `_apply_auto_opening_balance` added; `process_folder` updated)
- `tests/unit/test_auto_opening_balance.py` — added
- `tests/unit/test_process_folder.py` — modified (`make_client()` fixture default)
- `libs/firefly-python-api/` — updated via `git subtree pull` (adds `get_opening_balance`, `set_opening_balance`)
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-30, FR-65, and UC-31/FR-66 for the follow-up transfer-detection task)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-053-auto-opening-balance.md` — modified
- `docs/tasks/TASK-054-transfer-detection.md` — added (follow-up task)

**Branch:** `git checkout task/053-auto-opening-balance`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_auto_opening_balance.py tests/unit/test_process_folder.py libs/firefly-python-api docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-053-auto-opening-balance.md docs/tasks/TASK-054-transfer-detection.md CHANGELOG.md`
**Commit:** `git commit -m "Add automatic opening balance detection from bank export on first import (TASK-053)"`
