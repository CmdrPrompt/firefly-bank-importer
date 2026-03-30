# TASK-039 Nordea bank format package

## Status
done

## Description
Add support for Nordea's CSV export format so that Nordea transactions can be imported
into Firefly III. Nordea exports use semicolon as separator and have the following
header structure:

```text
Bokföringsdag;Belopp;Avsändare;Mottagare;Namn;Rubrik;Saldo;Valuta;
```

The relevant columns are:
- **Date:** `Bokföringsdag`
- **Amount:** `Belopp`
- **Description:** `Rubrik`
- **Balance:** `Saldo`

The format should be implemented as a new `HeaderBankFormat` in a dedicated
`nordea.py` module under `src/firefly_bank_importer/bank_formats/` and registered in
the bank-format registry, following the same pattern as the existing SEB and ICA formats.

Relevant requirements: UC-13, UC-14, FR-32 – FR-36.

## Branch
**Branch name:** `task/039-nordea-bank-format`
**Switch/create:** `git checkout -b task/039-nordea-bank-format`
**Make target:** `make branch-task f=TASK-039`

## Acceptance criteria
- [ ] `src/firefly_bank_importer/bank_formats/nordea.py` exists and defines a `NORDEA_FORMAT` using `HeaderBankFormat`.
- [ ] `NORDEA_FORMAT` is registered in the bank-format registry (`__init__.py`).
- [ ] `NORDEA_FORMAT.matches()` returns `True` for a Nordea header row and `False` for SEB/ICA headers.
- [ ] `NORDEA_FORMAT.build_column_mapping()` maps `Bokföringsdag` → `date_idx`, `Belopp` → `amount_idx`, `Rubrik` → `description_idx`, `Saldo` → `balance_idx`.
- [ ] Nordea date format `YYYY/MM/DD` is parsed correctly by the importer (no crash, correct date).
- [ ] Amount and balance values are normalised to US format before processing: comma decimal separator replaced by dot, thousands separators (space or period in Swedish format, e.g. `1 234,56` or `1.234,56`) stripped.
- [ ] Unit tests cover format detection, column mapping, and date/amount normalisation for Nordea rows.
- [ ] `make lint` and `make test` pass with no regressions and coverage is not lower than at task start.

## Completion

**Date:** 2026-03-30

**Summary:** Added `nordea.py` bank format with `NORDEA_FORMAT` using `date_format="%Y/%m/%d"`. Extended `HeaderBankFormat` in `base.py` with a `date_format` field and a `normalise_date()` method. Updated `_resolve_column_mapping` to return the full `BankFormat` object instead of just the name. Updated `split_file_in_place` to normalise dates in-place and `_collect_pending_rows` to accept a `normalise_date` callable. Added 28 new tests covering format detection, column mapping, date normalisation, split behaviour, and `process_csv` integration.

**Files changed:**

- `src/firefly_bank_importer/bank_formats/nordea.py` — created
- `src/firefly_bank_importer/bank_formats/base.py` — modified (added `date_format`, `normalise_date`)
- `src/firefly_bank_importer/bank_formats/__init__.py` — modified (registered `NORDEA_FORMAT`)
- `src/firefly_bank_importer/import_firefly.py` — modified (date normalisation in split and import)
- `tests/unit/test_nordea_format.py` — created
- `tests/unit/test_duplicate_detection.py` — modified (updated calls to `_collect_pending_rows`)
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-26, FR-5, FR-6, section 7)
- `docs/tasks/TASK-039-nordea-bank-format.md` — modified
- `CHANGELOG.md` — modified

**Branch:** `task/039-nordea-bank-format`

**Stage:** `git add src/firefly_bank_importer/bank_formats/nordea.py src/firefly_bank_importer/bank_formats/base.py src/firefly_bank_importer/bank_formats/__init__.py src/firefly_bank_importer/import_firefly.py tests/unit/test_nordea_format.py tests/unit/test_duplicate_detection.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-039-nordea-bank-format.md CHANGELOG.md`

**Commit:** `git commit -m "Add Nordea bank CSV format support"`
