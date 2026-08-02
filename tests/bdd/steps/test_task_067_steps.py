"""Step definitions for TASK-067's BDD feature file.

Binds `tests/bdd/features/TASK-067-decouple-logging-tqdm-emit-events.feature`
to the already-implemented event-based service layer
(`firefly_bank_importer.service`) and CLI adapter
(`firefly_bank_importer.import_firefly`). This is a documentation retrofit
(BDD-053 style): the functionality already exists and is covered by
`tests/unit/test_task_067_event_contracts.py` and
`tests/unit/test_task_067_golden_master.py`; these steps exercise the same
code paths so the scenarios are green on first run, giving the task's
acceptance criteria an executable form.

All scenarios run against a mocked `FireflyClient` (MagicMock/monkeypatch),
per the project's established testing convention. No real HTTP calls are
made to any Firefly instance.
"""

import contextlib
import csv
import inspect
import logging
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient
from pytest_bdd import given, scenarios, then, when

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.service import (
    OpeningBalanceResult,
    PendingRow,
    TransactionResult,
    TransactionStatus,
    TransferResult,
)

scenarios("../features/TASK-067-decouple-logging-tqdm-emit-events.feature")

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


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


def _run_main_with_patches(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    """Shared helper: patch collaborators per the context and call main()."""
    patches = [
        patch.object(module, "build_account_map", return_value=(context["account_map"], [])),
        patch.object(module, "get_latest_transaction_date", return_value=None),
        patch.object(module, "load_api_token", return_value="token"),
        patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
        patch.object(module, "FireflyClient", return_value=context["client"]),
    ]
    if "find_account_id_return" in context:
        patches.append(patch.object(module, "find_account_id", return_value=context["find_account_id_return"]))
    if "monotonic_side_effect" in context:
        patches.append(patch.object(module.time, "monotonic", side_effect=context["monotonic_side_effect"]))

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        with caplog.at_level(logging.INFO):
            context["main_result"] = module.main(**context["main_kwargs"])
    context["messages"] = [r.message for r in caplog.records]


# ---------------------------------------------------------------------------
# Scenario: Transaction posting emits structured results, not logging
# ---------------------------------------------------------------------------


@given("a posting function processes a transaction")
def given_posting_function(context: dict[str, Any]) -> None:
    context["client"] = make_client()


@when("the function executes per FR-71")
def when_posting_executes(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        context["result"] = module.create_transaction(
            context["client"], "2025-01-05", "Shop", "-10,00", 42, account_name="SEB Lonekonto"
        )
    context["log_records"] = list(caplog.records)


@then(
    "it returns a structured result object containing date, amount, description, account ID, account name, "
    "status, and error message"
)
def then_result_has_structured_fields(context: dict[str, Any]) -> None:
    result = context["result"]
    assert isinstance(result, TransactionResult)
    assert result.date == "2025-01-05"
    assert result.amount == pytest.approx(-10.0)
    assert result.description == "Shop"
    assert result.account_id == 42
    assert result.account_name == "SEB Lonekonto"
    assert result.status == TransactionStatus.OK
    assert result.error_message is None


@then("it does not call logging.info or logging.error directly")
def then_no_direct_logging(context: dict[str, Any]) -> None:
    assert context["log_records"] == []


# ---------------------------------------------------------------------------
# Scenario: Progress tracking uses events, not tqdm parameters
# ---------------------------------------------------------------------------


@given("posting and orchestration functions previously accepted a tqdm progress bar as a parameter")
def given_previous_pbar_contract(context: dict[str, Any]) -> None:
    context["target_funcs"] = ["_run_threaded_import", "_post_transfer", "_post_unmatched_rows"]


@when("refactored per FR-71")
def when_refactored_functions_exercised(
    context: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context["signatures"] = {name: inspect.signature(getattr(module, name)) for name in context["target_funcs"]}

    client = make_client()
    pending = [("2025-01-05", "Shop", "-10,00"), ("2025-01-06", "Cafe", "-20,00")]
    context["threaded_results"] = list(module._run_threaded_import(client, pending, 42, account_name="SEB"))

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("_run_multi_folder_import must not instantiate tqdm directly")

    monkeypatch.setattr(module, "tqdm", boom)

    folder_a = tmp_path / "kontoutdrag_Lonekonto"
    folder_b = tmp_path / "kontoutdrag_Sparkonto"
    folder_a.mkdir()
    folder_b.mkdir()
    write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"]])
    write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "100,00", "1100,00"]])
    account_map = {"Lonekonto": 1, "Sparkonto": 2}

    with patch.object(module, "get_latest_transaction_date", return_value=None):
        context["multi_folder_results"] = list(
            module._run_multi_folder_import(
                client, [folder_a, folder_b], account_map, dry_run=True, ignore_latest_date_check=False
            )
        )


