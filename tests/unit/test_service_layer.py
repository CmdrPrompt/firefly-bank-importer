"""Characterisation tests for the service layer module (TASK-066, FR-71/72/73).

Covers:
- the module has no CLI-only dependencies (argparse, tqdm, sys.exit, print),
- the transfer-matching helpers behave identically once moved here,
- the structured result/event types are constructible and inspectable.
"""

import ast
from datetime import date
from pathlib import Path

from firefly_bank_importer import service
from firefly_bank_importer.service import (
    PendingRow,
    ProgressEvent,
    TransactionResult,
    TransactionStatus,
    _choose_candidate,
    _description_overlap,
    _match_transfer_pairs,
    parse_amount,
)

SERVICE_MODULE_PATH = Path(service.__file__)

FORBIDDEN_IMPORTS = {"tqdm", "argparse"}


class TestNoCliDependencies:
    def test_module_does_not_import_cli_only_libraries(self) -> None:
        tree = ast.parse(SERVICE_MODULE_PATH.read_text(encoding="utf-8"))
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names.add(node.module.split(".")[0])
        assert imported_names.isdisjoint(FORBIDDEN_IMPORTS)

    def test_module_does_not_call_print_or_sys_exit(self) -> None:
        tree = ast.parse(SERVICE_MODULE_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                raise AssertionError("service module must not call print()")
            if isinstance(func, ast.Attribute) and func.attr == "exit":
                assert not (isinstance(func.value, ast.Name) and func.value.id == "sys")


def row(account_id: int, iso_date: str, description: str, amount: str, bank_format: str = "seb") -> PendingRow:
    return PendingRow(
        account_id=account_id,
        account_name=str(account_id),
        iso_date=iso_date,
        description=description,
        amount=amount,
        bank_format=bank_format,
        row_date=date.fromisoformat(iso_date),
    )


class TestExtractedHelpersBehaveIdentically:
    def test_description_overlap(self) -> None:
        assert _description_overlap("K*Amazon", "K*Amazon SE") is True
        assert _description_overlap("Lon", "Hyra") is False

    def test_choose_candidate(self) -> None:
        rows = [row(1, "2025-01-05", "X", "-100.00"), row(2, "2025-01-05", "Y", "100.00")]
        assert _choose_candidate(rows[0], rows, [1]) == 1

    def test_match_transfer_pairs(self) -> None:
        rows = [row(1, "2025-01-05", "Overforing", "-100.00"), row(2, "2025-01-05", "Unrelated text", "100.00")]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == [(0, 1)]
        assert matched == {0, 1}

    def test_parse_amount(self) -> None:
        assert parse_amount("1 234,56 kr") == 1234.56


class TestStructuredTypes:
    def test_transaction_result_is_constructible_and_inspectable(self) -> None:
        result = TransactionResult(
            date="2025-01-05",
            amount=100.0,
            account_id=1,
            status=TransactionStatus.OK,
            error_message=None,
        )
        assert result.date == "2025-01-05"
        assert result.amount == 100.0
        assert result.account_id == 1
        assert result.status == TransactionStatus.OK
        assert result.error_message is None

    def test_transaction_result_error_status(self) -> None:
        result = TransactionResult(
            date="2025-01-05",
            amount=100.0,
            account_id=1,
            status=TransactionStatus.ERROR,
            error_message="boom",
        )
        assert result.status == TransactionStatus.ERROR
        assert result.error_message == "boom"

    def test_folder_result_is_constructible_and_inspectable(self) -> None:
        result = TransactionResult(
            date="2025-01-05", amount=100.0, account_id=1, status=TransactionStatus.OK, error_message=None
        )
        folder_result = service.FolderResult(
            folder="kontoutdrag_Lonekonto",
            account_id=1,
            transactions=[result],
            ok_count=1,
            error_count=0,
        )
        assert folder_result.folder == "kontoutdrag_Lonekonto"
        assert folder_result.transactions == [result]
        assert folder_result.ok_count == 1
        assert folder_result.error_count == 0

    def test_progress_event_is_constructible_and_inspectable(self) -> None:
        event = ProgressEvent(folder="kontoutdrag_Lonekonto", completed=1, total=5)
        assert event.folder == "kontoutdrag_Lonekonto"
        assert event.completed == 1
        assert event.total == 5
