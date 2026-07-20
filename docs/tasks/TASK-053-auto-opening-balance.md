# TASK-053 Automatisk startsaldo-detektering vid import

## Status

not started

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

- [ ] Scenario: Startsaldo sätts automatiskt för konto med saldo 0
      Given ett konto vars nuvarande opening balance är `0`
      And kontots CSV-filer innehåller en "Saldo"-kolumn
      When importen körs för kontot
      Then opening balance och opening balance-datum sätts från den äldsta
      radens saldo- och datumvärde
      And den äldsta raden importeras inte som en transaktion
      And övriga rader importeras normalt

- [ ] Scenario: Startsaldo sätts inte om kontot redan har ett saldo
      Given ett konto vars nuvarande opening balance inte är `0`
      When importen körs för kontot
      Then `set_opening_balance` anropas inte
      And samtliga rader, inklusive den äldsta, importeras som idag

- [ ] Scenario: Bank-format utan saldokolumn
      Given ett konto vars bank-format saknar `balance_header`
      When importen körs för kontot
      Then en varning loggas om att startsaldo inte kunde detekteras
      automatiskt
      And samtliga rader importeras normalt, utan att någon exkluderas

- [ ] Scenario: Dry-run visar planerad ändring utan att verkställa
      Given ett konto vars nuvarande opening balance är `0` och vars
      bank-format har `balance_header`
      When importen körs med `--dry-run`
      Then det saldo/datum som skulle sättas, och vilken rad som skulle
      exkluderas, loggas
      And `set_opening_balance` anropas inte
      And inga transaktioner postas

- [ ] Scenario: Kvalitetsgrindar
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

`FireflyClient.get_opening_balance` och `FireflyClient.set_opening_balance`
är klara och mergade i `firefly-python-api` (TASK-013, TASK-014, PR #13 och
#14 på GitHub). `libs/firefly-python-api/` här i det här repot behöver
uppdateras via `git subtree pull --prefix=libs/firefly-python-api
firefly-python-api-upstream main --squash` innan implementationen kan
påbörjas (samma mönster som i TASK-051).

## Completion

_Not yet completed._
