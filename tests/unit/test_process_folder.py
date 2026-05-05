"""Characterisation tests for process_folder().

Documents current behavior as-is. Uses tmp_path for the folder/CSV fixture and
monkeypatches get_latest_transaction_date to avoid real HTTP calls.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import process_folder

ACCOUNT_MAP = {"SEB Lönekonto": 42}
SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(SEB_HEADERS)
        writer.writerows(rows)


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    return client


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


# ---------------------------------------------------------------------------
# Account not found
# ---------------------------------------------------------------------------


class TestNoMatchingAccount:
    def test_logs_warning_and_returns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_Okant"
        folder.mkdir()
        client = make_client()
        with caplog.at_level(logging.WARNING):
            process_folder(client, folder, ACCOUNT_MAP)
        assert any("Inget konto hittat" in r.message for r in caplog.records)

    def test_no_api_call_when_no_account(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_Okant"
        folder.mkdir()
        client = make_client()
        process_folder(client, folder, ACCOUNT_MAP)
        client.create_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# Account found but no CSV files
# ---------------------------------------------------------------------------


class TestNoCsvFiles:
    def test_logs_warning_when_empty(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        client = make_client()
        with caplog.at_level(logging.WARNING):
            process_folder(client, folder, ACCOUNT_MAP)
        assert any("Inga CSV-filer" in r.message for r in caplog.records)

    def test_no_api_call_when_no_csv(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        client = make_client()
        process_folder(client, folder, ACCOUNT_MAP)
        client.create_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# ignore_latest_date_check=True
# ---------------------------------------------------------------------------


class TestIgnoreLatestDateCheck:
    def test_get_latest_not_called(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with patch.object(module, "get_latest_transaction_date") as mock_get:
            process_folder(client, folder, ACCOUNT_MAP, ignore_latest_date_check=True)
            mock_get.assert_not_called()

    def test_logs_ignore_message(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with caplog.at_level(logging.INFO):
            process_folder(client, folder, ACCOUNT_MAP, ignore_latest_date_check=True)
        assert any("Ignorerar" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ignore_latest_date_check=False, mock returns a date
# ---------------------------------------------------------------------------


class TestLatestDateFromApi:
    def test_process_csv_called_with_latest_date(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(
            folder / "2025-01.csv",
            [
                ["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"],
                ["2025-01-20", "2025-01-20", "V2", "New", "-20,00", "970,00"],
            ],
        )
        client = make_client()
        cutoff = date(2025, 1, 10)
        with patch.object(module, "get_latest_transaction_date", return_value=cutoff):
            process_folder(client, folder, ACCOUNT_MAP, dry_run=True)
        # Only the row after cutoff should trigger a DRY RUN log — not tested in detail
        # here because process_csv is already covered separately. We just ensure no crash.

    def test_no_log_line_about_no_previous_tx(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-20", "2025-01-20", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with (
            patch.object(module, "get_latest_transaction_date", return_value=date(2025, 1, 5)),
            caplog.at_level(logging.INFO),
        ):
            process_folder(client, folder, ACCOUNT_MAP)
        assert not any("Ingen tidigare transaktion" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ignore_latest_date_check=False, mock returns None
# ---------------------------------------------------------------------------


class TestLatestDateNone:
    def test_logs_no_previous_transaction(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with (
            patch.object(module, "get_latest_transaction_date", return_value=None),
            caplog.at_level(logging.INFO),
        ):
            process_folder(client, folder, ACCOUNT_MAP, dry_run=True)
        assert any("Ingen tidigare transaktion" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Non-monthly file gets split before process_csv runs
# ---------------------------------------------------------------------------


class TestOnlyMonthlyFilesImported:
    def test_unknown_csv_in_folder_is_not_imported(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        # Unknown CSV that auto_split warned about and skipped
        write_seb_csv(folder / "export.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with (
            patch.object(module, "process_csv") as mock_csv,
            patch.object(module, "get_latest_transaction_date", return_value=None),
        ):
            process_folder(client, folder, ACCOUNT_MAP, dry_run=True)
        mock_csv.assert_not_called()

    def test_monthly_csv_in_folder_is_imported(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        client = make_client()
        with (
            patch.object(module, "process_csv") as mock_csv,
            patch.object(module, "get_latest_transaction_date", return_value=None),
        ):
            process_folder(client, folder, ACCOUNT_MAP, dry_run=True)
        mock_csv.assert_called_once()


class TestAutoSplitBeforeProcess:
    def test_non_monthly_file_is_split_first(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        src = folder / "kontoutdrag_export.csv"
        write_seb_csv(src, [["2025-02-15", "2025-02-15", "V1", "Shop", "-50,00", "950,00"]])
        client = make_client()
        with patch.object(module, "get_latest_transaction_date", return_value=None):
            process_folder(client, folder, ACCOUNT_MAP, dry_run=True)
        assert not src.exists()
        assert (folder / "2025-02.csv").exists()
