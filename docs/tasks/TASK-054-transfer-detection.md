# TASK-054 Detektera överföringar mellan konton vid import

## Status

done

## Description

Lägg till detektering och import av överföringar mellan användarens egna
konton vid en flerkonto-import, så att en insättning på ett konto och ett
motsvarande uttag på ett annat konto postas som en enda `transfer`-
transaktion i Firefly III, istället för att postas som två orelaterade
withdrawal/deposit-transaktioner.

Realiserar UC-31 och FR-66 i `docs/REQUIREMENTS_import_firefly.md`.

Detta kräver en arkitekturändring: idag postas varje rad direkt när en mapp
bearbetas (`process_folder`/`process_csv`, per konto, oberoende av andra
mappar). För att kunna para ihop rader mellan konton måste **alla mappars
rader samlas in innan något postas**, sedan paras ihop, och därefter postas
i två steg: matchade par som `transfer`, resterande rader som idag
(withdrawal/deposit).

Matchningsregler (se UC-31 för fullständig beskrivning):

1. Belopp lika stort med motsatt tecken, mellan två olika konton.
2. Datumfönster: samma dag om båda kontona har samma bank-format (t.ex.
   båda SEB), annars upp till 2 dagars skillnad.
3. Vid exakt en kandidat inom fönstret: para ihop direkt.
4. Vid flera kandidater: föredra en kandidat vars text är en
   skiftlägesokänslig delsträng av den andras (i endera riktningen), om
   exakt en sådan kandidat finns. Annars: ingen matchning, raden postas som
   vanligt.
5. Matchade par postas som en `transfer`-transaktion (`source_id` = kontot
   med minusbeloppet, `destination_id` = kontot med plusbeloppet). Båda
   raderna exkluderas från individuell withdrawal/deposit-postning.
6. Med `--dry-run` loggas vilka par som skulle postas som transfers, samt
   vilka rader som förblir omatchade/tvetydiga, utan att något postas.

## Branch

**Branch name:** `task/054-transfer-detection`
**Switch/create:** `git checkout -b task/054-transfer-detection`
**Make target:** `make branch-task f=TASK-054`

## Acceptance criteria (Gherkin)

- [x] Scenario: Överföring mellan konton hos samma bank matchas samma dag
      Given två konton med samma bank-format
      And ett uttag på det ena kontot och en insättning på det andra, med
      samma belopp och samma datum
      When importen körs för båda kontons mappar i samma körning
      Then en enda `transfer`-transaktion postas mellan kontona
      And ingen av raderna postas som withdrawal eller deposit

- [x] Scenario: Överföring mellan konton hos olika banker matchas inom 2 dagar
      Given två konton med olika bank-format
      And ett uttag på det ena kontot och en insättning på det andra, med
      samma belopp och datum som skiljer sig med 1 eller 2 dagar
      When importen körs för båda kontons mappar i samma körning
      Then en enda `transfer`-transaktion postas mellan kontona

- [x] Scenario: Överföring mellan konton hos olika banker matchas inte om
      datumskillnaden överstiger 2 dagar
      Given två konton med olika bank-format
      And rader med samma belopp men datum som skiljer sig med mer än 2 dagar
      When importen körs
      Then ingen transfer postas
      And båda raderna postas som withdrawal respektive deposit som vanligt

- [x] Scenario: Tvetydig matchning löses med textöverlappning
      Given flera kandidatrader med samma belopp och inom datumfönstret
      And exakt en av kandidaterna har en text som är en delsträng av den
      andra radens text (skiftlägesokänsligt)
      When importen körs
      Then den kandidaten paras ihop och postas som transfer
      And övriga kandidater postas som vanligt

- [x] Scenario: Tvetydig matchning utan entydig textöverlappning postas som vanligt
      Given flera kandidatrader med samma belopp och inom datumfönstret
      And ingen, eller mer än en, av kandidaterna har textöverlappning
      When importen körs
      Then ingen av kandidaterna paras ihop
      And samtliga postas som withdrawal/deposit som vanligt

- [x] Scenario: Enstaka mappimport påverkas inte
      Given endast en kontomapp importeras i körningen (UC-1)
      When importen körs
      Then ingen cross-account-matchning görs
      And samtliga rader postas som withdrawal/deposit som idag

