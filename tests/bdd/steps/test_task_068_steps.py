"""Step definitions for TASK-068's BDD feature file.

Binds `tests/bdd/features/TASK-068-finalize-service-layer-interface.feature`
to the finalized, documented public service-layer interface
(`firefly_bank_importer.service`). Per FR-71/72/73, the public surface
(`fetch_accounts_from_firefly`, `create_transaction`,
`apply_auto_opening_balance`, `post_transfer`, `run_multi_folder_import`,
plus the event/result types) must live in `firefly_bank_importer.service`,
be importable without pulling in the CLI module
(`firefly_bank_importer.import_firefly`), be fully docstringed, be
documented in `docs/SERVICE_LAYER_INTERFACE.md`, have no web-framework/HTTP
server dependency, and communicate exclusively via return values and event
objects (no logging emitted by the service layer itself).

All scenarios run against a mocked `FireflyClient` (MagicMock/monkeypatch),
per the project's established testing convention. No real HTTP calls are
made to any Firefly instance.
"""

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from firefly_python_api import FireflyClient
from pytest_bdd import given, scenarios, then, when

scenarios("../features/TASK-068-finalize-service-layer-interface.feature")

_REPO_ROOT = Path(__file__).resolve().parents[3]

PUBLIC_FUNCTION_NAMES = [
    "fetch_accounts_from_firefly",
    "create_transaction",
    "apply_auto_opening_balance",
    "post_transfer",
    "run_multi_folder_import",
]

PUBLIC_TYPE_NAMES = [
    "TransactionResult",
    "TransferResult",
    "OpeningBalanceResult",
    "TransferDetectionSummary",
    "FolderResult",
    "ProgressEvent",
    "PendingRow",
    "TransactionStatus",
]

FORBIDDEN_DEPENDENCY_NAMES = ["flask", "fastapi", "django", "uvicorn", "gunicorn", "waitress"]


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": "100.00", "date": None}
    return client


@pytest.fixture
def context() -> dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# Scenario: Service layer has stable, documented public interface
# ---------------------------------------------------------------------------


@given("the refactored service layer from TASK-067")
def given_refactored_service_layer(context: dict[str, Any]) -> None:
    import firefly_bank_importer.service as service_module

    context["service_module"] = service_module


@when(
    "external documentation (docstrings, interface guide, or README section) describes the importable "
    "module path and public functions/classes per FR-71/FR-73"
)
def when_documentation_examined(context: dict[str, Any]) -> None:
    service_module = context["service_module"]
    context["public_names"] = PUBLIC_FUNCTION_NAMES + PUBLIC_TYPE_NAMES
    context["docstrings"] = {
        name: getattr(getattr(service_module, name, None), "__doc__", None) for name in context["public_names"]
    }
    interface_doc_path = _REPO_ROOT / "docs" / "SERVICE_LAYER_INTERFACE.md"
    context["interface_doc_path"] = interface_doc_path
    context["interface_doc_text"] = (
        interface_doc_path.read_text(encoding="utf-8") if interface_doc_path.exists() else ""
    )


@then(
    "the public functions, classes, event types, and their parameters, return types, and exceptions are "
    "clearly documented so an external application can use them"
)
def then_public_surface_documented(context: dict[str, Any]) -> None:
    for name, doc in context["docstrings"].items():
        assert doc is not None and doc.strip() != "", f"{name} must have a non-empty docstring"

    assert context["interface_doc_path"].exists(), "docs/SERVICE_LAYER_INTERFACE.md must exist"
    interface_doc_text = context["interface_doc_text"]
    for name in PUBLIC_FUNCTION_NAMES:
        assert name in interface_doc_text, f"docs/SERVICE_LAYER_INTERFACE.md must mention {name}"


# ---------------------------------------------------------------------------
# Scenario: Service layer can be imported and used without CLI code
# ---------------------------------------------------------------------------


@given("an external application (not this repo) imports the service layer per FR-73")
def given_external_app_imports_service(context: dict[str, Any]) -> None:
    subprocess_check = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import firefly_bank_importer.service; "
            "assert 'firefly_bank_importer.import_firefly' not in sys.modules, "
            "'importing service must not import the CLI module'",
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
    )
    context["import_isolation_result"] = subprocess_check


@when(
    "it instantiates a FireflyClient separately (or provides a mocked one for testing) and calls a public "
    "service-layer function with configuration (folder paths, flags, client instance)"
)
def when_calls_public_service_function(context: dict[str, Any]) -> None:
    from firefly_bank_importer.service import create_transaction

    client = make_client()
    context["client"] = client
    context["call_result"] = create_transaction(client, "2025-01-05", "Shop", "-10,00", 42, account_name="SEB")


