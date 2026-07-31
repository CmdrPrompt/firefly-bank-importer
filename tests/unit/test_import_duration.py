"""Characterisation tests for import duration logging (UC-35, FR-70).

Covers main() logging total elapsed wall-clock time and average time per
transaction as the final log lines, after "Klar!".
"""

import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import main

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(SEB_HEADERS)
        writer.writerows(rows)


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": "100.00", "date": None}
    return client


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


class TestImportDurationLogging:
    def test_duration_logged_after_klar(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        write_seb_csv(tmp_path / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"]])
        client = make_client()
        account_map = {"Lonekonto": 1}

        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "find_account_id", return_value=1),
            patch.object(module.time, "monotonic", side_effect=[0.0, 312.0]),
            caplog.at_level(logging.INFO),
        ):
            main(base_folder=str(tmp_path))

        messages = [r.message for r in caplog.records]
        klar_idx = messages.index("Klar!")
        assert any("0:05:12" in m for m in messages[klar_idx + 1 :])

    def test_average_time_per_transaction_logged(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        write_seb_csv(
            tmp_path / "2025-01.csv",
            [
                ["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"],
                ["2025-01-06", "2025-01-06", "V2", "Cafe", "-20,00", "970,00"],
            ],
        )
        client = make_client()
        account_map = {"Lonekonto": 1}

        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "find_account_id", return_value=1),
            patch.object(module.time, "monotonic", side_effect=[0.0, 1.0]),
            caplog.at_level(logging.INFO),
        ):
            main(base_folder=str(tmp_path))

        messages = [r.message for r in caplog.records]
        assert any("0.50s/transaktion" in m for m in messages)

    def test_no_average_line_when_zero_transactions(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        write_seb_csv(tmp_path / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"]])
        client = make_client()
        account_map = {"Lonekonto": 1}

        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=date(2025, 1, 5)),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "find_account_id", return_value=1),
            caplog.at_level(logging.INFO),
        ):
            main(base_folder=str(tmp_path))

        messages = [r.message for r in caplog.records]
        assert not any("s/transaktion" in m for m in messages)