- [x] Scenario: Dry-run visar planerade transfers utan att posta
      Given rader som skulle matchas som en överföring
      When importen körs med `--dry-run`
      Then de planerade transfer-paren loggas
      And omatchade/tvetydiga rader loggas separat
      And inga transaktioner postas

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Konvertering av redan importerade withdrawal/deposit-par till transfer i
  efterhand (engångsskript mot redan existerande data) — separat, ej
  planerad task tills vidare.
- Textmatchning som primärt kriterium — används endast som tiebreaker vid
  flera kandidater inom belopp/datum-fönstret, inte som ett fristående
  matchningsvillkor.
- Överföringar till/från konton som inte ingår i den aktuella
  importkörningen (dvs. bara en sida av överföringen importeras) — dessa
  rader postas som vanlig withdrawal/deposit, precis som idag.

## Blockers

None. TASK-053 landades och mergades till `main` (PR #31) innan denna task
påbörjades.

## Completion

**Date:** 2026-07-21
**Summary:** Added cross-account transfer detection for multi-folder imports. `main()` now branches: a single resolved folder still goes through the unchanged `process_folder()`/`process_csv()` path (UC-1 unaffected); two or more folders go through the new `_run_multi_folder_import()` path, which gathers every folder's pending rows first (`_gather_folder_pending()`, reusing `_apply_auto_opening_balance()`/`_collect_pending_rows()` per account, tagged into a new `PendingRow` NamedTuple with `account_id`/`bank_format`/`row_date`), matches transfer candidates via `_match_transfer_pairs()`, posts matched pairs as a single `transfer` transaction (`_build_transfer_payload()`/`_post_transfer()`, source = negative-amount account, destination = positive-amount account), and posts everything else as withdrawal/deposit exactly as before (`_post_unmatched_rows()`, still using the existing threaded `_run_threaded_import()` for real posts). Matching rule: equal-and-opposite amount between different accounts, `0`-day window when both rows share a bank format, `2`-day window otherwise; when a row has several amount/date candidates, a candidate is only chosen if its description is a case-insensitive substring of the other's (in either direction) and exactly one candidate has that overlap — verified **mutually** in both directions (`_resolve_row_choice()` called from both sides) so that an ambiguous group of 3+ same-amount rows never lets one row "steal" a pairing just because it looks unambiguous from one side while the other side is genuinely ambiguous; this mutual-match requirement was added after a Hypothesis/example test caught the one-directional version wrongly pairing a 3-row ambiguous group. `--dry-run` logs planned transfers (`[DRY RUN] [transfer] ...`) and leaves unmatched rows going through the existing dry-run preview path, without posting anything. 19 new tests in `tests/unit/test_transfer_detection.py` (unit-level matching/disambiguation logic plus one Hypothesis property test for amount-equality matching, and `main()` integration tests for matched/unmatched/dry-run/single-folder behavior). 416 tests pass (up from 397), coverage 91.51%→92.41% (no regression). `make lint` (ruff, ruff format, mypy, bandit, pymarkdown, complexipy) all clean — required renaming `PendingRow.date` to `PendingRow.iso_date` because the field name shadowed the `datetime.date` type used by the sibling `row_date: date` field, which mypy flagged as `valid-type` error.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified (`PendingRow`, `_resolve_folder_account_and_files`, `_compute_latest_date_floor`, `_collect_csv_pending_rows`, `_gather_folder_pending`, `_description_overlap`, `_is_amount_and_date_match`, `_candidates_for_row`, `_choose_candidate`, `_resolve_row_choice`, `_match_transfer_pairs`, `_build_transfer_payload`, `_post_transfer`, `_post_unmatched_rows`, `_run_multi_folder_import` added; `main()` updated to branch on folder count)
- `tests/unit/test_transfer_detection.py` — added
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-31, FR-66 — already present from requirements confirmation)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-054-transfer-detection.md` — modified

**Branch:** `git checkout task/054-transfer-detection`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_transfer_detection.py CHANGELOG.md docs/tasks/TASK-054-transfer-detection.md`
**Commit:** `git commit -m "Add cross-account transfer detection for multi-folder imports (TASK-054)"`
