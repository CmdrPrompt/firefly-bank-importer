"""Characterisation tests for the tqdm progress bar during import (UC-32, FR-67).

Patches module.tqdm with a lightweight fake so tests don't depend on real
terminal rendering, and assert the fake was constructed with the right total
and updated once per row processed.
"""

import csv
from datetime import date
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient, FireflyConnectionError

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import (
    PendingRow,
    _post_transfer,
    _post_unmatched_rows,
    main,
    process_csv,
)

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]


class FakeTqdm:
    instances: list["FakeTqdm"] = []

    def __init__(self, total: int = 0, desc: str = "", unit: str = "") -> None:
        self.total = total
        self.desc = desc
        self.updates = 0
        FakeTqdm.instances.append(self)

    def update(self, n: int = 1) -> None:
        self.updates += n

    def __enter__(self) -> "FakeTqdm":
        return self

    def __exit__(self, *args: Any) -> None:
        return None


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


@pytest.fixture(autouse=True)
def fake_tqdm(monkeypatch: pytest.MonkeyPatch) -> type[FakeTqdm]:
    FakeTqdm.instances = []
    monkeypatch.setattr(module, "tqdm", FakeTqdm)
    return FakeTqdm


class TestProcessCsvProgressBar:
    def test_live_import_updates_once_per_row(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(
            csv_path,
            [
                ["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"],
                ["2025-01-06", "2025-01-06", "V2", "Cafe", "-20,00", "970,00"],
            ],
        )
        client = make_client()
        process_csv(client, csv_path, account_id=1)
        assert len(FakeTqdm.instances) == 1
        assert FakeTqdm.instances[0].total == 2
        assert FakeTqdm.instances[0].updates == 2

    def test_dry_run_updates_once_per_row(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"]])
        client = make_client()
        process_csv(client, csv_path, account_id=1, dry_run=True)
        assert len(FakeTqdm.instances) == 1
        assert FakeTqdm.instances[0].total == 1
        assert FakeTqdm.instances[0].updates == 1

    def test_zero_rows_creates_empty_bar(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [])
        client = make_client()
        process_csv(client, csv_path, account_id=1)
        assert FakeTqdm.instances[0].total == 0
        assert FakeTqdm.instances[0].updates == 0

    def test_updates_even_when_post_raises(self, tmp_path: Path) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(
            csv_path,
            [
                ["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"],
                ["2025-01-06", "2025-01-06", "V2", "Cafe", "-20,00", "970,00"],
            ],
        )
        client = make_client()
        client.create_transaction.side_effect = FireflyConnectionError("boom")
        process_csv(client, csv_path, account_id=1)
        assert FakeTqdm.instances[0].updates == 2


class TestPostTransferProgressBar:
    def test_updates_on_success(self) -> None:
        client = make_client()
        pbar = FakeTqdm(total=1)
        payload = {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "X",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }
        _post_transfer(client, payload, dry_run=False, pbar=cast(Any, pbar))
        assert pbar.updates == 1

    def test_updates_even_when_post_raises(self) -> None:
        client = make_client()
        client.create_transaction.side_effect = FireflyConnectionError("boom")
        pbar = FakeTqdm(total=1)
        payload = {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "X",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }
        _post_transfer(client, payload, dry_run=False, pbar=cast(Any, pbar))
        assert pbar.updates == 1

    def test_updates_in_dry_run(self) -> None:
        client = make_client()
        pbar = FakeTqdm(total=1)
        payload = {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "X",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }
        _post_transfer(client, payload, dry_run=True, pbar=cast(Any, pbar))
        assert pbar.updates == 1
        client.create_transaction.assert_not_called()


class TestPostUnmatchedRowsProgressBar:
    def test_dry_run_updates_once_per_row(self) -> None:
        client = make_client()
        pbar = FakeTqdm(total=2)
        rows = [
            PendingRow(1, "Account A", "2025-01-05", "X", "-10.00", "seb", date(2025, 1, 5)),
            PendingRow(2, "Account B", "2025-01-05", "Y", "20.00", "seb", date(2025, 1, 5)),
        ]
        _post_unmatched_rows(client, rows, dry_run=True, pbar=cast(Any, pbar))
        assert pbar.updates == 2
        client.create_transaction.assert_not_called()


class TestMultiFolderProgressBar:
    def test_updates_once_per_transfer_and_unmatched_row(self, tmp_path: Path) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(
            folder_a / "2025-01.csv",
            [
                ["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"],
                ["2025-01-05", "2025-01-05", "V2", "Shop", "-50,00", "850,00"],
            ],
        )
        write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "100,00", "1100,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
        ):
            main(base_folder=str(tmp_path))

        # One shared progress bar for the multi-folder run: 1 transfer pair + 1 unmatched row.
        multi_bar = next(inst for inst in FakeTqdm.instances if inst.desc == "Import")
        assert multi_bar.total == 2
        assert multi_bar.updates == 2
