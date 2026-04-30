"""Tests for Nordea bank CSV format package.

Covers format detection, column mapping, date normalisation, split behaviour,
and process_csv integration for Nordea exports.
"""

import csv
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.bank_formats import get_registered_bank_formats, resolve_bank_format
from firefly_bank_importer.bank_formats.nordea import NORDEA_FORMAT
from firefly_bank_importer.import_firefly import process_csv, split_file_in_place

NORDEA_HEADERS = ["Bokföringsdag", "Belopp", "Avsändare", "Mottagare", "Namn", "Rubrik", "Saldo", "Valuta"]
NORDEA_REQUIRED = {"Bokföringsdag", "Belopp", "Rubrik"}


# ---------------------------------------------------------------------------
# Format registration
# ---------------------------------------------------------------------------


class TestNordeaRegistered:
    def test_nordea_is_registered(self) -> None:
        format_names = {fmt.name for fmt in get_registered_bank_formats()}
        assert "nordea" in format_names

    def test_all_three_formats_registered(self) -> None:
        format_names = {fmt.name for fmt in get_registered_bank_formats()}
        assert {"seb", "ica", "nordea"}.issubset(format_names)


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestNordeaMatches:
    def test_full_nordea_headers_resolve_to_nordea(self) -> None:
        fmt = resolve_bank_format(NORDEA_HEADERS)
        assert fmt is not None
        assert fmt.name == "nordea"

    def test_minimal_nordea_headers_resolve_to_nordea(self) -> None:
        fmt = resolve_bank_format(["Bokföringsdag", "Belopp", "Rubrik"])
        assert fmt is not None
        assert fmt.name == "nordea"

    def test_nordea_missing_rubrik_returns_none(self) -> None:
        assert resolve_bank_format(["Bokföringsdag", "Belopp"]) is None

    def test_nordea_missing_belopp_returns_none(self) -> None:
        assert resolve_bank_format(["Bokföringsdag", "Rubrik"]) is None

    def test_nordea_missing_bokforingsdag_returns_none(self) -> None:
        assert resolve_bank_format(["Belopp", "Rubrik"]) is None

    def test_seb_headers_do_not_match_nordea(self) -> None:
        fmt = resolve_bank_format(["Bokföringsdatum", "Text", "Belopp"])
        assert fmt is not None
        assert fmt.name != "nordea"

    def test_ica_headers_do_not_match_nordea(self) -> None:
        fmt = resolve_bank_format(["Datum", "Text", "Typ", "Belopp"])
        assert fmt is not None
        assert fmt.name != "nordea"


class TestNordeaMatchesHypothesis:
    @given(extra=st.lists(st.text(min_size=1, max_size=20), max_size=5))
    @settings(max_examples=200)
    def test_nordea_headers_with_extra_columns_still_nordea(self, extra: list[str]) -> None:
        headers = list(NORDEA_REQUIRED) + extra
        result = resolve_bank_format(headers)
        assert result is None or result.name in ("seb", "ica", "nordea")

    @given(headers=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10))
    @settings(max_examples=300)
    def test_random_headers_never_crash(self, headers: list[str]) -> None:
        result = resolve_bank_format(headers)
        assert result is None or result.name in ("seb", "ica", "nordea")


# ---------------------------------------------------------------------------
# Column mapping
# ---------------------------------------------------------------------------


class TestNordeaColumnMapping:
    def test_date_idx_points_to_bokforingsdag(self) -> None:
        mapping = NORDEA_FORMAT.build_column_mapping(NORDEA_HEADERS)
        assert mapping.date_idx == NORDEA_HEADERS.index("Bokföringsdag")

    def test_amount_idx_points_to_belopp(self) -> None:
        mapping = NORDEA_FORMAT.build_column_mapping(NORDEA_HEADERS)
        assert mapping.amount_idx == NORDEA_HEADERS.index("Belopp")

    def test_description_idx_points_to_rubrik(self) -> None:
        mapping = NORDEA_FORMAT.build_column_mapping(NORDEA_HEADERS)
        assert mapping.description_idx == NORDEA_HEADERS.index("Rubrik")

    def test_balance_idx_points_to_saldo(self) -> None:
        mapping = NORDEA_FORMAT.build_column_mapping(NORDEA_HEADERS)
        assert mapping.balance_idx == NORDEA_HEADERS.index("Saldo")

    def test_transaction_type_idx_is_none(self) -> None:
        mapping = NORDEA_FORMAT.build_column_mapping(NORDEA_HEADERS)
        assert mapping.transaction_type_idx is None


# ---------------------------------------------------------------------------
# Date normalisation
# ---------------------------------------------------------------------------


