# TASK-050 Komplettera filnamnsfilter: import, CLI och webb

## Status

in-progress

## Description

TASK-049 implementerade filnamnsfilter i `auto_split_folder` (FR-63) men
lämnade tre gap som identifierades vid kravgranskning:

1. **Implementationsgap** — `process_folder` samlar in alla `*.csv`-filer för
   import, inklusive filer som redan fått en WARNING av `auto_split_folder`.
   FR-63 säger att okända filer "shall not be split **or** imported".
2. **Kravdokument inaktuellt** — UC-6 och FR-12 saknade filnamnsvillkoret.
   (Redan åtgärdat i kravdokumentet inför denna task.)
3. **UX-inkonsistens** — Webb-UI:ts uppladdning (FR-45) accepterade filer
   vars namn inte innehåller `konto`/`kontoutdrag`, men importen hoppade
   sedan över dem. FR-64 kräver dessutom att namnkonventionen visas i
   uppladdningsformuläret. CLI-hjälptexten saknar också information om
   namnreglerna (FR-2).

Åtgärder:

- `process_folder`: samla bara in `YYYY-MM.csv`-filer för import.
- `_validate_upload_file`: avvisa filer vars namn inte innehåller
  `konto`/`kontoutdrag`.
- `_render_upload_form`: lägg till synlig beskrivning av namnkonventionen.
- `_parse_cli_args`: utöka hjälptexten med de två filtyperna.

## Branch

**Branch name:** `task/050-complete-filename-filter`
**Switch/create:** `git checkout -b task/050-complete-filename-filter`
**Make target:** `make branch-task f=TASK-050`

## Acceptance criteria

- [x] `process_folder` plockar bara upp `YYYY-MM.csv`-filer för import;
  övriga CSV-filer importeras inte (även om de råkar ligga kvar).
- [x] Uppladdning via webb-UI avvisar filer vars namn inte innehåller
  `konto` eller `kontoutdrag` (skiftlägesokänsligt) med en tydlig
  avvisningsorsak.
- [x] Uppladdningsformuläret visar en synlig text om namnkonventionen.
- [x] CLI-hjälptexten beskriver de två filtyperna (kontoutdragsfil och
  månadsfil).
- [x] `make lint && make test` passerar.

## Completion

**Date:** 2026-05-05
**Summary:** Fixade implementationsgapet i `process_folder` (nu endast YYYY-MM.csv), lade till filnamnsvalidering i `_validate_upload_file`, synlig namnkonventionstext i `_render_upload_form`, och utökad hjälptext i `_parse_cli_args`. Kravdokumentet hade redan uppdaterats (FR-2, FR-12, UC-6, FR-45, FR-63, FR-64). 13 nya/uppdaterade tester.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified
- `src/firefly_bank_importer/web_ui.py` — modified
- `tests/unit/test_process_folder.py` — modified
- `tests/unit/test_cli_args.py` — modified
- `tests/unit/test_web_ui_file_upload.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `CHANGELOG.md` — modified

**Branch:** `git checkout task/050-complete-filename-filter`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py src/firefly_bank_importer/web_ui.py tests/unit/test_process_folder.py tests/unit/test_cli_args.py tests/unit/test_web_ui_file_upload.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-050-complete-filename-filter.md CHANGELOG.md`
**Commit:** `git commit -m "Complete filename filter: import collects only monthly files, upload rejects wrong names, CLI and UI show naming rules"`
