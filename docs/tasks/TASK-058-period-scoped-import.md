# TASK-058 Importera en vald period från alla konton

## Status

done

## Description

Ny funktion: låta användaren välja en enskild period (`--period ÅÅÅÅ-MM`)
och importera bara den månadens rader, från alla kontomappar samtidigt, i
en enda multi-folder-körning — istället för att alltid importera hela
historiken i varje kontomapp.

Realiserar UC-33 och FR-68 i `docs/REQUIREMENTS_import_firefly.md`.

Berörda kodställen i `import_firefly.py`:

- `_parse_cli_args` (rad ~809) — lägg till `--period ÅÅÅÅ-MM`-flaggan och
  validera formatet.
- `main` (rad ~832) — skicka `period` vidare.
- `_resolve_folder_account_and_files` (rad ~560, multi-folder-vägen) och
  `process_folder` (rad ~522, single-folder-vägen) — filtrera
  `csv_files` till bara `<period>.csv` när en period är angiven, istället
  för alla filer som matchar `MONTHLY_FILE_RE`.
- `_gather_folder_pending` / `_run_multi_folder_import` — periodvärdet
  behöver nå ner till filresolutionen utan att störa den befintliga
  senaste-datum-/opening-balance-logiken, som ska fungera oförändrat på
  den (nu begränsade) filmängden.

Auto-split (`auto_split_folder`) körs som idag innan periodfiltreringen,
så en osplittrad exportfil hinner delas upp i månadsfiler först.

## Branch

**Branch name:** `task/058-period-scoped-import`
**Switch/create:** `git checkout -b task/058-period-scoped-import`
**Make target:** `make branch-task f=TASK-058`

## Acceptance criteria (Gherkin)

- [x] Scenario: Giltig period begränsar import till en fil per konto
      Given flera kontomappar, var och en med flera `ÅÅÅÅ-MM.csv`-filer
      When importen körs med `--period 2025-06`
      Then bara `2025-06.csv` i respektive kontomapp bearbetas
      And övriga månadsfiler i mapparna ignoreras helt

- [x] Scenario: Konto utan fil för perioden hoppas över
      Given en kontomapp som saknar `<period>.csv` (men har andra
      månadsfiler)
      When importen körs med `--period` satt till en period utan
      motsvarande fil
      Then mappen hoppas över med samma varning som "Inga CSV-filer"

- [x] Scenario: Ogiltigt periodformat avbryter körningen tidigt
      Given ett `--period`-värde som inte matchar `ÅÅÅÅ-MM` (t.ex.
      `2025-13`, `2025/06`, `juni-2025`)
      When skriptet körs
      Then ett tydligt felmeddelande skrivs ut och skriptet avslutas med
      felkod, innan något konto-/API-anrop görs

- [x] Scenario: Transfer-matchning fungerar som vanligt inom perioden
      Given två konton med matchande överföringsrader i samma period
      When importen körs med `--period` satt till den period raderna
      tillhör
      Then raderna paras ihop som en transfer precis som i en ofiltrerad
      körning (UC-31/FR-66), fast bara med den periodens rader i
      kandidatmängden

- [x] Scenario: Utan `--period` är beteendet oförändrat
      Given en normal körning utan `--period`
      When importen körs
      Then samtliga `ÅÅÅÅ-MM.csv`-filer i varje kontomapp bearbetas som
      idag

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Att kunna ange ett intervall av perioder (t.ex. `2025-01..2025-06`) —
  bara en enskild period per körning.
- Ändringar av auto-split-logiken (UC-6) i sig.
- Web-UI-stöd för periodval — bara CLI:t i denna task.

## Blockers

None.

## Completion

**Date:** 2026-07-21
**Summary:** Added a `--period YYYY-MM` CLI flag that restricts CSV file resolution to a single monthly file per account folder, in both the single-folder path (`process_folder`) and the multi-folder path (`_resolve_folder_account_and_files`/`_gather_folder_pending`/`_run_multi_folder_import`), via a shared `_filter_csv_files_for_period` helper. `_parse_cli_args` now consumes `--period` and its value (so the value isn't mistaken for the folder positional argument) and validates it against `PERIOD_RE` (`\d{4}-(0[1-9]|1[0-2])`) via `_validate_period`, raising `ValueError` on an invalid format or a missing value before any account/API work happens. `main()` threads `period` through unchanged when omitted (`None`), preserving today's all-months behavior. Folders with no matching `<period>.csv` are skipped with the existing "Inga CSV-filer" warning. Cross-account transfer matching (UC-31/FR-66) is unaffected in its own logic — it simply operates on the smaller, period-filtered row set gathered per folder. Rewrote `tests/unit/test_cli_args.py`'s unpacking for the new 6-tuple return (added `period is None` assertions to existing characterization tests) and added a `TestParseCLIArgsPeriodFlag` class; added `TestPeriodFilter` to `tests/unit/test_process_folder.py`; added `TestPeriodScopedMultiFolderImport` (real transfer-matching end-to-end through `main()`) to `tests/unit/test_transfer_detection.py`. Verified against the user's real Firefly instance and full `bankImports/` tree: `--dry-run --period 2025-06` processed exactly one `2025-06.csv` per account folder, detected 14 transfers scoped to that month, and imported 205 rows total — confirmed via log output (`Bearbetar: 2025-06.csv` appearing exactly once per folder). Full suite: 448 tests pass, `make lint` clean, no coverage regression. This branch also merged `main` (which now includes the previously-unmerged TASK-057 fix, PR #35) partway through development, after discovering the branch had been cut before that PR merged and was silently exercising the old, broken latest-date logic during manual verification.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified (`PERIOD_RE`, `_validate_period`, `_filter_csv_files_for_period` added; `_parse_cli_args`, `main`, `process_folder`, `_resolve_folder_account_and_files`, `_gather_folder_pending`, `_run_multi_folder_import` updated to thread `period` through)
- `tests/unit/test_cli_args.py` — modified
- `tests/unit/test_process_folder.py` — modified
- `tests/unit/test_transfer_detection.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-33, FR-68 added)
- `docs/tasks/TASK-058-period-scoped-import.md` — modified

**Branch:** `git checkout task/058-period-scoped-import`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_cli_args.py tests/unit/test_process_folder.py tests/unit/test_transfer_detection.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-058-period-scoped-import.md`
**Commit:** `git commit -m "Add --period YYYY-MM flag to import a single month across all accounts (TASK-058)"`
