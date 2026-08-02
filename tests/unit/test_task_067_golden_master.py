"""Golden-master characterization tests for TASK-067.

Captures the CLI's exact, ordered log output for representative single-folder
and multi-folder scenarios *before* refactoring logging/tqdm into structured
events (FR-71, FR-72, FR-73). These tests exist to prove, line-for-line, that
the post-refactor CLI renders identical output to what is captured here.

Also documents an asymmetry in how the BLOCK_TRANSACTION_POSTS guard (test
safety mechanism, see TASK-067 acceptance criteria "Test Safety Constraint")
is handled by the two posting call sites:

- `_run_threaded_import` / `_handle_batch_result` catches the guard's
  RuntimeError and logs a `[FEL]` (ERROR) line per transaction, continuing.
- `_post_transfer` does NOT catch the guard's RuntimeError; it propagates
  out of `_post_transfer` (after pbar.update via `finally`), which would
  currently crash `_run_multi_folder_import` if BLOCK_TRANSACTION_POSTS is
  enabled while a transfer is pending. This is flagged as a discrepancy
  between the task's "Test Safety Constraint" wording (which implies
  BLOCK_TRANSACTION_POSTS can safely be enabled for a non-dry-run,
  transfer-detecting scenario and still observe "per-transaction OK/ERROR
  status") and current code behavior -- see characterization test docstrings
  below for the exact observed behavior.

All tests run against a mocked FireflyClient (MagicMock/monkeypatch), per the
existing test suite's pattern (see test_process_folder.py). No real HTTP
calls are made.
"""

import csv
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import _post_transfer, _run_threaded_import, main

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


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


# ---------------------------------------------------------------------------
# Scenario: single-folder dry-run
# ---------------------------------------------------------------------------


class TestGoldenMasterSingleFolderDryRun:
    """Full ordered log-message sequence for a single-folder dry-run import.

    2 rows in one CSV, no prior Firefly transactions, non-zero opening
    balance (so UC-30 auto-detection does not trigger).
    """

    def test_exact_log_sequence(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
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
            patch.object(module.time, "monotonic", side_effect=[0.0, 5.0]),
            caplog.at_level(logging.INFO),
        ):
            result = main(base_folder=str(tmp_path), dry_run=True)

        assert result == 0
        messages = [r.message for r in caplog.records]
        assert messages == [
            "=== DRY RUN -- inga transaktioner skapas ===",
            "Hittade 1 kontomapp(ar).",
            messages[2],  # "Loggar till: <timestamped log filename>"
            "Konto ID 1: " + tmp_path.name,
            "  Ingen tidigare transaktion hittades i Firefly.",
            "Bearbetar: 2025-01.csv",
            "  Format: SEB",
            "  [DRY RUN] [Lonekonto] [withdrawal] 10.00 SEK | 2025-01-05 | Shop",
            "  [DRY RUN] [Lonekonto] [withdrawal] 20.00 SEK | 2025-01-06 | Cafe",
            "  Summa: 2 transaktioner",
            "Klar!",
            "Total tid: 0:00:05",
            "2.50s/transaktion",
        ]
        assert messages[2].startswith("Loggar till: import_")


# ---------------------------------------------------------------------------
# Scenario: multi-folder non-dry-run with transfer detection (UC-31/FR-66)
# ---------------------------------------------------------------------------


