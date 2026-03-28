"""Characterisation tests for process_csv().

Documents current behavior as-is. Uses tmp_path for CSV files and
unittest.mock for the HTTP session so no real API calls are made.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

import firefly_bank_importer.bank_formats as bank_formats
import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import process_csv
from tests.unit.dummy_bank_format import DUMMY_FORMAT, DUMMY_HEADERS

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
ICA_HEADERS = ["Datum", "Text", "Typ", "Belopp"]
ACCOUNT_ID = 42
FIREFLY_URL = "http://test.local:30105"


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


def make_session(status_code: int = 201) -> MagicMock:
    session = MagicMock(spec=requests.Session)
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.text = ""
    session.post.return_value = mock_response
    return session


@pytest.fixture(autouse=True)
def no_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


@pytest.fixture()
def register_dummy_bank_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bank_formats,
        "_REGISTERED_BANK_FORMATS",
        bank_formats.get_registered_bank_formats() + (DUMMY_FORMAT,),
    )


class TestDryRunSeb:
    def test_no_post_calls_in_dry_run(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "Shop", "-100,00", "900,00"]],
        )
        session = make_session()
        process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        session.post.assert_not_called()

    def test_dry_run_logs_transaction(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "Kaffebar", "-35,00", "900,00"]],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        assert any("DRY RUN" in r.message for r in caplog.records)

    def test_dry_run_logs_correct_count(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-10", "2025-01-10", "V1", "A", "-10,00", "990,00"],
                ["2025-01-15", "2025-01-15", "V2", "B", "-20,00", "970,00"],
            ],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        assert any("2 transaktioner" in r.message for r in caplog.records)


class TestDryRunIca:
    def test_ica_type_appended_to_description(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-03.csv"
        write_csv(
            csv_path,
            ICA_HEADERS,
            [["2025-03-10", "ICA Maxi", "Köp", "-200,00"]],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        assert any("ICA Maxi [Köp]" in r.message for r in caplog.records)

    def test_ica_no_post_calls(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-03.csv"
        write_csv(
            csv_path,
            ICA_HEADERS,
            [["2025-03-10", "Mat", "Köp", "-150,00"]],
        )
        session = make_session()
        process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        session.post.assert_not_called()


class TestUnknownFormat:
    def test_no_post_on_unknown_format(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, ["Col1", "Col2"], [["val1", "val2"]])
        session = make_session()
        process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        session.post.assert_not_called()

    def test_unknown_format_logs_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(csv_path, ["Col1", "Col2"], [["val1", "val2"]])
        session = make_session()
        with caplog.at_level(logging.ERROR):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL)
        assert any("Okant CSV-format" in r.message for r in caplog.records)


class TestExtensibilityWithRegisteredDummyBank:
    def test_dummy_bank_format_works_through_process_csv(
        self,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        register_dummy_bank_format: None,
    ) -> None:
        csv_path = tmp_path / "2025-07.csv"
        write_csv(
            csv_path,
            DUMMY_HEADERS,
            [["2025-07-10", "Coffee", "Card", "-45,50", "2 345,00"]],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True)
        session.post.assert_not_called()
        assert any("Format: DUMMYBANK" in r.message for r in caplog.records)
        assert any("Coffee [Card]" in r.message for r in caplog.records)


class TestLatestDateFiltering:
    def test_latest_date_none_includes_all_rows(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-05", "2025-01-05", "V1", "A", "-10,00", "990,00"],
                ["2025-01-15", "2025-01-15", "V2", "B", "-20,00", "970,00"],
            ],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=True, latest_date=None)
        assert any("2 transaktioner" in r.message for r in caplog.records)

    def test_rows_on_or_before_latest_date_skipped(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"],
                ["2025-01-15", "2025-01-15", "V2", "New", "-20,00", "970,00"],
            ],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(
                session,
                csv_path,
                ACCOUNT_ID,
                FIREFLY_URL,
                dry_run=True,
                latest_date=date(2025, 1, 5),
            )
        # Only the row after latest_date should be processed
        assert any("1 transaktioner" in r.message for r in caplog.records)

    def test_row_exactly_on_latest_date_is_skipped(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "Exact", "-50,00", "950,00"]],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(
                session,
                csv_path,
                ACCOUNT_ID,
                FIREFLY_URL,
                dry_run=True,
                latest_date=date(2025, 1, 10),
            )
        assert any("0 transaktioner" in r.message for r in caplog.records)

    def test_skipped_count_logged_when_rows_skipped(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"],
                ["2025-01-20", "2025-01-20", "V2", "New", "-20,00", "970,00"],
            ],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(
                session,
                csv_path,
                ACCOUNT_ID,
                FIREFLY_URL,
                dry_run=True,
                latest_date=date(2025, 1, 10),
            )
        assert any("Hoppade over" in r.message for r in caplog.records)

    def test_no_skipped_log_when_nothing_skipped(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [["2025-01-15", "2025-01-15", "V1", "New", "-10,00", "990,00"]],
        )
        session = make_session()
        with caplog.at_level(logging.INFO):
            process_csv(
                session,
                csv_path,
                ACCOUNT_ID,
                FIREFLY_URL,
                dry_run=True,
                latest_date=date(2025, 1, 10),
            )
        assert not any("Hoppade over" in r.message for r in caplog.records)


class TestRealMode:
    def test_post_called_once_per_transaction(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [
                ["2025-01-10", "2025-01-10", "V1", "A", "-10,00", "990,00"],
                ["2025-01-15", "2025-01-15", "V2", "B", "-20,00", "970,00"],
            ],
        )
        session = make_session(status_code=201)
        process_csv(session, csv_path, ACCOUNT_ID, FIREFLY_URL, dry_run=False)
        assert session.post.call_count == 2

    def test_post_not_called_when_no_pending(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_csv(
            csv_path,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "Old", "-10,00", "990,00"]],
        )
        session = make_session()
        process_csv(
            session,
            csv_path,
            ACCOUNT_ID,
            FIREFLY_URL,
            dry_run=False,
            latest_date=date(2025, 1, 10),
        )
        session.post.assert_not_called()