@then(
    "the import succeeds, the function runs without argparse or sys.exit logic, and all results are "
    "delivered through return values and event objects (not logging or stdout)"
)
def then_import_and_call_succeed(context: dict[str, Any]) -> None:
    from firefly_bank_importer.service import TransactionResult

    isolation_result = context["import_isolation_result"]
    assert isolation_result.returncode == 0, (
        f"importing firefly_bank_importer.service must not import the CLI module: {isolation_result.stderr}"
    )
    assert isinstance(context["call_result"], TransactionResult)


# ---------------------------------------------------------------------------
# Scenario: Service layer has no web framework or HTTP server dependency
# ---------------------------------------------------------------------------


@given("the service-layer module and its test suite")
def given_service_module_and_tests(context: dict[str, Any]) -> None:
    context["pyproject_text"] = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    context["service_source_text"] = (_REPO_ROOT / "src" / "firefly_bank_importer" / "service.py").read_text(
        encoding="utf-8"
    )


@when("the module dependencies are analyzed (import statements, pyproject.toml dependencies)")
def when_dependencies_analyzed(context: dict[str, Any]) -> None:
    lowered_pyproject = context["pyproject_text"].lower()
    lowered_service_source = context["service_source_text"].lower()
    context["found_in_pyproject"] = [name for name in FORBIDDEN_DEPENDENCY_NAMES if name in lowered_pyproject]
    context["found_in_service"] = [name for name in FORBIDDEN_DEPENDENCY_NAMES if name in lowered_service_source]


@then(
    "no web framework (Flask, FastAPI, Django) or HTTP server (uvicorn, gunicorn, waitress) appears as a "
    "dependency or import within the service layer itself; only `firefly-python-api` and standard library "
    "are used for HTTP"
)
def then_no_forbidden_dependencies(context: dict[str, Any]) -> None:
    assert context["found_in_pyproject"] == [], (
        f"pyproject.toml must not depend on web frameworks/servers: {context['found_in_pyproject']}"
    )
    assert context["found_in_service"] == [], (
        f"service.py must not import web frameworks/servers: {context['found_in_service']}"
    )


# ---------------------------------------------------------------------------
# Scenario: Service layer results are communicated via return values and
# event objects
# ---------------------------------------------------------------------------


@given("an external application calls service-layer functions")
def given_external_app_calls_service_functions(context: dict[str, Any], tmp_path: Path) -> None:
    import csv

    headers = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
    folder_a = tmp_path / "kontoutdrag_Lonekonto"
    folder_b = tmp_path / "kontoutdrag_Sparkonto"
    folder_a.mkdir()
    folder_b.mkdir()
    for folder, amount, balance in ((folder_a, "-100,00", "900,00"), (folder_b, "100,00", "1100,00")):
        with open(folder / "2025-01.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow(headers)
            writer.writerow(["2025-01-05", "2025-01-05", "V1", "Overforing", amount, balance])

    context["folders"] = [folder_a, folder_b]
    context["account_map"] = {"Lonekonto": 1, "Sparkonto": 2}
    context["client"] = make_client()


@when("it provides a callback or event listener for progress/result events")
def when_callback_provided_for_events(context: dict[str, Any], caplog: pytest.LogCaptureFixture) -> None:
    from firefly_bank_importer.service import run_multi_folder_import

    with caplog.at_level(logging.INFO):
        context["events"] = list(
            run_multi_folder_import(
                context["client"],
                context["folders"],
                context["account_map"],
                dry_run=True,
                ignore_latest_date_check=True,
            )
        )
    context["log_records"] = list(caplog.records)


@then(
    "all transaction results, folder summaries, and progress updates are delivered through those event "
    "objects and return values, with no reliance on globals, direct logging configuration, or "
    "stdout/stderr redirection from the calling environment"
)
def then_events_and_no_logging(context: dict[str, Any]) -> None:
    from firefly_bank_importer.service import (
        FolderResult,
        OpeningBalanceResult,
        ProgressEvent,
        TransactionResult,
        TransferDetectionSummary,
        TransferResult,
    )

    documented_event_types = (
        TransactionResult,
        TransferResult,
        OpeningBalanceResult,
        TransferDetectionSummary,
        FolderResult,
        ProgressEvent,
    )
    events = context["events"]
    assert events, "run_multi_folder_import must yield at least one event"
    assert all(isinstance(event, documented_event_types) for event in events)
    assert context["log_records"] == [], "service-layer call must not emit any logging records"