class TestGoldenMasterMultiFolderNonDryRun:
    """Full ordered log-message sequence for a multi-folder, non-dry-run
    import with one matched transfer and one unmatched withdrawal.

    BLOCK_TRANSACTION_POSTS is left at its natural value for this scenario:
    main() sets it to `dry_run`, i.e. False here, matching the existing test
    suite's established convention (test_transfer_detection.py,
    test_process_folder.py, etc. all explicitly set it to False for
    non-dry-run scenarios against a mocked client).
    """

    def test_exact_log_sequence(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(
            folder_a / "2025-01.csv",
            [
                ["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"],
                ["2025-01-06", "2025-01-06", "V2", "Shop", "-50,00", "850,00"],
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
            patch.object(module.time, "monotonic", side_effect=[0.0, 3.0]),
            caplog.at_level(logging.INFO),
        ):
            result = main(base_folder=str(tmp_path))

        assert result == 0
        messages = [r.message for r in caplog.records]
        assert messages == [
            "Säkerställer importmappar för alla konton...",
            "  Inga nya importmappar behövde skapas.",
            "Hittade 2 kontomapp(ar).",
            messages[3],  # "Loggar till: <timestamped log filename>"
            "Konto ID 1: kontoutdrag_Lonekonto",
            "  Ingen tidigare transaktion hittades i Firefly.",
            "Bearbetar: 2025-01.csv",
            "  Format: SEB",
            "Konto ID 2: kontoutdrag_Sparkonto",
            "  Ingen tidigare transaktion hittades i Firefly.",
            "Bearbetar: 2025-01.csv",
            "  Format: SEB",
            "Detekterade 1 overforing(ar) mellan konton.",
            "  [OK] [transfer] 100.00 SEK | 2025-01-05 | Lonekonto -> Sparkonto | Overforing",
            "  [OK] [Lonekonto] [withdrawal] 50.00 SEK | 2025-01-06 | Shop",
            "  Summa: 1 ok, 0 fel",
            "Klar!",
            "Total tid: 0:00:03",
            "1.50s/transaktion",
        ]
        assert messages[3].startswith("Loggar till: import_")
        client.create_transaction.assert_called()  # mocked -- no real HTTP


# ---------------------------------------------------------------------------
# Scenario: opening-balance detection (UC-30) with balance == 0, integrated
# into a full single-folder non-dry-run run
# ---------------------------------------------------------------------------


class TestGoldenMasterOpeningBalanceZero:
    """Full ordered log-message sequence when the account's opening balance
    is 0.00 and gets auto-set from the earliest CSV row (UC-30/FR-65); that
    row is then excluded from import.
    """

    def test_exact_log_sequence(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        write_seb_csv(
            tmp_path / "2025-01.csv",
            [
                ["2025-01-05", "2025-01-05", "V1", "Opening", "-10,00", "990,00"],
                ["2025-01-20", "2025-01-20", "V2", "Later", "-20,00", "970,00"],
            ],
        )
        client = make_client(balance="0.00")
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
        assert messages == [
            "Hittade 1 kontomapp(ar).",
            messages[1],
            "  Satte opening balance: 990.00 SEK per 2025-01-05 (rad exkluderad fran import).",
            "Konto ID 1: " + tmp_path.name,
            "Bearbetar: 2025-01.csv",
            "  Format: SEB",
            "  Senaste i Firefly: 2025-01-05 (hoppar over <= detta datum)",
            "  [OK] [Lonekonto] [withdrawal] 20.00 SEK | 2025-01-20 | Later",
            "  Summa: 1 ok, 0 fel",
            "  Hoppade over: 1 rader",
            "Klar!",
            "Total tid: 0:00:01",
            "1.00s/transaktion",
        ]
        assert messages[1].startswith("Loggar till: import_")
        client.set_opening_balance.assert_called_once_with("1", "990.00", "2025-01-05")


# ---------------------------------------------------------------------------
# BLOCK_TRANSACTION_POSTS guard: asymmetric handling between call sites
# ---------------------------------------------------------------------------


class TestBlockTransactionPostsGuardAsymmetry:
    """TASK-067 update: this class originally documented an *inconsistency*
    in how the BLOCK_TRANSACTION_POSTS test-safety guard was handled --
    `create_transaction`'s RuntimeError was caught and turned into a `[FEL]`
    log line, while `_post_transfer`'s identical RuntimeError propagated
    uncaught (see the pre-refactor git history for the original assertions).

    TASK-067's own acceptance criteria ("BLOCK_TRANSACTION_POSTS guard is
    handled consistently for postings and transfers") explicitly closes
    this inconsistency: both `create_transaction` and `_post_transfer` now
    return a structured ERROR result instead of raising, and neither
    accepts a `pbar` parameter anymore (posting/orchestration functions are
    pure per FR-71). The three tests that asserted the old raising/pbar
    behavior are superseded by
    `test_task_067_event_contracts.py::TestBlockGuardEmitsStructuredErrorConsistently`,
    which asserts the new, consistent, non-raising contract for both call
    sites.
    """

    def test_run_threaded_import_yields_error_result_on_block_guard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from firefly_bank_importer.service import TransactionStatus

        monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
        client = make_client()
        pending = [("2025-01-05", "Shop", "-50.00")]

        results = list(_run_threaded_import(client, pending, account_id=1, account_name="Lonekonto"))

        assert len(results) == 1
        assert results[0].status == TransactionStatus.ERROR
        assert results[0].error_message is not None and "blockerad" in results[0].error_message
        client.create_transaction.assert_not_called()

    def test_post_transfer_returns_error_result_on_block_guard_instead_of_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from firefly_bank_importer.service import TransactionStatus

        monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
        client = make_client()
        payload = {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "X",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }

        result = _post_transfer(client, payload, dry_run=False)

        assert result.status == TransactionStatus.ERROR
        assert result.error_message is not None and "blockerad" in result.error_message
        client.create_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# Transfer log-line format (FR-69)
# ---------------------------------------------------------------------------


class TestTransferLogLineFormat:
    """TASK-067 update: `_post_transfer` itself no longer logs (FR-71); the
    exact `[OK] [transfer] ...` line format is now rendered by the CLI
    adapter's `_render_transfer_result` helper, exercised here directly (and
    already covered end-to-end via `main()` in
    `TestGoldenMasterMultiFolderNonDryRun` above).
    """

    def test_ok_transfer_format(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        payload = {
            "type": "transfer",
            "date": "2025-06-23",
            "amount": "500.00",
            "description": "UTLAGG MAT",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }
        result = _post_transfer(client, payload, dry_run=False, source_name="Planbok", destination_name="Sparkonto")
        with caplog.at_level(logging.INFO):
            module._render_transfer_result(result, dry_run=False)

        assert any(
            r.message == "  [OK] [transfer] 500.00 SEK | 2025-06-23 | Planbok -> Sparkonto | UTLAGG MAT"
            for r in caplog.records
        )


# ---------------------------------------------------------------------------
# Period-scoped import (UC-33) transaction count
# ---------------------------------------------------------------------------


class TestPeriodScopingTransactionCount:
    def test_only_period_rows_counted(self, tmp_path: Path) -> None:
        write_seb_csv(tmp_path / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
        write_seb_csv(
            tmp_path / "2025-02.csv",
            [
                ["2025-02-10", "2025-02-10", "V1", "X", "-10,00", "990,00"],
                ["2025-02-11", "2025-02-11", "V2", "Y", "-20,00", "970,00"],
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
        ):
            main(base_folder=str(tmp_path), period="2025-02")

        assert client.create_transaction.call_count == 2
