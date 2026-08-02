"""Characterisation tests for _build_transaction_payload and the CLI
adapter's transaction-result rendering.

Documents current behavior as-is. TASK-067 moved OK/error line rendering
out of the (now pure) posting functions and into
`_render_transaction_result`, a thin CLI adapter helper that renders a
`TransactionResult` to the log exactly as `_log_tx_result` used to (FR-71/72).
"""

import logging

import pytest
from hypothesis import given
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import (
    _build_transaction_payload,
    _render_transaction_result,
)
from firefly_bank_importer.service import TransactionResult, TransactionStatus


def _render(transaction_type: str, amount_abs: float, tx_date: str, description: str, account_name: str) -> None:
    """Build a TransactionResult matching the old _log_tx_result() inputs
    and render it, for characterization tests that predate the event-based
    refactor and only care about the rendered OK line's content."""
    signed_amount = -amount_abs if transaction_type == "withdrawal" else amount_abs
    result = TransactionResult(
        date=tx_date,
        amount=signed_amount,
        account_id=1,
        status=TransactionStatus.OK,
        description=description,
        account_name=account_name,
    )
    _render_transaction_result(result, dry_run=False)


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


class TestRenderTransactionResult:
    def test_logs_ok_line(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _render("withdrawal", 100.0, "2025-01-01", "X", "1")
        assert any("[OK]" in r.message for r in caplog.records)

    def test_logs_transaction_type(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _render("deposit", 50.0, "2025-01-01", "Salary", "1")
        assert any("deposit" in r.message for r in caplog.records)

    def test_logs_amount(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _render("withdrawal", 42.50, "2025-01-01", "Test", "1")
        assert any("42.50" in r.message for r in caplog.records)

    def test_logs_account_name(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            _render("withdrawal", 42.50, "2025-01-01", "Test", "SEB Lönekonto Thomas")
        assert any("[SEB Lönekonto Thomas]" in r.message for r in caplog.records)
