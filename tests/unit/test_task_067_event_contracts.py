"""RED-phase contract tests for TASK-067 (FR-71/72/73, UC-30/31/33/34).

Specifies the *new* event-based contract for posting and orchestration
functions: they must return/yield structured result objects (from the
service layer) instead of calling `logging.info`/`logging.error`, and they
must no longer accept `pbar: tqdm | None` as a parameter.

These tests intentionally fail against the current (pre-TASK-067) code,
because:
- `firefly_bank_importer.service` does not yet define `TransferResult` or
  `OpeningBalanceResult`, and `TransactionResult` does not yet carry
  `description`/`account_name` fields (all expected per this contract).
- `create_transaction`, `_run_threaded_import`, `_post_transfer`,
  `_post_unmatched_rows`, and `_run_multi_folder_import` in
  `import_firefly.py` still call `logging.info`/`logging.error` directly,
  still accept a `pbar` parameter, and do not return/yield the structured
  result objects below.

Expected contract for the Implementation Worker (green phase):

- `firefly_bank_importer.service.TransactionResult` gains `description: str`
  and `account_name: str` fields alongside the existing `date`, `amount`,
  `account_id`, `status`, `error_message`.
- `firefly_bank_importer.service.TransferResult` (new, frozen dataclass):
  `date`, `amount`, `description`, `source_account_id`,
  `source_account_name`, `destination_account_id`,
  `destination_account_name`, `status`, `error_message`.
- `firefly_bank_importer.service.OpeningBalanceResult` (new, frozen
  dataclass): `account_id`, `balance`, `date`, `excluded_row_date`,
  `dry_run`.
- `import_firefly.create_transaction(...)` returns a `TransactionResult`
  (OK or ERROR) instead of `tuple[str, float] | None`, and no longer emits
  any `logging` calls itself (rendering is the CLI's job).
- `import_firefly._run_threaded_import(...)`, `_post_unmatched_rows(...)`
  become generators yielding `TransactionResult` objects; neither accepts
  `pbar` anymore.
- `import_firefly._post_transfer(...)` returns a `TransferResult` instead of
  `None`, no longer accepts `pbar`, and — closing the pre-existing
  BLOCK_TRANSACTION_POSTS asymmetry documented in
  `test_task_067_golden_master.py` — returns a structured ERROR result
  instead of letting the guard's `RuntimeError` propagate.
- `import_firefly._run_multi_folder_import(...)` becomes a generator that
  yields a mix of `TransactionResult`/`TransferResult`/`ProgressEvent`
  objects instead of instantiating a `tqdm` progress bar itself.

Where the exact shape is a genuine design choice left open by the task
(e.g. whether orchestration functions are generators vs. return lists), this
file states the chosen contract explicitly in each test's docstring so
Implementation Worker can implement to it, or renegotiate it consciously
rather than by accident.

All tests run against a mocked FireflyClient (MagicMock), per the existing
test suite's pattern. No real HTTP calls are made.
"""

import csv
import inspect
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient
from hypothesis import given
from hypothesis import strategies as st

import firefly_bank_importer.import_firefly as module

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
# Scenario: Transaction posting emits structured results, not logging
# ---------------------------------------------------------------------------


