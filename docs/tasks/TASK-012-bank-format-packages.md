# TASK-012 Bank format packages and header-based field mapping

## Status
done

## Description
Move bank-specific CSV recognition and field-mapping logic out of the core importer
and into separate packages/modules. The importer should identify the correct format
by reading a CSV header and then use the selected package to map source columns to
normalized Firefly-relevant fields.

Relevant requirements: UC-13, UC-14, FR-32, FR-33, FR-34, FR-35, FR-36, NFR-9.

## Acceptance criteria
- [x] Bank-specific CSV format logic no longer lives directly in the core importer.
- [x] A shared contract/interface exists for bank format packages.
- [x] CSV format resolution is driven by the header row.
- [x] Split and import logic use normalized field mappings from the selected format package.
- [x] Unsupported headers still produce a clear skip/error path.
- [x] Existing SEB and ICA formats are migrated to the new package-based architecture.
- [x] Tests cover format selection and normalized field mapping.

## Completion
**Date:** 2026-03-28
**Summary:** Added a `bank_formats` package with a shared `BankFormat` contract, a reusable `HeaderBankFormat` implementation, and registered SEB/ICA format modules. Refactored the importer so split and import resolve bank formats through the registry and consume normalized `ColumnMapping` data instead of hardcoded bank-specific column names. Replaced the old CSV parsing tests with registry- and mapping-focused tests, and added dummy-bank extensibility tests that import a separate dummy bank-format module and register it dynamically to exercise both `process_csv` and `split_file_in_place` without changing the core importer. Verified with `uv run ruff check . && uv run ruff format --check . && uv run mypy src/` and `uv run pytest -q`.
**Files changed:**
- `src/firefly_bank_importer/bank_formats/__init__.py` — created
- `src/firefly_bank_importer/bank_formats/base.py` — created
- `src/firefly_bank_importer/bank_formats/ica.py` — created
- `src/firefly_bank_importer/bank_formats/seb.py` — created
- `src/firefly_bank_importer/import_firefly.py` — modified
- `tests/unit/test_csv_parsing.py` — modified
- `tests/unit/dummy_bank_format.py` — created
- `tests/unit/test_process_csv.py` — modified
- `tests/unit/test_split_file_in_place.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified
- `docs/tasks/TASK-012-bank-format-packages.md` — modified
**Stage:** `git add src/firefly_bank_importer/bank_formats/__init__.py src/firefly_bank_importer/bank_formats/base.py src/firefly_bank_importer/bank_formats/ica.py src/firefly_bank_importer/bank_formats/seb.py src/firefly_bank_importer/import_firefly.py tests/unit/test_csv_parsing.py tests/unit/dummy_bank_format.py tests/unit/test_process_csv.py tests/unit/test_split_file_in_place.py docs/REQUIREMENTS_import_firefly.md docs/tasks/TASK-012-bank-format-packages.md`
**Commit:** `git commit -m "Extract bank CSV formats into packages"`
