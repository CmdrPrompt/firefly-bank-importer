"""Characterisation tests for account-name transaction logging (UC-34, FR-69).

Covers _render_transaction_result, create_transaction, and _post_transfer
(with _render_transfer_result) using the Firefly account name instead of the
numeric account ID, with a fallback to the numeric ID when the name cannot be
resolved. TASK-067 moved the actual `logging` calls for these outcomes out
of `create_transaction`/`_post_transfer` (now pure, event-returning
functions per FR-71) and into the CLI adapter's `_render_transaction_result`
/`_render_transfer_result` helpers.
"""

import csv
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import (
    _render_transaction_result,
    _render_transfer_result,
    _resolve_account_name,
    create_transaction,
    main,
    post_transfer,
)


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": "100.00", "date": None}
    return client


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


class TestResolveAccountName:
    def test_resolves_known_account_id(self) -> None:
        account_map = {"SEB Lönekonto Thomas": 42}
        assert _resolve_account_name(42, account_map) == "SEB Lönekonto Thomas"

    def test_falls_back_to_numeric_id_when_unknown(self) -> None:
        account_map = {"SEB Lönekonto Thomas": 42}
        assert _resolve_account_name(99, account_map) == "99"


class TestRenderTransactionResultAccountName:
    def test_logs_account_name_line(self, caplog: pytest.LogCaptureFixture) -> None:
        from firefly_bank_importer.service import TransactionResult, TransactionStatus

        result = TransactionResult(
            date="2025-06-25",
            amount=-69.0,
            account_id=1,
            status=TransactionStatus.OK,
            description="MCDJARFALLAS/25-06-24",
            account_name="SEB Lönekonto Thomas",
        )
        with caplog.at_level(logging.INFO):
            _render_transaction_result(result, dry_run=False)
        assert any(
            r.message == "  [OK] [SEB Lönekonto Thomas] [withdrawal] 69.00 SEK | 2025-06-25 | MCDJARFALLAS/25-06-24"
            for r in caplog.records
        )


class TestCreateTransactionAccountName:
    def test_live_log_includes_account_name(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = create_transaction(
            client,
            "2025-06-25",
            "MCDJARFALLAS/25-06-24",
            "-69.00",
            42,
            account_name="SEB Lönekonto Thomas",
        )
        with caplog.at_level(logging.INFO):
            _render_transaction_result(result, dry_run=False)
        assert any(
            r.message == "  [OK] [SEB Lönekonto Thomas] [withdrawal] 69.00 SEK | 2025-06-25 | MCDJARFALLAS/25-06-24"
            for r in caplog.records
        )

    def test_dry_run_log_includes_account_name(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = create_transaction(
            client,
            "2025-06-25",
            "MCDJARFALLAS/25-06-24",
            "-69.00",
            42,
            dry_run=True,
            account_name="SEB Lönekonto Thomas",
        )
        with caplog.at_level(logging.INFO):
            _render_transaction_result(result, dry_run=True)
        assert any(
            "[DRY RUN] [SEB Lönekonto Thomas] [withdrawal] 69.00 SEK | 2025-06-25 | MCDJARFALLAS/25-06-24" in r.message
            for r in caplog.records
        )

    def test_falls_back_to_numeric_id_when_name_omitted(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = create_transaction(client, "2025-06-25", "X", "-10.00", 99)
        with caplog.at_level(logging.INFO):
            _render_transaction_result(result, dry_run=False)
        assert any("[OK] [99] [withdrawal]" in r.message for r in caplog.records)


class TestPostTransferAccountNames:
    def _payload(self) -> dict[str, str]:
        return {
            "type": "transfer",
            "date": "2025-06-23",
            "amount": "500.00",
            "description": "UTLÄGG MAT",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }

    def test_live_log_uses_account_names(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = post_transfer(
            client,
            self._payload(),
            dry_run=False,
            source_name="Planbok",
            destination_name="SEB Räkningskonto",
        )
        with caplog.at_level(logging.INFO):
            _render_transfer_result(result, dry_run=False)
        assert any(
            r.message == "  [OK] [transfer] 500.00 SEK | 2025-06-23 | Planbok -> SEB Räkningskonto | UTLÄGG MAT"
            for r in caplog.records
        )

    def test_dry_run_log_uses_account_names(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = post_transfer(
            client,
            self._payload(),
            dry_run=True,
            source_name="Planbok",
            destination_name="SEB Räkningskonto",
        )
        with caplog.at_level(logging.INFO):
            _render_transfer_result(result, dry_run=True)
        assert any(
            r.message == "  [DRY RUN] [transfer] 500.00 SEK | 2025-06-23 | Planbok -> SEB Räkningskonto | UTLÄGG MAT"
            for r in caplog.records
        )

    def test_falls_back_to_numeric_ids_when_names_omitted(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        result = post_transfer(client, self._payload(), dry_run=False)
        with caplog.at_level(logging.INFO):
            _render_transfer_result(result, dry_run=False)
        assert any("1 -> 2" in r.message for r in caplog.records)


class TestMainEndToEndAccountNames:
    def test_multi_folder_transfer_logs_account_names(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder_a = tmp_path / "kontoutdrag_Planbok"
        folder_b = tmp_path / "kontoutdrag_SEB_Rakningskonto"
        folder_a.mkdir()
        folder_b.mkdir()

        def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
            headers = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f, delimiter=";")
                writer.writerow(headers)
                writer.writerows(rows)

        write_seb_csv(
            folder_a / "2025-06.csv",
            [["2025-06-23", "2025-06-23", "V1", "UTLAGG MAT", "-500,00", "900,00"]],
        )
        write_seb_csv(
            folder_b / "2025-06.csv",
            [["2025-06-23", "2025-06-23", "V1", "UTLAGG MAT", "500,00", "1100,00"]],
        )

        client = make_client()
        account_map = {"Planbok": 1, "SEB Räkningskonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            caplog.at_level(logging.INFO),
        ):
            main(base_folder=str(tmp_path))

        assert any("Planbok -> SEB Räkningskonto" in r.message for r in caplog.records)
