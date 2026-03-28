"""Characterisation tests for get_latest_transaction_date().

Documents current behavior as-is. Uses unittest.mock to avoid real HTTP calls.
"""

from datetime import date
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import get_latest_transaction_date


def _make_session(status_code: int = 200, json_body: object = None) -> MagicMock:
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = json_body or {}
    session = MagicMock()
    session.get.return_value = response
    return session


def _make_transaction_response(date_str: str) -> dict[str, object]:
    return {"data": [{"attributes": {"transactions": [{"date": date_str}]}}]}


class TestGetLatestTransactionDateHappyPath:
    def test_returns_date_from_iso_datetime(self) -> None:
        session = _make_session(200, _make_transaction_response("2025-03-15T12:00:00+00:00"))
        result = get_latest_transaction_date(session, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_date_from_date_only_string(self) -> None:
        session = _make_session(200, _make_transaction_response("2025-03-15"))
        result = get_latest_transaction_date(session, account_id=1)
        assert result == date(2025, 3, 15)

    def test_returns_date_type(self) -> None:
        session = _make_session(200, _make_transaction_response("2025-01-01"))
        result = get_latest_transaction_date(session, account_id=1)
        assert isinstance(result, date)

    def test_year_boundary_december(self) -> None:
        session = _make_session(200, _make_transaction_response("2024-12-31"))
        result = get_latest_transaction_date(session, account_id=1)
        assert result == date(2024, 12, 31)

    def test_year_boundary_january(self) -> None:
        session = _make_session(200, _make_transaction_response("2025-01-01"))
        result = get_latest_transaction_date(session, account_id=1)
        assert result == date(2025, 1, 1)

    def test_end_of_month(self) -> None:
        session = _make_session(200, _make_transaction_response("2025-01-31"))
        result = get_latest_transaction_date(session, account_id=1)
        assert result == date(2025, 1, 31)


class TestGetLatestTransactionDateErrorCases:
    def test_non_200_status_returns_none(self) -> None:
        session = _make_session(status_code=404)
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None

    def test_500_status_returns_none(self) -> None:
        session = _make_session(status_code=500)
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None

    def test_empty_data_list_returns_none(self) -> None:
        session = _make_session(200, {"data": []})
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None

    def test_missing_data_key_returns_none(self) -> None:
        session = _make_session(200, {})
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None

    def test_empty_transactions_list_returns_none(self) -> None:
        session = _make_session(200, {"data": [{"attributes": {"transactions": []}}]})
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None

    def test_missing_transactions_key_returns_none(self) -> None:
        session = _make_session(200, {"data": [{"attributes": {}}]})
        result = get_latest_transaction_date(session, account_id=1)
        assert result is None


class TestGetLatestTransactionDateHypothesis:
    @given(
        year=st.integers(min_value=2000, max_value=2099),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),  # 28 is safe for all months
    )
    @settings(max_examples=200)
    def test_date_prefix_correctly_parsed(self, year: int, month: int, day: int) -> None:
        date_str = f"{year:04d}-{month:02d}-{day:02d}T00:00:00+00:00"
        session = _make_session(200, _make_transaction_response(date_str))
        result = get_latest_transaction_date(session, account_id=42)
        assert result == date(year, month, day)