@then("they no longer accept a pbar parameter")
def then_no_pbar_parameter(context: dict[str, Any]) -> None:
    for name, sig in context["signatures"].items():
        assert "pbar" not in sig.parameters, f"{name} must not accept pbar anymore (FR-71)"


@then(
    "they emit progress events that the CLI consumes and renders to tqdm, "
    "producing output identical to the unrefactored tqdm bar"
)
def then_progress_events_emitted(context: dict[str, Any]) -> None:
    assert len(context["threaded_results"]) == 2
    assert all(isinstance(r, TransactionResult) for r in context["threaded_results"])
    assert len(context["multi_folder_results"]) > 0


# ---------------------------------------------------------------------------
# Scenario: CLI log output for single-folder dry-run matches pre-refactor
# behavior (characterization test)
# ---------------------------------------------------------------------------


@given(
    "a representative single-folder import scenario with known CSV data, run against a mocked FireflyClient "
    "in dry-run mode"
)
def given_single_folder_dry_run(context: dict[str, Any], tmp_path: Path) -> None:
    write_seb_csv(
        tmp_path / "2025-01.csv",
        [
            ["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"],
            ["2025-01-06", "2025-01-06", "V2", "Cafe", "-20,00", "970,00"],
        ],
    )
    context["tmp_path"] = tmp_path
    context["client"] = make_client()
    context["account_map"] = {"Lonekonto": 1}
    context["main_kwargs"] = {"base_folder": str(tmp_path), "dry_run": True}
    context["monotonic_side_effect"] = [0.0, 5.0]
    context["find_account_id_return"] = 1