class TestTransactionResultContract:
    def test_transaction_result_type_carries_description_and_account_name(self) -> None:
        """TransactionResult must be constructible with `description` and
        `account_name`, extending the fields already defined in TASK-066.
        """
        from firefly_bank_importer.service import TransactionResult, TransactionStatus

        result = TransactionResult(
            date="2025-01-05",
            amount=10.0,
            description="Shop",
            account_id=42,
            account_name="SEB Lonekonto",
            status=TransactionStatus.OK,
        )
        assert result.description == "Shop"
        assert result.account_name == "SEB Lonekonto"

    def test_create_transaction_returns_transaction_result_on_success(self) -> None:
        from firefly_bank_importer.service import TransactionResult, TransactionStatus

        client = make_client()
        result = module.create_transaction(client, "2025-01-05", "Shop", "-10,00", 42, account_name="SEB Lonekonto")
        assert isinstance(result, TransactionResult)
        assert result.status == TransactionStatus.OK
        assert result.date == "2025-01-05"
        assert result.description == "Shop"
        assert result.account_id == 42
        assert result.account_name == "SEB Lonekonto"
        assert result.amount == pytest.approx(10.0)
        assert result.error_message is None

    def test_create_transaction_emits_no_logging_calls(self, caplog: pytest.LogCaptureFixture) -> None:
        """Posting functions must not call logging.info/error themselves;
        rendering those results is the CLI's job (FR-71/FR-72).
        """
        client = make_client()
        with caplog.at_level(logging.INFO):
            module.create_transaction(client, "2025-01-05", "Shop", "-10,00", 42, account_name="SEB")
        assert caplog.records == []

    def test_create_transaction_dry_run_returns_ok_result_without_posting_or_logging(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        from firefly_bank_importer.service import TransactionStatus

        client = make_client()
        with caplog.at_level(logging.INFO):
            result = module.create_transaction(
                client, "2025-01-05", "Shop", "-10,00", 42, account_name="SEB", dry_run=True
            )
        assert result.status == TransactionStatus.OK
        assert caplog.records == []
        client.create_transaction.assert_not_called()

    @given(raw_amount=st.decimals(min_value=-100000, max_value=100000, places=2).map(str))
    def test_create_transaction_result_amount_matches_parsed_amount(self, raw_amount: str) -> None:
        """Data-transformation property: the amount reported on the result
        must equal parse_amount() applied to the raw CSV amount string,
        regardless of sign or magnitude.
        """
        from firefly_bank_importer.service import parse_amount

        client = make_client()
        formatted = raw_amount.replace(".", ",")
        result = module.create_transaction(client, "2025-01-05", "Row", formatted, 42, dry_run=True)
        assert result.amount == pytest.approx(parse_amount(formatted))


# ---------------------------------------------------------------------------
# Scenario: Progress tracking uses events, not tqdm parameters
# ---------------------------------------------------------------------------


class TestNoPbarParameter:
    @pytest.mark.parametrize(
        "func_name",
        ["_run_threaded_import", "_post_transfer", "_post_unmatched_rows"],
    )
    def test_function_no_longer_accepts_pbar(self, func_name: str) -> None:
        func = getattr(module, func_name)
        sig = inspect.signature(func)
        assert "pbar" not in sig.parameters, f"{func_name} must not accept pbar anymore (FR-71)"

    def test_run_threaded_import_yields_transaction_results_instead_of_updating_pbar(self) -> None:
        """`_run_threaded_import` becomes a generator of TransactionResult
        events; the CLI is responsible for advancing its own tqdm bar per
        yielded event.
        """
        from firefly_bank_importer.service import TransactionResult, TransactionStatus

        client = make_client()
        pending = [("2025-01-05", "Shop", "-10,00"), ("2025-01-06", "Cafe", "-20,00")]
        results = list(module._run_threaded_import(client, pending, 42, account_name="SEB"))
        assert len(results) == 2
        assert all(isinstance(r, TransactionResult) for r in results)
        assert {r.status for r in results} == {TransactionStatus.OK}
        assert {r.description for r in results} == {"Shop", "Cafe"}

    def test_run_multi_folder_import_does_not_instantiate_tqdm_directly(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_run_multi_folder_import` must emit ProgressEvent objects
        instead of owning a tqdm progress bar itself; only the CLI adapter
        may construct a tqdm bar.
        """

        def boom(*_args: object, **_kwargs: object) -> None:
            raise AssertionError("_run_multi_folder_import must not instantiate tqdm directly")

        monkeypatch.setattr(module, "tqdm", boom)

        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"]])
        write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "100,00", "1100,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}

        with patch.object(module, "get_latest_transaction_date", return_value=None):
            results = list(
                module._run_multi_folder_import(
                    client, [folder_a, folder_b], account_map, dry_run=True, ignore_latest_date_check=False
                )
            )
        assert len(results) > 0


# ---------------------------------------------------------------------------
# Scenario: Opening-balance detection result is communicated via events (UC-30)
# ---------------------------------------------------------------------------


class TestOpeningBalanceEventContract:
    def test_apply_auto_opening_balance_returns_structured_result(self, tmp_path: Path) -> None:
        from firefly_bank_importer.service import OpeningBalanceResult

        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="0.00")

        result = module._apply_auto_opening_balance(client, 42, [csv_path], dry_run=False)

        assert isinstance(result, OpeningBalanceResult)
        assert result.account_id == 42
        assert result.balance == pytest.approx(990.00)
        assert result.date == "2025-01-05"
        assert result.excluded_row_date == "2025-01-05"
        assert result.dry_run is False

    def test_apply_auto_opening_balance_emits_no_logging_calls(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        csv_path = tmp_path / "2025-01.csv"
        write_seb_csv(csv_path, [["2025-01-05", "2025-01-05", "V1", "Old", "-10,00", "990,00"]])
        client = make_client(balance="0.00")

        with caplog.at_level(logging.INFO):
            module._apply_auto_opening_balance(client, 42, [csv_path], dry_run=True)
        assert caplog.records == []


# ---------------------------------------------------------------------------
# Scenario: Transfer detection result includes source and destination account
# names (UC-31/FR-66)
# ---------------------------------------------------------------------------


class TestTransferResultContract:
    def _payload(self) -> dict[str, str]:
        return {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "Overforing",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }

    def test_post_transfer_returns_structured_result_with_account_names(self) -> None:
        from firefly_bank_importer.service import TransactionStatus, TransferResult

        client = make_client()
        result = module._post_transfer(
            client, self._payload(), dry_run=False, source_name="Lonekonto", destination_name="Sparkonto"
        )
        assert isinstance(result, TransferResult)
        assert result.status == TransactionStatus.OK
        assert result.source_account_id == 1
        assert result.source_account_name == "Lonekonto"
        assert result.destination_account_id == 2
        assert result.destination_account_name == "Sparkonto"
        assert result.amount == pytest.approx(100.00)
        assert result.date == "2025-01-05"

    def test_post_transfer_emits_no_logging_calls(self, caplog: pytest.LogCaptureFixture) -> None:
        client = make_client()
        with caplog.at_level(logging.INFO):
            module._post_transfer(
                client, self._payload(), dry_run=False, source_name="Lonekonto", destination_name="Sparkonto"
            )
        assert caplog.records == []


# ---------------------------------------------------------------------------
# Scenario: BLOCK_TRANSACTION_POSTS guard is handled consistently for
# postings and transfers
# ---------------------------------------------------------------------------


class TestBlockGuardEmitsStructuredErrorConsistently:
    def test_create_transaction_block_guard_returns_error_result(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from firefly_bank_importer.service import TransactionStatus

        monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
        client = make_client()
        result = module.create_transaction(client, "2025-01-05", "Shop", "-10,00", 42, account_name="SEB")
        assert result.status == TransactionStatus.ERROR
        assert result.error_message is not None and "blockerad" in result.error_message
        client.create_transaction.assert_not_called()

    def test_post_transfer_block_guard_returns_error_result_instead_of_raising(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """This is the consequence fix named in TASK-067: pre-refactor,
        `_post_transfer` let the guard's RuntimeError propagate uncaught
        (see test_task_067_golden_master.py::TestBlockTransactionPostsGuardAsymmetry).
        Post-refactor, it must emit a structured ERROR result like
        create_transaction does, and the caller must be able to continue
        the run.
        """
        from firefly_bank_importer.service import TransactionStatus, TransferResult

        monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
        client = make_client()
        payload = {
            "type": "transfer",
            "date": "2025-01-05",
            "amount": "100.00",
            "description": "Overforing",
            "source_id": "1",
            "destination_id": "2",
            "currency_code": "SEK",
        }

        result = module._post_transfer(client, payload, dry_run=False, source_name="A", destination_name="B")

        assert isinstance(result, TransferResult)
        assert result.status == TransactionStatus.ERROR
        assert result.error_message is not None and "blockerad" in result.error_message
        client.create_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario: Account-name transaction logging works via events (UC-34)
# ---------------------------------------------------------------------------


class TestAccountNameInEvents:
    def test_post_unmatched_rows_yields_results_carrying_account_name(self) -> None:
        from firefly_bank_importer.service import PendingRow, TransactionResult

        client = make_client()
        rows = [
            PendingRow(
                account_id=42,
                account_name="SEB Lonekonto",
                iso_date="2025-01-05",
                description="Shop",
                amount="-10,00",
                bank_format="seb",
                row_date=date(2025, 1, 5),
            )
        ]
        results = list(module._post_unmatched_rows(client, rows, dry_run=True))
        assert len(results) == 1
        assert isinstance(results[0], TransactionResult)
        assert results[0].account_name == "SEB Lonekonto"
        assert results[0].account_id == 42
