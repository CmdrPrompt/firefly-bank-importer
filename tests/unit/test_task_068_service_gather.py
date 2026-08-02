"""Characterisation tests for TASK-068's self-contained, logging-free
gather helpers in `firefly_bank_importer.service` used by the public
`run_multi_folder_import` entry point.

These mirror the CLI's own `import_firefly._gather_folder_pending` and its
collaborators, but must never call `logging`, and must not depend on
`import_firefly` (FR-71/FR-73). All scenarios run against a mocked
`FireflyClient`; no real HTTP calls are made.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from firefly_python_api import FireflyClient, FireflyConnectionError

from firefly_bank_importer.service import (
    Account,
    _account_id_for_folder,
    _collect_csv_pending_rows,
    _compute_latest_date_floor,
    _gather_folder_pending,
    _latest_transaction_date,
    fetch_accounts_from_firefly,
)

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(SEB_HEADERS)
        writer.writerows(rows)


def make_client(balance: str | None = "100.00") -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": balance, "date": None}
    return client


class TestFetchAccountsFromFirefly:
    def test_returns_account_dicts_from_raw_client_response(self) -> None:
        client = make_client()
        client.get_asset_accounts.return_value = [{"id": "1", "name": "Lonekonto"}]
        accounts: list[Account] = fetch_accounts_from_firefly(client)
        assert accounts == [{"id": 1, "name": "Lonekonto", "type": "asset"}]


class TestLatestTransactionDateSilent:
    def test_returns_max_date_for_matching_account(self) -> None:
        client = make_client()
        client.get_transactions_by_type.return_value = [
            {"date": "2025-01-05", "source_id": "42", "destination_id": "9"},
            {"date": "2025-02-10", "source_id": "1", "destination_id": "42"},
        ]
        result = _latest_transaction_date(client, 42)
        assert result == date(2025, 2, 10)

    def test_returns_none_when_no_matching_transactions(self) -> None:
        client = make_client()
        client.get_transactions_by_type.return_value = []
        assert _latest_transaction_date(client, 42) is None

    def test_returns_none_silently_on_connection_error(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        client.get_transactions_by_type.side_effect = FireflyConnectionError("boom")
        with caplog.at_level(logging.WARNING):
            result = _latest_transaction_date(client, 42)
        assert result is None
        assert caplog.records == []


class TestAccountIdForFolderSilent:
    def test_returns_none_when_no_match(self) -> None:
        assert _account_id_for_folder("kontoutdrag_Unknown", {"Lonekonto": 1}) is None

    def test_returns_single_match(self) -> None:
        assert _account_id_for_folder("kontoutdrag_Lonekonto", {"Lonekonto": 1}) == 1

    def test_ambiguous_match_prefers_longest_name_silently(self, caplog: pytest.LogCaptureFixture) -> None:
        account_map = {"Lonekonto": 1, "Lonekonto Extra": 2}
        with caplog.at_level(logging.INFO):
            result = _account_id_for_folder("kontoutdrag_Lonekonto Extra", account_map)
        assert result == 2
        assert caplog.records == []


class TestCollectCsvPendingRowsSilent:
    def test_returns_empty_for_unresolvable_format(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [])
        csv_path.write_text("Col1;Col2\nval1;val2\n", encoding="utf-8")
        with caplog.at_level(logging.ERROR):
            rows, skipped = _collect_csv_pending_rows(csv_path, 42, "Lonekonto", None)
        assert rows == []
        assert skipped == 0
        assert caplog.records == []


class TestGatherFolderPendingSilent:
    def test_returns_empty_when_no_account_matches(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_Unknown"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"]])
        client = make_client()
        rows = _gather_folder_pending(client, folder, {"Lonekonto": 1}, dry_run=True, ignore_latest_date_check=True)
        assert rows == []

    def test_returns_empty_when_no_csv_files(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_Lonekonto"
        folder.mkdir()
        client = make_client()
        rows = _gather_folder_pending(client, folder, {"Lonekonto": 1}, dry_run=True, ignore_latest_date_check=True)
        assert rows == []

    def test_period_filter_restricts_to_single_month(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Jan", "-10,00", "990,00"]])
        write_seb_csv(folder / "2025-02.csv", [["2025-02-05", "2025-02-05", "V1", "Feb", "-20,00", "970,00"]])
        client = make_client()
        rows = _gather_folder_pending(
            client, folder, {"Lonekonto": 1}, dry_run=True, ignore_latest_date_check=True, period="2025-02"
        )
        assert [row.description for row in rows] == ["Feb"]


class TestComputeLatestDateFloorSilent:
    def test_opening_balance_floor_overrides_earlier_latest_date(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="0.00")
        client.get_transactions_by_type.return_value = [
            {"date": "2025-01-01", "source_id": "42", "destination_id": "9"}
        ]
        floor = _compute_latest_date_floor(client, 42, [csv_path], dry_run=False, ignore_latest_date_check=False)
        # The auto-detected opening balance's excluded row (2025-01-05) is later than
        # the latest known transaction date (2025-01-01), so it becomes the floor.
        assert floor == date(2025, 1, 5)