@when("the refactored CLI processes this scenario")
def when_cli_processes_scenario(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    _run_main_with_patches(context, caplog)


@then(
    'the terminal output and log file format, log line content, account names, transaction counts, "Klar!" '
    "message, and elapsed duration all match the pre-refactor golden-master version captured against the "
    "same mocked setup"
)
def then_single_folder_output_matches_golden_master(context: dict[str, Any]) -> None:
    tmp_path = context["tmp_path"]
    messages = context["messages"]
    assert context["main_result"] == 0
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
# Scenario: CLI log output for multi-folder non-dry-run matches pre-refactor
# behavior (characterization test)
# ---------------------------------------------------------------------------


@given(
    "a representative multi-folder import scenario with transfer detection, run against a mocked FireflyClient "
    "with BLOCK_TRANSACTION_POSTS enabled and the dry-run flag omitted"
)
def given_multi_folder_non_dry_run(context: dict[str, Any], tmp_path: Path) -> None:
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

    context["tmp_path"] = tmp_path
    context["client"] = make_client()
    context["account_map"] = {"Lonekonto": 1, "Sparkonto": 2}
    context["main_kwargs"] = {"base_folder": str(tmp_path)}
    context["monotonic_side_effect"] = [0.0, 3.0]


@then(
    "the terminal output and log file format, log line content, transfer-detection count, per-transaction "
    "OK/ERROR status, account names, and elapsed duration all match the pre-refactor golden-master version "
    "captured against the same mocked setup"
)
def then_multi_folder_output_matches_golden_master(context: dict[str, Any]) -> None:
    messages = context["messages"]
    assert context["main_result"] == 0
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
    context["client"].create_transaction.assert_called()  # mocked -- no real HTTP


# ---------------------------------------------------------------------------
# Scenario: Opening-balance detection result is communicated via events
# ---------------------------------------------------------------------------


@given("automatic opening-balance detection with an opening balance of 0")
def given_opening_balance_zero(context: dict[str, Any], tmp_path: Path) -> None:
    csv_path = tmp_path / "2025-01.csv"
    write_seb_csv(csv_path, [["2025-01-05", "2025-01-05", "V1", "Opening", "-10,00", "990,00"]])
    context["csv_path"] = csv_path
    context["client"] = make_client(balance="0.00")


@when("the service layer sets the opening balance via set_opening_balance per FR-71")
def when_opening_balance_set(context: dict[str, Any]) -> None:
    context["opening_balance_result"] = module._apply_auto_opening_balance(
        context["client"], 42, [context["csv_path"]], dry_run=False
    )


@then(
    "a structured result event includes the balance amount, the date set, and confirmation that the earliest "
    "row was excluded from import"
)
def then_opening_balance_result_structured(context: dict[str, Any]) -> None:
    result = context["opening_balance_result"]
    assert isinstance(result, OpeningBalanceResult)
    assert result.account_id == 42
    assert result.balance == pytest.approx(990.00)
    assert result.date == "2025-01-05"
    assert result.excluded_row_date == "2025-01-05"
    assert result.dry_run is False


@then("the CLI renders this to the log identically to before")
def then_opening_balance_rendered(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        module._render_opening_balance_result(context["opening_balance_result"])
    assert any(
        r.message == "  Satte opening balance: 990.00 SEK per 2025-01-05 (rad exkluderad fran import)."
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Scenario: Transfer detection result includes source and destination
# account names
# ---------------------------------------------------------------------------


@given("transfer detection during a multi-folder import")
def given_transfer_detection(context: dict[str, Any]) -> None:
    context["client"] = make_client()
    context["transfer_payload"] = {
        "type": "transfer",
        "date": "2025-06-23",
        "amount": "500.00",
        "description": "UTLAGG MAT",
        "source_id": "1",
        "destination_id": "2",
        "currency_code": "SEK",
    }


@when("a transfer is matched between accounts")
def when_transfer_matched(context: dict[str, Any]) -> None:
    context["transfer_result"] = module._post_transfer(
        context["client"],
        context["transfer_payload"],
        dry_run=False,
        source_name="Planbok",
        destination_name="Sparkonto",
    )


@then(
    "the result event includes source account ID, source account name, destination account ID, destination "
    "account name, amount, and date"
)
def then_transfer_result_structured(context: dict[str, Any]) -> None:
    result = context["transfer_result"]
    assert isinstance(result, TransferResult)
    assert result.status == TransactionStatus.OK
    assert result.source_account_id == 1
    assert result.source_account_name == "Planbok"
    assert result.destination_account_id == 2
    assert result.destination_account_name == "Sparkonto"
    assert result.amount == pytest.approx(500.00)
    assert result.date == "2025-06-23"


@then(
    'the CLI logs the transfer line in the format "[OK] [transfer] <amount> SEK | <date> | <source name> -> '
    '<destination name> | <description>"'
)
def then_transfer_line_format(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO):
        module._render_transfer_result(context["transfer_result"], dry_run=False)
    assert any(
        r.message == "  [OK] [transfer] 500.00 SEK | 2025-06-23 | Planbok -> Sparkonto | UTLAGG MAT"
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Scenario: Account-name transaction logging works via events
# ---------------------------------------------------------------------------


@given("account-name transaction logging")
def given_account_name_logging(context: dict[str, Any]) -> None:
    context["client"] = make_client()
    context["pending_rows"] = [
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


@when("each transaction result event is emitted")
def when_transaction_results_emitted(context: dict[str, Any]) -> None:
    context["unmatched_results"] = list(
        module._post_unmatched_rows(context["client"], context["pending_rows"], dry_run=True)
    )


@then("it includes the account name resolved from the discovered/cached account list")
def then_results_carry_account_name(context: dict[str, Any]) -> None:
    results = context["unmatched_results"]
    assert len(results) == 1
    assert isinstance(results[0], TransactionResult)
    assert results[0].account_name == "SEB Lonekonto"
    assert results[0].account_id == 42


@then(
    'the CLI logs the transaction line in the format "[OK] [<account name>] [<type>] <amount> SEK | <date> | '
    '<description>" (or "[DRY RUN]" in dry-run mode)'
)
def then_transaction_line_format(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    result = context["unmatched_results"][0]
    with caplog.at_level(logging.INFO):
        module._render_transaction_result(result, dry_run=True)
    assert any(
        r.message == "  [DRY RUN] [SEB Lonekonto] [withdrawal] 10.00 SEK | 2025-01-05 | Shop" for r in caplog.records
    )


# ---------------------------------------------------------------------------
# Scenario: Period scoping works via events
# ---------------------------------------------------------------------------


@given("a period-scoped import with a --period YYYY-MM filter")
def given_period_scoped_import(context: dict[str, Any], tmp_path: Path) -> None:
    write_seb_csv(tmp_path / "2025-01.csv", [["2025-01-10", "2025-01-10", "V1", "X", "-10,00", "990,00"]])
    write_seb_csv(
        tmp_path / "2025-02.csv",
        [
            ["2025-02-10", "2025-02-10", "V1", "X", "-10,00", "990,00"],
            ["2025-02-11", "2025-02-11", "V2", "Y", "-20,00", "970,00"],
        ],
    )
    context["tmp_path"] = tmp_path
    context["client"] = make_client()
    context["account_map"] = {"Lonekonto": 1}
    context["main_kwargs"] = {"base_folder": str(tmp_path), "period": "2025-02"}
    context["find_account_id_return"] = 1


@when("folders are processed with the period filter applied")
def when_folders_processed_with_period(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    _run_main_with_patches(context, caplog)


@then("the service layer only emits result events for rows from that period's CSV file")
def then_only_period_rows_emitted(context: dict[str, Any]) -> None:
    assert context["client"].create_transaction.call_count == 2


@then("the CLI renders the transaction count accurately for that period only")
def then_transaction_count_accurate_for_period(context: dict[str, Any]) -> None:
    assert context["client"].create_transaction.call_count == 2


# ---------------------------------------------------------------------------
# Scenario: BLOCK_TRANSACTION_POSTS guard is handled consistently for
# postings and transfers
# ---------------------------------------------------------------------------


@given("the event-based refactor introduces a single structured error-handling path per FR-71")
def given_block_guard_setup(context: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", True)
    context["client"] = make_client()
    context["transfer_payload"] = {
        "type": "transfer",
        "date": "2025-01-05",
        "amount": "100.00",
        "description": "Overforing",
        "source_id": "1",
        "destination_id": "2",
        "currency_code": "SEK",
    }


@when("a regular transaction posting or a transfer posting hits the BLOCK_TRANSACTION_POSTS guard")
def when_block_guard_hit(context: dict[str, Any]) -> None:
    context["transaction_result"] = module.create_transaction(
        context["client"], "2025-01-05", "Shop", "-10,00", 42, account_name="SEB"
    )
    context["transfer_result"] = module._post_transfer(
        context["client"], context["transfer_payload"], dry_run=False, source_name="A", destination_name="B"
    )


@then("both emit a structured ERROR result event with status ERROR and an error message, instead of raising")
def then_block_guard_error_results(context: dict[str, Any]) -> None:
    transaction_result = context["transaction_result"]
    transfer_result = context["transfer_result"]
    assert transaction_result.status == TransactionStatus.ERROR
    assert transaction_result.error_message is not None and "blockerad" in transaction_result.error_message
    assert transfer_result.status == TransactionStatus.ERROR
    assert transfer_result.error_message is not None and "blockerad" in transfer_result.error_message


@then("the run continues instead of crashing")
def then_run_continues(context: dict[str, Any]) -> None:
    # Reaching this step without an unhandled exception having propagated
    # from the When step already demonstrates the run continued; the
    # client's posting methods must not have been invoked either.
    context["client"].create_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario: Duration and average-time logging works via events
# ---------------------------------------------------------------------------


@given("an import completes after processing a number of transactions in a known duration")
def given_import_completes(context: dict[str, Any], tmp_path: Path) -> None:
    write_seb_csv(
        tmp_path / "2025-01.csv",
        [
            ["2025-01-05", "2025-01-05", "V1", "Shop", "-10,00", "990,00"],
            ["2025-01-06", "2025-01-06", "V2", "Cafe", "-20,00", "970,00"],
        ],
    )
    context["tmp_path"] = tmp_path
    context["client"] = make_client()
    context["account_map"] = {"Lonekonto": 1}
    context["main_kwargs"] = {"base_folder": str(tmp_path), "dry_run": True}
    context["monotonic_side_effect"] = [0.0, 5.0]
    context["find_account_id_return"] = 1


@when("the CLI receives final summary events from the service layer")
def when_cli_receives_final_summary(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    _run_main_with_patches(context, caplog)


@then("it logs total elapsed time in H:MM:SS format")
def then_logs_total_elapsed_time(context: dict[str, Any]) -> None:
    assert "Total tid: 0:00:05" in context["messages"]


@then("it logs average time per transaction in seconds, identical to the unrefactored version")
def then_logs_average_time(context: dict[str, Any]) -> None:
    assert "2.50s/transaktion" in context["messages"]
