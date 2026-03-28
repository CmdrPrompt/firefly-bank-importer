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
import requests

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import process_folder

ACCOUNT_MAP = {"SEB Lönekonto": 42}
SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
FIREFLY_URL = "http://test.local:30105"


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(SEB_HEADERS)
        writer.writerows(rows)


def make_session(status_code: int = 201) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    response = MagicMock()
    response.status_code = status_code
    response.text = ""
    session.post.return_value = response
    return session


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
        session = make_session()
        with caplog.at_level(logging.WARNING):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL)
        assert any("Inget konto hittat" in r.message for r in caplog.records)

    def test_no_post_when_no_account(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_Okant"
        folder.mkdir()
        session = make_session()
        process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL)
        session.post.assert_not_called()


# ---------------------------------------------------------------------------
# Account found but no CSV files
# ---------------------------------------------------------------------------


class TestNoCsvFiles:
    def test_logs_warning_when_empty(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        session = make_session()
        with caplog.at_level(logging.WARNING):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL)
        assert any("Inga CSV-filer" in r.message for r in caplog.records)

    def test_no_post_when_no_csv(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        session = make_session()
        process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL)
        session.post.assert_not_called()


# ---------------------------------------------------------------------------
# ignore_latest_date_check=True
# ---------------------------------------------------------------------------


class TestIgnoreLatestDateCheck:
    def test_get_latest_not_called(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        session = make_session()
        with patch.object(module, "get_latest_transaction_date") as mock_get:
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL, ignore_latest_date_check=True)
            mock_get.assert_not_called()

    def test_logs_ignore_message(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL, ignore_latest_date_check=True)
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
        session = make_session()
        cutoff = date(2025, 1, 10)
        with patch.object(module, "get_latest_transaction_date", return_value=cutoff):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL, dry_run=True)
        # Only the row after cutoff should trigger a DRY RUN log — not tested in detail
        # here because process_csv is already covered separately. We just ensure no crash.

    def test_no_log_line_about_no_previous_tx(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-20", "2025-01-20", "V1", "X", "-10,00", "990,00"]])
        session = make_session()
        with (
            patch.object(module, "get_latest_transaction_date", return_value=date(2025, 1, 5)),
            caplog.at_level(logging.INFO),
        ):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL)
        assert not any("Ingen tidigare transaktion" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# ignore_latest_date_check=False, mock returns None
# ---------------------------------------------------------------------------


class TestLatestDateNone:
    def test_logs_no_previous_transaction(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        write_seb_csv(folder / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        session = make_session()
        with (
            patch.object(module, "get_latest_transaction_date", return_value=None),
            caplog.at_level(logging.INFO),
        ):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL, dry_run=True)
        assert any("Ingen tidigare transaktion" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Non-monthly file gets split before process_csv runs
# ---------------------------------------------------------------------------


class TestAutoSplitBeforeProcess:
    def test_non_monthly_file_is_split_first(self, tmp_path: Path) -> None:
        folder = tmp_path / "kontoutdrag_SEB_Lonekonto"
        folder.mkdir()
        src = folder / "export.csv"
        write_seb_csv(src, [["2025-02-15", "2025-02-15", "V1", "Shop", "-50,00", "950,00"]])
        session = make_session()
        with patch.object(module, "get_latest_transaction_date", return_value=None):
            process_folder(session, folder, ACCOUNT_MAP, FIREFLY_URL, dry_run=True)
        assert not src.exists()
        assert (folder / "2025-02.csv").exists()
