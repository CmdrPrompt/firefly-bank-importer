# TASK-059 Kontonamn i transaktionsloggen samt tidtagning av importen

## Status

done

## Description

Två relaterade loggnings-förbättringar, realiserar UC-34/FR-69 och
UC-35/FR-70 i `docs/REQUIREMENTS_import_firefly.md`:

1. **Kontonamn istället för konto-ID i transaktionsloggen (FR-69).**
   Idag loggas withdrawal/deposit-rader utan konto-referens alls
   (`_log_tx_result`, rad ~379) och transfer-rader med numeriska
   `source_id`/`destination_id` (`_post_transfer`, rad ~773-776). Båda ska
   istället visa kontonamnet, uppslaget via `account_map` (namn -> id).
   Om ett konto-ID inte kan slås upp (t.ex. inaktuell cache) faller
   loggningen tillbaka på det numeriska ID:t.

   Format (icke-transfer):
   `[OK] [<kontonamn>] [<transaktionstyp>] 69.00 SEK | 2025-06-25 | MCDJARFALLAS/25-06-24`

   Format (transfer):
   `[OK] [transfer] 500.00 SEK | 2025-06-23 | <kontonamn 1> -> <kontonamn 2> | UTLÄGG MAT`

   Samma format gäller `[DRY RUN]`-varianterna av båda radtyperna.

2. **Tidtagning av hela importkörningen samt snitt-tid per transaktion
   (FR-70).** `main()` (rad ~868) ska ta tid från start (innan
   token/URL-inläsning och konto-discovery) till att samtliga mappar är
   färdigbehandlade, och räkna det totala antalet försökta transaktioner
   (withdrawal/deposit-rader + transfer-par, lyckade som misslyckade).
   Efter befintliga `"Klar!"`-raden (rad ~927) loggas total tid i
   `H:MM:SS`-format samt snitt-tid per transaktion i sekunder
   (t.ex. `0.42s/transaktion`); snitt-raden utelämnas om antalet
   transaktioner är `0`.

Berörda kodställen i `import_firefly.py`:

- `_log_tx_result` — lägg till `account_name`-parameter.
- `create_transaction` — lägg till `account_name`-parameter, uppdatera
  både `[OK]`- och `[DRY RUN]`-loggraderna.
- `_submit_batch`, `_handle_batch_result`, `_run_threaded_import` —
  trä `account_name` igenom till `create_transaction`/`_log_tx_result`.
- `process_csv`, `process_folder` — slå upp kontonamnet en gång per
  mapp och skicka vidare.
- `PendingRow` (NamedTuple, rad ~37) — lägg till `account_name`-fält så
  namnet finns tillgängligt i multi-folder-vägen utan upprepade
  uppslag.
- `_collect_csv_pending_rows`, `_gather_folder_pending` — sätt
  `account_name` vid radskapande.
- `_post_transfer` — bygg loggsammanfattningen från `PendingRow`-parets
  `account_name`-fält istället för payloadens `source_id`/`destination_id`.
- `_post_unmatched_rows` — gruppera per konto med tillhörande
  `account_name`.
- Ny hjälpfunktion `_resolve_account_name(account_id, account_map)` med
  fallback till `str(account_id)`.
- `main` — mät tid med `time.monotonic()`, räkna totalt antal
  transaktioner, logga efter `"Klar!"`.

## Branch

**Branch name:** `task/059-account-name-logging-and-duration`
**Switch/create:** `git checkout -b task/059-account-name-logging-and-duration`
**Make target:** `make branch-task f=TASK-059`

## Acceptance criteria (Gherkin)

- [x] Scenario: Withdrawal/deposit-rad loggar kontonamn
      Given ett konto med namnet "SEB Lönekonto Thomas" i `account_map`
      When en withdrawal-transaktion på 69.00 SEK postas för det kontot
      Then loggraden är
      `[OK] [SEB Lönekonto Thomas] [withdrawal] 69.00 SEK | 2025-06-25 | MCDJARFALLAS/25-06-24`

- [x] Scenario: Transfer-rad loggar båda kontonamnen
      Given två konton "Planbok" och "SEB Räkningskonto" med en matchad
      transfer mellan dem
      When transfer-transaktionen på 500.00 SEK postas
      Then loggraden är
      `[OK] [transfer] 500.00 SEK | 2025-06-23 | Planbok -> SEB Räkningskonto | UTLÄGG MAT`

- [x] Scenario: Dry-run använder samma format
      Given `--dry-run` är satt
      When en withdrawal- respektive en transfer-rad skulle postas
      Then loggraderna har samma kontonamns-format som ovan men med
      `[DRY RUN]` istället för `[OK]`

