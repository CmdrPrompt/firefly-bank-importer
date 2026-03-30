"""Characterisation tests for _collect_pending_rows().

Documents current duplicate-detection behavior as-is.
SURPRISING behavior noted where ≤ comparison causes same-day transactions to be skipped.
"""

import csv
import io
from collections.abc import Iterator
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import _collect_pending_rows

DATUM_IDX = 0
TEXT_IDX = 1
BELOPP_IDX = 2
TYPE_IDX = None  # SEB-style, no type column


def _make_reader(rows: list[list[str]]) -> Iterator[list[str]]:
    content = "\n".join(";".join(row) for row in rows)
    return csv.reader(io.StringIO(content), delimiter=";")


def _make_rows(dates: list[str], text: str = "Test", belopp: str = "-100,00") -> list[list[str]]:
    return [[d, text, belopp] for d in dates]


def _collect(
    reader: Iterator[list[str]],
    latest: date | None = None,
    type_idx: int | None = TYPE_IDX,
) -> tuple[list[tuple[str, str, str]], int]:
    """Convenience wrapper: uses identity date normaliser for pre-ISO (YYYY-MM-DD) test data."""
    return _collect_pending_rows(reader, DATUM_IDX, TEXT_IDX, BELOPP_IDX, type_idx, latest, lambda x: x)


class TestCollectPendingRowsNoLatestDate:
    def test_all_rows_included_when_latest_date_none(self) -> None:
        rows = _make_rows(["2025-01-10", "2025-01-15", "2025-01-20"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader)
        assert len(pending) == 3
        assert skipped == 0

    def test_single_row_included_when_latest_date_none(self) -> None:
        rows = _make_rows(["2025-06-01"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader)
        assert len(pending) == 1
        assert skipped == 0

    def test_empty_file_returns_empty_pending(self) -> None:
        reader = _make_reader([])
        pending, skipped = _collect(reader)
        assert pending == []
        assert skipped == 0


class TestCollectPendingRowsDeduplication:
    def test_row_after_latest_date_is_included(self) -> None:
        rows = _make_rows(["2025-01-20"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2025, 1, 15))
        assert len(pending) == 1
        assert skipped == 0

    def test_row_before_latest_date_is_skipped(self) -> None:
        rows = _make_rows(["2025-01-10"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2025, 1, 15))
        assert len(pending) == 0
        assert skipped == 1

    def test_row_equal_to_latest_date_is_skipped(self) -> None:
        # SURPRISING: row ON the latest date is skipped (≤ comparison, not <).
        # This means new transactions posted on the same day as the existing latest
        # will be silently skipped on subsequent imports.
        rows = _make_rows(["2025-01-15"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2025, 1, 15))
        assert len(pending) == 0
        assert skipped == 1

    def test_mixed_rows_correct_split(self) -> None:
        rows = _make_rows(["2025-01-10", "2025-01-15", "2025-01-16", "2025-01-20"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2025, 1, 15))
        assert len(pending) == 2
        assert skipped == 2

    def test_all_rows_before_latest_date_all_skipped(self) -> None:
        rows = _make_rows(["2025-01-01", "2025-01-05", "2025-01-10"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2025, 6, 1))
        assert len(pending) == 0
        assert skipped == 3


class TestCollectPendingRowsYearBoundary:
    def test_year_boundary_old_year_skipped(self) -> None:
        rows = _make_rows(["2024-12-31"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2024, 12, 31))
        assert skipped == 1

    def test_year_boundary_new_year_included(self) -> None:
        rows = _make_rows(["2025-01-01"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2024, 12, 31))
        assert len(pending) == 1
        assert skipped == 0

    def test_year_boundary_mixed(self) -> None:
        rows = _make_rows(["2024-12-30", "2024-12-31", "2025-01-01", "2025-01-02"])
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=date(2024, 12, 31))
        assert len(pending) == 2
        assert skipped == 2


class TestCollectPendingRowsICAFormat:
    def test_ica_type_appended_to_description(self) -> None:
        rows = [["2025-01-15", "ICA Kortköp", "Kortköp", "-100,00"]]
        reader = _make_reader(rows)
        pending, _ = _collect(reader, type_idx=2)  # belopp at idx 3
        assert len(pending) == 1
        date_val, description, amount = pending[0]
        assert "[Kortköp]" in description
        assert "ICA Kortköp" in description

    def test_seb_no_type_in_description(self) -> None:
        rows = _make_rows(["2025-01-15"], text="Swish till Anna")
        reader = _make_reader(rows)
        pending, _ = _collect(reader)
        assert "[" not in pending[0][1]

    def test_pending_row_tuple_structure(self) -> None:
        rows = _make_rows(["2025-01-15"], text="  Spotify  ", belopp="-99,00")
        reader = _make_reader(rows)
        pending, _ = _collect(reader)
        tx_date, description, amount = pending[0]
        assert tx_date == "2025-01-15"
        assert description == "Spotify"  # stripped
        assert amount == "-99,00"


class TestCollectPendingRowsHypothesis:
    @given(
        dates=st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=0,
            max_size=50,
        ),
        latest=st.one_of(
            st.none(),
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
        ),
    )
    @settings(max_examples=300)
    def test_pending_plus_skipped_equals_total(self, dates: list[date], latest: date | None) -> None:
        rows = [[d.strftime("%Y-%m-%d"), "Test", "-100,00"] for d in dates]
        reader = _make_reader(rows)
        pending, skipped = _collect(reader, latest=latest)
        assert len(pending) + skipped == len(dates)

    @given(
        dates=st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=1,
            max_size=50,
        ),
        latest=st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
    )
    @settings(max_examples=300)
    def test_all_pending_dates_are_after_latest(self, dates: list[date], latest: date) -> None:
        rows = [[d.strftime("%Y-%m-%d"), "Test", "-100,00"] for d in dates]
        reader = _make_reader(rows)
        pending, _ = _collect(reader, latest=latest)
        for tx_date, _, _ in pending:
            assert tx_date > latest.strftime("%Y-%m-%d")

    @given(
        dates=st.lists(
            st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31)),
            min_size=1,
            max_size=50,
        ),
    )
    @settings(max_examples=200)
    def test_no_latest_date_all_rows_pending(self, dates: list[date]) -> None:
        rows = [[d.strftime("%Y-%m-%d"), "Test", "-100,00"] for d in dates]
        reader = _make_reader(rows)
        pending, skipped = _collect(reader)
        assert len(pending) == len(dates)
        assert skipped == 0