class TestNordeaDateNormalisation:
    def test_slash_date_normalised_to_iso(self) -> None:
        assert NORDEA_FORMAT.normalise_date("2026/03/01") == "2026-03-01"

    def test_slash_date_december(self) -> None:
        assert NORDEA_FORMAT.normalise_date("2025/12/31") == "2025-12-31"

    def test_slash_date_single_digit_month_and_day(self) -> None:
        assert NORDEA_FORMAT.normalise_date("2025/01/05") == "2025-01-05"

    def test_already_iso_date_returned_unchanged(self) -> None:
        """Regression: split files store ISO dates — normalise_date must not crash on them."""
        assert NORDEA_FORMAT.normalise_date("2025-01-01") == "2025-01-01"

    def test_already_iso_date_december(self) -> None:
        assert NORDEA_FORMAT.normalise_date("2025-12-31") == "2025-12-31"

    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
    )
    @settings(max_examples=200)
    def test_any_valid_date_normalises_without_crash(self, year: int, month: int, day: int) -> None:
        raw = f"{year}/{month:02d}/{day:02d}"
        result = NORDEA_FORMAT.normalise_date(raw)
        assert result == f"{year}-{month:02d}-{day:02d}"

    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
    )
    @settings(max_examples=200)
    def test_already_iso_date_idempotent(self, year: int, month: int, day: int) -> None:
        iso = f"{year}-{month:02d}-{day:02d}"
        assert NORDEA_FORMAT.normalise_date(iso) == iso


# ---------------------------------------------------------------------------
# split_file_in_place – Nordea
# ---------------------------------------------------------------------------


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        csv.writer(f, delimiter=";").writerows([headers] + rows)


def _read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
        rows = list(reader)
    return headers, rows


class TestNordeaSplitFileInPlace:
    def test_creates_monthly_files_with_dash_separator(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [
                ["2026/01/10", "-35,00", "710318", "", "", "Vardagspaket", "100,00", "SEK"],
                ["2026/02/01", "-35,00", "710318", "", "", "Vardagspaket", "65,00", "SEK"],
            ],
        )
        split_file_in_place(src)
        assert (tmp_path / "2026-01.csv").exists()
        assert (tmp_path / "2026-02.csv").exists()

    def test_slash_filenames_not_created(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [["2026/03/01", "-35,00", "", "", "", "Vardagspaket", "109,77", "SEK"]],
        )
        split_file_in_place(src)
        slash_files = list(tmp_path.glob("????/??.*"))
        assert slash_files == []

    def test_original_file_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [["2026/03/01", "-35,00", "", "", "", "Vardagspaket", "109,77", "SEK"]],
        )
        split_file_in_place(src)
        assert not src.exists()

    def test_date_normalised_to_iso_in_output(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [["2026/03/01", "-35,00", "", "", "", "Vardagspaket", "109,77", "SEK"]],
        )
        split_file_in_place(src)
        _, rows = _read_csv(tmp_path / "2026-03.csv")
        assert rows[0][0] == "2026-03-01"

    def test_amount_normalised_to_dot_decimal(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [["2026/03/01", "-1 234,56", "", "", "", "Handel", "10 000,00", "SEK"]],
        )
        split_file_in_place(src)
        _, rows = _read_csv(tmp_path / "2026-03.csv")
        assert rows[0][1] == "-1234.56"
        assert rows[0][6] == "10000.00"

    def test_rows_sorted_chronologically(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        _write_csv(
            src,
            NORDEA_HEADERS,
            [
                ["2026/03/25", "-10,00", "", "", "", "Later", "90,00", "SEK"],
                ["2026/03/01", "-35,00", "", "", "", "Earlier", "125,00", "SEK"],
            ],
        )
        split_file_in_place(src)
        _, rows = _read_csv(tmp_path / "2026-03.csv")
        assert rows[0][0] == "2026-03-01"
        assert rows[1][0] == "2026-03-25"


# ---------------------------------------------------------------------------
# process_csv – Nordea date parsing
# ---------------------------------------------------------------------------


class TestNordeaProcessCsv:
    def _write_monthly_nordea_csv(self, path: Path, rows: list[list[str]]) -> None:
        _write_csv(path, NORDEA_HEADERS, rows)

    def test_nordea_slash_date_in_monthly_file_imports_without_crash(self, tmp_path: Path) -> None:
        """A Nordea monthly file placed directly (without split) uses YYYY/MM/DD dates."""
        csv_path = tmp_path / "2026-03.csv"
        self._write_monthly_nordea_csv(
            csv_path,
            [["2026/03/01", "-35,00", "", "", "", "Vardagspaket", "109,77", "SEK"]],
        )
        client = MagicMock()
        with patch("firefly_bank_importer.import_firefly.create_transaction") as mock_create:
            process_csv(client, csv_path, account_id=1, dry_run=True)
        mock_create.assert_called_once()

    def test_nordea_latest_date_skips_old_rows(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2026-03.csv"
        self._write_monthly_nordea_csv(
            csv_path,
            [
                ["2026/03/01", "-35,00", "", "", "", "Old", "144,77", "SEK"],
                ["2026/03/15", "-10,00", "", "", "", "New", "134,77", "SEK"],
            ],
        )
        client = MagicMock()
        with patch("firefly_bank_importer.import_firefly.create_transaction") as mock_create:
            process_csv(
                client,
                csv_path,
                account_id=1,
                dry_run=True,
                latest_date=date(2026, 3, 1),
            )
        mock_create.assert_called_once()
        assert "New" in str(mock_create.call_args)
