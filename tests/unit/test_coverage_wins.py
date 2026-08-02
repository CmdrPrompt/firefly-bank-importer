"""Characterisation tests for easy coverage wins (TASK-009).

Covers: save_account_cache, create_import_folders, auto_split_folder,
split_file_in_place (empty-row branch), create_transaction (BLOCK guard,
result rendering).
"""

import csv
import json
import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import (
    Account,
    auto_split_folder,
    create_import_folders,
    create_transaction,
    save_account_cache,
    split_file_in_place,
)

ACCOUNT_ID = 7


@pytest.fixture()
def cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "accounts_cache.json"
    monkeypatch.setattr(module, "ACCOUNT_CACHE_FILE", path)
    return path


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    return client


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    headers = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# save_account_cache
# ---------------------------------------------------------------------------


class TestSaveAccountCache:
    def test_writes_accounts_to_file(self, cache_path: Path) -> None:
        accounts: list[Account] = [{"id": 1, "name": "Lönekonto", "type": "asset"}]
        save_account_cache(accounts)
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert data["accounts"] == accounts

    def test_includes_fetched_at_key(self, cache_path: Path) -> None:
        accounts: list[Account] = [{"id": 1, "name": "X", "type": "asset"}]
        save_account_cache(accounts)
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert "fetched_at" in data

    def test_multiple_accounts_all_written(self, cache_path: Path) -> None:
        accounts: list[Account] = [
            {"id": 1, "name": "A", "type": "asset"},
            {"id": 2, "name": "B", "type": "asset"},
        ]
        save_account_cache(accounts)
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert len(data["accounts"]) == 2

    def test_file_is_valid_utf8_json(self, cache_path: Path) -> None:
        accounts: list[Account] = [{"id": 1, "name": "Räkningskonto", "type": "asset"}]
        save_account_cache(accounts)
        text = cache_path.read_text(encoding="utf-8")
        parsed = json.loads(text)
        assert parsed["accounts"][0]["name"] == "Räkningskonto"


# ---------------------------------------------------------------------------
# create_import_folders
# ---------------------------------------------------------------------------


class TestCreateImportFolders:
    def test_creates_one_folder_per_account(self, tmp_path: Path) -> None:
        accounts: list[Account] = [
            {"id": 1, "name": "Lönekonto", "type": "asset"},
            {"id": 2, "name": "Sparkonto", "type": "asset"},
        ]
        create_import_folders(tmp_path, accounts)
        assert (tmp_path / "kontoutdrag_Lonekonto").is_dir()
        assert (tmp_path / "kontoutdrag_Sparkonto").is_dir()

    def test_existing_folder_not_recreated(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        accounts: list[Account] = [{"id": 1, "name": "Lönekonto", "type": "asset"}]
        (tmp_path / "kontoutdrag_Lonekonto").mkdir()
        with caplog.at_level(logging.INFO):
            create_import_folders(tmp_path, accounts)
        assert any("Inga nya" in r.message for r in caplog.records)

    def test_logs_created_count(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        accounts: list[Account] = [
            {"id": 1, "name": "A", "type": "asset"},
            {"id": 2, "name": "B", "type": "asset"},
        ]
        with caplog.at_level(logging.INFO):
            create_import_folders(tmp_path, accounts)
        assert any("2" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# auto_split_folder
# ---------------------------------------------------------------------------


class TestAutoSplitFolder:
    def test_non_monthly_file_is_split(self, tmp_path: Path) -> None:
        src = tmp_path / "kontoutdrag_export.csv"
        write_seb_csv(src, [["2025-01-10", "2025-01-10", "V1", "Shop", "-100,00", "900,00"]])
        auto_split_folder(tmp_path)
        assert not src.exists()
        assert (tmp_path / "2025-01.csv").exists()

    def test_monthly_file_is_left_untouched(self, tmp_path: Path) -> None:
        monthly = tmp_path / "2025-01.csv"
        write_seb_csv(monthly, [["2025-01-10", "2025-01-10", "V1", "Shop", "-100,00", "900,00"]])
        auto_split_folder(tmp_path)
        assert monthly.exists()

    def test_empty_folder_does_not_crash(self, tmp_path: Path) -> None:
        auto_split_folder(tmp_path)  # no exception


# ---------------------------------------------------------------------------
# split_file_in_place — header-only (empty-row) branch
# ---------------------------------------------------------------------------


class TestSplitFileInPlaceEmptyRows:
    def test_header_only_file_not_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_seb_csv(src, [])  # header but no data rows
        split_file_in_place(src)
        assert src.exists()

    def test_header_only_no_output_files(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_seb_csv(src, [])
        split_file_in_place(src)
        assert list(tmp_path.glob("????-??.csv")) == []


# ---------------------------------------------------------------------------
# create_transaction — BLOCK_TRANSACTION_POSTS guard and log=True branch
# ---------------------------------------------------------------------------


class TestCreateTransactionBlock:
    def test_returns_error_result_when_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TASK-067: the BLOCK_TRANSACTION_POSTS guard no longer raises;
        create_transaction is a pure function (FR-71) that returns a
        structured ERROR TransactionResult instead, so the CLI can render
        it and the run can continue."""
        from firefly_bank_importer.service import TransactionStatus

        monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
        client = make_client()
        result = create_transaction(client, "2025-01-10", "Test", "-50,00", ACCOUNT_ID)
        assert result.status == TransactionStatus.ERROR
        assert result.error_message is not None and "blockerad" in result.error_message
        client.create_transaction.assert_not_called()


class TestCreateTransactionResult:
    def test_returns_transaction_result_on_success(self) -> None:
        from firefly_bank_importer.service import TransactionStatus

        client = make_client()
        result = create_transaction(client, "2025-01-10", "Kaffebar", "-35,00", ACCOUNT_ID)
        assert result.status == TransactionStatus.OK
        assert result.amount == pytest.approx(-35.0)

    def test_render_transaction_result_logs_ok_line(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = create_transaction(client, "2025-01-10", "Kaffebar", "-35,00", ACCOUNT_ID)
        with caplog.at_level(logging.INFO):
            module._render_transaction_result(result, dry_run=False)
        assert any("[OK]" in r.message for r in caplog.records)

    def test_client_create_transaction_called(self) -> None:
        client = make_client()
        create_transaction(client, "2025-01-10", "X", "-10,00", ACCOUNT_ID)
        client.create_transaction.assert_called_once()
