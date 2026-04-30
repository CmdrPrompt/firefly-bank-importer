"""Characterisation tests for get_latest_transaction_date().

Documents current behavior as-is. Uses unittest.mock to avoid real HTTP calls.
"""

from datetime import date
from unittest.mock import MagicMock

from firefly_python_api import FireflyClient, FireflyConnectionError
from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import get_latest_transaction_date


def _make_client(date_str: str | None = None, raise_error: bool = False) -> FireflyClient:
    client = MagicMock(spec=FireflyClient)
    if raise_error:
        client.get_latest_transaction_date.side_effect = FireflyConnectionError("error")
    else:
        client.get_latest_transaction_date.return_value = date_str
    return client


class TestGetLatestTransactionDateHappyPath:
    def test_returns_date_from_iso_datetime(self) -> None:
        client = _make_client("2025-03-15")
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_date_from_date_only_string(self) -> None:
        client = _make_client("2025-03-15")
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_date_type(self) -> None:
        client = _make_client("2025-01-01")
        result = get_latest_transaction_date(client, account_id=1)
        assert isinstance(result, date)

    def test_year_boundary_december(self) -> None:
        client = _make_client("2024-12-31")
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2024, 12, 31)

    def test_year_boundary_january(self) -> None:
        client = _make_client("2025-01-01")
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 1, 1)

    def test_end_of_month(self) -> None:
        client = _make_client("2025-01-31")
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 1, 31)


class TestGetLatestTransactionDateErrorCases:
    def test_connection_error_returns_none(self) -> None:
        client = _make_client(raise_error=True)
        result = get_latest_transaction_date(client, account_id=1)
        assert result is None

    def test_empty_data_list_returns_none(self) -> None:
        client = _make_client(date_str=None)
        result = get_latest_transaction_date(client, account_id=1)
        assert result is None

    def test_passes_account_id_as_string(self) -> None:
        client = _make_client("2025-01-15")
        get_latest_transaction_date(client, account_id=42)
        client.get_latest_transaction_date.assert_called_once_with("42")


class TestGetLatestTransactionDateHypothesis:
    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),  # 28 is safe for all months
    )
    @settings(max_examples=200)
    def test_date_prefix_correctly_parsed(self, year: int, month: int, day: int) -> None:
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        client = _make_client(date_str)
        result = get_latest_transaction_date(client, account_id=42)
        assert result == date(year, month, day)
