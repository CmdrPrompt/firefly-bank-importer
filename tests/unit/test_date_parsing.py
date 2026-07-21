"""Characterisation tests for get_latest_transaction_date().

Documents current behavior as-is. Uses unittest.mock to avoid real HTTP calls.
"""

from datetime import date
from unittest.mock import MagicMock

from firefly_python_api import FireflyClient, FireflyConnectionError, TransactionRead
from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import get_latest_transaction_date


def _tx(tx_date: str, source_id: str | None = None, destination_id: str | None = None) -> TransactionRead:
    return TransactionRead(
        date=tx_date,
        amount="1.00",
        destination_name=None,
        category_name=None,
        source_name=None,
        source_id=source_id,
        destination_id=destination_id,
    )


def _make_client(transactions: list[TransactionRead] | None = None, raise_error: bool = False) -> FireflyClient:
    client = MagicMock(spec=FireflyClient)
    if raise_error:
        client.get_transactions_by_type.side_effect = FireflyConnectionError("error")
    else:
        client.get_transactions_by_type.return_value = transactions or []
    return client


class TestGetLatestTransactionDateHappyPath:
    def test_returns_max_date_for_account_as_source(self) -> None:
        client = _make_client([_tx("2025-01-01", source_id="1"), _tx("2025-03-15", source_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_max_date_for_account_as_destination(self) -> None:
        client = _make_client([_tx("2025-03-15", destination_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_date_type(self) -> None:
        client = _make_client([_tx("2025-01-01", source_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert isinstance(result, date)

    def test_ignores_transactions_belonging_to_other_accounts(self) -> None:
        client = _make_client(
            [
                _tx("2026-07-14", source_id="99", destination_id="8"),
                _tx("2025-01-05", source_id="1"),
            ]
        )
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 1, 5)

    def test_year_boundary_december(self) -> None:
        client = _make_client([_tx("2024-12-31", source_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2024, 12, 31)

    def test_year_boundary_january(self) -> None:
        client = _make_client([_tx("2025-01-01", source_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 1, 1)

    def test_end_of_month(self) -> None:
        client = _make_client([_tx("2025-01-31", source_id="1")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result == date(2025, 1, 31)


class TestGetLatestTransactionDateErrorCases:
    def test_connection_error_returns_none(self) -> None:
        client = _make_client(raise_error=True)
        result = get_latest_transaction_date(client, account_id=1)
        assert result is None

    def test_empty_list_returns_none(self) -> None:
        client = _make_client([])
        result = get_latest_transaction_date(client, account_id=1)
        assert result is None

    def test_no_matching_account_returns_none(self) -> None:
        client = _make_client([_tx("2025-01-05", source_id="99", destination_id="8")])
        result = get_latest_transaction_date(client, account_id=1)
        assert result is None

    def test_calls_get_transactions_by_type_with_withdrawal_deposit(self) -> None:
        client = _make_client([_tx("2025-01-15", source_id="42")])
        get_latest_transaction_date(client, account_id=42)
        args, kwargs = client.get_transactions_by_type.call_args
        assert args[0] == "withdrawal,deposit"


class TestGetLatestTransactionDateHypothesis:
    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),  # 28 is safe for all months
    )
    @settings(max_examples=200)
    def test_date_prefix_correctly_parsed(self, year: int, month: int, day: int) -> None:
        date_str = f"{year:04d}-{month:02d}-{day:02d}"
        client = _make_client([_tx(date_str, source_id="42")])
        result = get_latest_transaction_date(client, account_id=42)
        assert result == date(year, month, day)