- [x] Scenario: Okänt konto-ID faller tillbaka på numeriskt ID
      Given ett konto-ID som saknas i `account_map` (t.ex. inaktuell cache)
      When en transaktion för det kontot postas
      Then loggraden visar det numeriska konto-ID:t istället för ett namn,
      och raden skrivs ut som vanligt

- [x] Scenario: Total körtid loggas sist
      Given en normal importkörning (en eller flera mappar)
      When körningen är klar
      Then en loggrad efter `"Klar!"` visar total förfluten tid i
      `H:MM:SS`-format

- [x] Scenario: Snitt-tid per transaktion loggas
      Given en körning som postar (eller i dry-run skulle posta) minst en
      transaktion
      When körningen är klar
      Then en loggrad visar snitt-tid per transaktion i sekunder
      (t.ex. `0.42s/transaktion`)

- [x] Scenario: Ingen snitt-tid vid noll transaktioner
      Given en körning där inga rader behövde importeras (t.ex. alla
      mappar redan uppdaterade)
      When körningen är klar
      Then total körtid loggas men ingen snitt-tid-rad skrivs ut

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Ändringar av vilka rader som räknas som "transaktion" i andra
  sammanhang (t.ex. `_run_threaded_import`s egna "X ok, Y fel"-summering)
  utöver att återanvända samma räkning för snitt-tiden.
- Web-UI-visning av kontonamn eller körtid — bara CLI/loggfil i denna
  task.
- Konfigurerbart tidsformat eller enhet för snitt-tiden.

## Blockers

None.

## Completion

**Date:** 2026-07-31
**Summary:** Added `account_name` throughout the transaction-logging call chain so withdrawal/deposit and transfer log lines show the Firefly account name instead of the numeric ID, with a fallback to the ID via a new `_resolve_account_name(account_id, account_map)` helper. `_log_tx_result` now takes a required `account_name`; `create_transaction` takes an optional `account_name` (defaulting to `None`, resolved internally to `str(account_id)`) so existing callers that don't pass it (e.g. the web UI, which logs its own progress with `log=False`) are unaffected. `PendingRow` gained an `account_name` field, populated once per folder in `_gather_folder_pending`/`_collect_csv_pending_rows` and reused by `_post_unmatched_rows` and the transfer-posting loop in `_run_multi_folder_import`, which now resolves the neg/pos (source/destination) names to pass into `_post_transfer`'s new optional `source_name`/`destination_name` parameters — falling back to the payload's numeric IDs when omitted. For FR-70, `main()` now records `time.monotonic()` right after `BLOCK_TRANSACTION_POSTS` is set (before token/URL loading and account discovery), and `process_folder`/`process_csv`/`_run_multi_folder_import` were changed to return the count of attempted transactions (previously `None`) so `main()` can compute and log total elapsed time (`H:MM:SS` via `timedelta`) and average time per transaction after `"Klar!"`, omitting the average line when the count is `0`. Updated existing characterization tests for the new `PendingRow` field and `_log_tx_result`/`_post_transfer` signatures (`test_progress_bar.py`, `test_transfer_detection.py`, `test_transaction_payload_log.py`); added `tests/unit/test_account_name_logging.py` and `tests/unit/test_import_duration.py`. Full suite: 462 tests pass, `make lint` clean, coverage unchanged at 93.30% (no regression from the pre-task baseline).
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified (`_resolve_account_name` added; `PendingRow`, `_log_tx_result`, `create_transaction`, `_submit_batch`, `_handle_batch_result`, `_run_threaded_import`, `process_csv`, `process_folder`, `_collect_csv_pending_rows`, `_gather_folder_pending`, `_post_transfer`, `_post_unmatched_rows`, `_run_multi_folder_import`, `main` updated)
- `tests/unit/test_account_name_logging.py` — created
- `tests/unit/test_import_duration.py` — created
- `tests/unit/test_transaction_payload_log.py` — modified
- `tests/unit/test_progress_bar.py` — modified
- `tests/unit/test_transfer_detection.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-34, UC-35, FR-69, FR-70 added)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-059-account-name-logging-and-duration.md` — modified

**Branch:** `git checkout task/059-account-name-logging-and-duration`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_account_name_logging.py tests/unit/test_import_duration.py tests/unit/test_transaction_payload_log.py tests/unit/test_progress_bar.py tests/unit/test_transfer_detection.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-059-account-name-logging-and-duration.md`
**Commit:** `git commit -m "Show account names in transaction logs and log import duration (TASK-059)"`
