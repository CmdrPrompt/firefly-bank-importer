"""Characterisation tests for automatic opening balance detection (UC-30, FR-65).

Covers _find_earliest_balance_row(), apply_auto_opening_balance(), and their
integration into process_folder(). Uses tmp_path for CSV fixtures and
unittest.mock for FireflyClient so no real API calls are made.
"""

import csv
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient, FireflyConnectionError

import firefly_bank_importer.bank_formats as bank_formats
import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.bank_formats.base import HeaderBankFormat
from firefly_bank_importer.import_firefly import (
    _find_earliest_balance_row,
    _opening_balance_floor,
    _render_opening_balance_result,
    apply_auto_opening_balance,
    process_folder,
)

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
NO_BALANCE_HEADERS = ["Booked", "Narrative", "Amount"]
NO_BALANCE_FORMAT = HeaderBankFormat(
    name="nobalance",
    required_headers=frozenset({"Booked", "Narrative", "Amount"}),
    date_header="Booked",
    description_header="Narrative",
    amount_header="Amount",
)

ACCOUNT_MAP = {"SEB Lönekonto": 42}


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


def make_client(balance: str | None = "0.00") -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": balance, "date": None}
    return client


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


@pytest.fixture()
def register_no_balance_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bank_formats,
        "_REGISTERED_BANK_FORMATS",
        bank_formats.get_registered_bank_formats() + (NO_BALANCE_FORMAT,),
    )


# ---------------------------------------------------------------------------
# _find_earliest_balance_row()
# ---------------------------------------------------------------------------


class TestFindEarliestBalanceRow:
    def test_returns_earliest_row_across_single_file(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-20", "2025-01-20", "V2", "New", "-20,00", "970,00"],
                ["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"],
            ],
        )
        result = _find_earliest_balance_row([csv_path])
        assert result == ("2025-01-05", "990.00")

    def test_returns_earliest_row_across_multiple_files(self, tmp_path: Path) -> None:
        file_a = tmp_path / "2025-02.csv"
        file_b = tmp_path / "2025-01.csv"
        write_csv(file_a, SEB_HEADERS, [["2025-02-01", "2025-02-01", "V2", "Feb", "-20,00", "970,00"]])
        write_csv(file_b, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Jan", "-10,00", "990,00"]])
        result = _find_earliest_balance_row([file_a, file_b])
        assert result == ("2025-01-05", "990.00")

    def test_returns_none_when_no_balance_header(self, tmp_path: Path, register_no_balance_format: None) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, NO_BALANCE_HEADERS, [["2025-01-05", "Old", "-10,00"]])
        result = _find_earliest_balance_row([csv_path])
        assert result is None

    def test_returns_none_for_empty_file_list(self) -> None:
        assert _find_earliest_balance_row([]) is None


# ---------------------------------------------------------------------------
# apply_auto_opening_balance()
# ---------------------------------------------------------------------------


class TestApplyAutoOpeningBalance:
    """`apply_auto_opening_balance` returns a structured `OpeningBalanceResult`
    (or `None`) and performs no `logging` calls itself (FR-71/FR-72); the
    caller renders the outcome via `_render_opening_balance_result` and
    derives an import-exclusion floor via `_opening_balance_floor`."""

    def test_sets_opening_balance_when_zero(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="0.00")
        result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)
        client.set_opening_balance.assert_called_once_with("42", "990.00", "2025-01-05")
        floor = _opening_balance_floor(result)
        assert floor is not None and floor.isoformat() == "2025-01-05"

    def test_sets_opening_balance_when_none(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance=None)
        result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)
        client.set_opening_balance.assert_called_once_with("42", "990.00", "2025-01-05")
        assert result is not None

    def test_skips_when_balance_not_zero(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="500.00")
        result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)
        client.set_opening_balance.assert_not_called()
        assert result is None

    def test_skips_when_no_balance_header_and_emits_no_logging(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, register_no_balance_format: None
    ) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, NO_BALANCE_HEADERS, [["2025-01-05", "Old", "-10,00"]])
        client = make_client(balance="0.00")
        with caplog.at_level(logging.WARNING):
            result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)
        client.set_opening_balance.assert_not_called()
        assert result is None
        assert caplog.records == []

    def test_dry_run_does_not_call_api_and_render_logs_the_outcome(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="0.00")
        with caplog.at_level(logging.INFO):
            result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=True)
        client.set_opening_balance.assert_not_called()
        floor = _opening_balance_floor(result)
        assert floor is not None and floor.isoformat() == "2025-01-05"
        assert caplog.records == []

        caplog.clear()
        with caplog.at_level(logging.INFO):
            _render_opening_balance_result(result)
        assert any("DRY RUN" in r.message and "990.00" in r.message for r in caplog.records)

    def test_get_opening_balance_error_is_handled_without_logging(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, SEB_HEADERS, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = MagicMock(spec=FireflyClient)
        client.get_opening_balance.side_effect = FireflyConnectionError("boom")
        with caplog.at_level(logging.WARNING):
            result = apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)
        client.set_opening_balance.assert_not_called()
        assert result is None
        assert caplog.records == []


# ---------------------------------------------------------------------------
# Integration with process_folder()
# ---------------------------------------------------------------------------


class TestProcessFolderIntegration:
    def test_earliest_row_excluded_from_import_when_balance_zero(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_csv(
            folder / "2025-01.csv",
            SEB_HEADERS,
            [
                ["2025-01-05", "2025-01-05", "V1", "Opening", "-10,00", "990,00"],
                ["2025-01-20", "2025-01-20", "V2", "Later", "-20,00", "970,00"],
            ],
        )
        client = make_client(balance="0.00")
        with patch.object(module, "get_latest_transaction_date", return_value=None):
            process_folder(client, folder, ACCOUNT_MAP)

        client.set_opening_balance.assert_called_once_with("42", "990.00", "2025-01-05")
        assert client.create_transaction.call_count == 1
        posted_payload = client.create_transaction.call_args.args[0]["transactions"][0]
        assert posted_payload["date"] == "2025-01-20"

    def test_all_rows_imported_when_balance_not_zero(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_csv(
            folder / "2025-01.csv",
            SEB_HEADERS,
            [
                ["2025-01-05", "2025-01-05", "V1", "Opening", "-10,00", "990,00"],
                ["2025-01-20", "2025-01-20", "V2", "Later", "-20,00", "970,00"],
            ],
        )
        client = make_client(balance="500.00")
        with patch.object(module, "get_latest_transaction_date", return_value=None):
            process_folder(client, folder, ACCOUNT_MAP)

        client.set_opening_balance.assert_not_called()
        assert client.create_transaction.call_count == 2
