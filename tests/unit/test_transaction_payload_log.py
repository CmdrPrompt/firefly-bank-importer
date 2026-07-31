"""Characterisation tests for _build_transaction_payload and _log_tx_result.

Documents current behavior as-is.
"""

import logging

import pytest
from hypothesis import given
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import (
    _build_transaction_payload,
    _log_tx_result,
)


class TestBuildTransactionPayloadWithdrawal:
    def test_negative_amount_gives_withdrawal_type(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Groceries", -100.0, 42)
        assert payload["type"] == "withdrawal"

    def test_negative_amount_sets_source_id(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Groceries", -100.0, 42)
        assert payload["source_id"] == "42"

    def test_negative_amount_no_destination_id(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Groceries", -100.0, 42)
        assert "destination_id" not in payload

    def test_negative_amount_formatted_as_absolute(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Groceries", -100.5, 42)
        assert payload["amount"] == "100.50"


class TestBuildTransactionPayloadDeposit:
    def test_positive_amount_gives_deposit_type(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Salary", 25000.0, 7)
        assert payload["type"] == "deposit"

    def test_positive_amount_sets_destination_id(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Salary", 25000.0, 7)
        assert payload["destination_id"] == "7"

    def test_positive_amount_no_source_id(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Salary", 25000.0, 7)
        assert "source_id" not in payload

    def test_positive_amount_formatted_to_two_decimals(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Salary", 25000.0, 7)
        assert payload["amount"] == "25000.00"


class TestBuildTransactionPayloadRequiredFields:
    def test_date_field_present(self) -> None:
        payload = _build_transaction_payload("2025-06-15", "Test", -10.0, 1)
        assert payload["date"] == "2025-06-15"

    def test_description_field_present(self) -> None:
        payload = _build_transaction_payload("2025-06-15", "Test desc", -10.0, 1)
        assert payload["description"] == "Test desc"

    def test_currency_code_is_sek(self) -> None:
        payload = _build_transaction_payload("2025-06-15", "Test", -10.0, 1)
        assert payload["currency_code"] == "SEK"

    def test_amount_two_decimal_places_withdrawal(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Test", -1.0, 1)
        assert "." in payload["amount"]
        assert len(payload["amount"].split(".")[1]) == 2

    def test_amount_two_decimal_places_deposit(self) -> None:
        payload = _build_transaction_payload("2025-01-01", "Test", 1.0, 1)
        assert "." in payload["amount"]
        assert len(payload["amount"].split(".")[1]) == 2


class TestBuildTransactionPayloadHypothesis:
    @given(amount=st.floats(min_value=-1e6, max_value=-0.01))
    def test_negative_amount_always_withdrawal(self, amount: float) -> None:
        payload = _build_transaction_payload("2025-01-01", "X", amount, 1)
        assert payload["type"] == "withdrawal"
        assert "source_id" in payload
        assert "destination_id" not in payload

    @given(amount=st.floats(min_value=0.01, max_value=1e6))
    def test_positive_amount_always_deposit(self, amount: float) -> None:
        payload = _build_transaction_payload("2025-01-01", "X", amount, 1)
        assert payload["type"] == "deposit"
        assert "destination_id" in payload
        assert "source_id" not in payload


class TestLogTxResult:
    def test_logs_ok_line(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _log_tx_result("withdrawal", 100.0, "2025-01-01", "X", "1")
        assert any("[OK]" in r.message for r in caplog.records)

    def test_logs_transaction_type(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _log_tx_result("deposit", 50.0, "2025-01-01", "Salary", "1")
        assert any("deposit" in r.message for r in caplog.records)

    def test_logs_amount(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _log_tx_result("withdrawal", 42.50, "2025-01-01", "Test", "1")
        assert any("42.50" in r.message for r in caplog.records)

    def test_logs_account_name(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _log_tx_result("withdrawal", 42.50, "2025-01-01", "Test", "SEB Lönekonto Thomas")
        assert any("[SEB Lönekonto Thomas]" in r.message for r in caplog.records)
