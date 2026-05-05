# TASK-049 Namnbaserat filter för CSV-filer i importmapp

## Status

done

## Description

Scriptet saknar ett namnbaserat filter för CSV-filer i importmappar.
Idag bearbetas alla `.csv`-filer oavsett filnamn, vilket kan leda till att
orelaterade filer splittas eller importeras av misstag.

Inför FR-63: scriptet ska känna igen två typer av CSV-filer:

1. **Kontoutdragsfil** — filnamnet innehåller `konto` eller `kontoutdrag`
   (skiftlägesokänsligt). Dessa splittas till månadsfiler.
2. **Månadsfil** — filnamnet matchar `YYYY-MM.csv`. Dessa importeras direkt.

En CSV-fil som varken matchar kontoutdragsmönstret eller datummönstret ska
ge en loggad varning och hoppas över.

Ersätter TASK-048 (cancelled 2026-05-05).

## Branch

**Branch name:** `task/049-csv-filename-filter`
**Switch/create:** `git checkout -b task/049-csv-filename-filter`
**Make target:** `make branch-task f=TASK-049`

## Acceptance criteria

- [x] CSV-filer vars namn innehåller `konto` eller `kontoutdrag`
  (skiftlägesokänsligt) splittas till månadsfiler som tidigare.
- [x] Månadsfiler (`YYYY-MM.csv`) importeras direkt som tidigare.
- [x] En CSV-fil som varken matchar kontoutdragsmönstret eller datummönstret
  loggas som `WARNING: Okänd filtyp, hoppar över: <filnamn>` och bearbetas inte.
- [x] `make lint && make test` passerar.

## Completion

**Date:** 2026-05-05
**Summary:** Lade till `_KONTOUTDRAG_RE` och ändrade `auto_split_folder` så att filer splittas endast om namnet innehåller "konto"/"kontoutdrag" (skiftlägesokänsligt), YYYY-MM.csv-filer hoppas över, och övriga CSV-filer ger en WARNING. Uppdaterade två befintliga tester som använde "export.csv" till "kontoutdrag_export.csv". Lade till 13 nya tester i `test_csv_filename_filter.py`. TASK-048 markerades cancelled.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified
- `tests/unit/test_csv_filename_filter.py` — created
- `tests/unit/test_coverage_wins.py` — modified
- `tests/unit/test_process_folder.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified (FR-63 tillagd)
- `docs/tasks/TASK-048-create-folder-if-not-exists.md` — modified (cancelled)
- `CHANGELOG.md` — modified

**Branch:** `git checkout task/049-csv-filename-filter`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_csv_filename_filter.py tests/unit/test_coverage_wins.py tests/unit/test_process_folder.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-048-create-folder-if-not-exists.md docs/tasks/TASK-049-csv-filename-filter.md CHANGELOG.md`
**Commit:** `git commit -m "Filter CSV files by name: kontoutdrag-pattern splits, YYYY-MM imports, warn on unknown"`
