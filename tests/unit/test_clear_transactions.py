"""Tests for clear_transactions.py (TASK-051, UC-29, FR-64).

Covers account-selection resolution, transaction collection/deletion against
a mocked FireflyClient, the confirmation gate, --dry-run behavior, and CLI
argument parsing.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient

import firefly_bank_importer.clear_transactions as module
from firefly_bank_importer.clear_transactions import (
    _parse_cli_args,
    collect_transactions_by_account,
    confirm_deletion,
    delete_transactions,
    log_summary,
    main,
    resolve_target_accounts,
)
from firefly_bank_importer.import_firefly import Account

ACCOUNTS: list[Account] = [
    {"id": 1, "name": "Lönekonto", "type": "asset"},
    {"id": 2, "name": "Sparkonto", "type": "asset"},
    {"id": 3, "name": "Buffertkonto", "type": "asset"},
]


def make_client() -> MagicMock:
    return MagicMock(spec=FireflyClient)


# ---------------------------------------------------------------------------
# resolve_target_accounts
# ---------------------------------------------------------------------------


class TestResolveTargetAccounts:
    def test_none_returns_all_accounts(self) -> None:
        assert resolve_target_accounts(ACCOUNTS, None) == ACCOUNTS

    def test_list_returns_matching_subset(self) -> None:
        result = resolve_target_accounts(ACCOUNTS, ["Sparkonto"])
        assert result == [ACCOUNTS[1]]

    def test_list_preserves_requested_order(self) -> None:
        result = resolve_target_accounts(ACCOUNTS, ["Buffertkonto", "Lönekonto"])
        assert result == [ACCOUNTS[2], ACCOUNTS[0]]

    def test_unknown_account_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Okänt"):
            resolve_target_accounts(ACCOUNTS, ["Okänt konto"])

    def test_empty_list_returns_empty(self) -> None:
        assert resolve_target_accounts(ACCOUNTS, []) == []


# ---------------------------------------------------------------------------
# collect_transactions_by_account
# ---------------------------------------------------------------------------


class TestCollectTransactionsByAccount:
    def test_calls_client_per_account(self) -> None:
        client = make_client()
        client.get_transactions_for_account.side_effect = [["10", "11"], ["20"]]

        result = collect_transactions_by_account(client, ACCOUNTS[:2])

        assert result == {"Lönekonto": ["10", "11"], "Sparkonto": ["20"]}
        assert client.get_transactions_for_account.call_args_list == [
            (("1",),),
            (("2",),),
        ]

    def test_account_with_no_transactions(self) -> None:
        client = make_client()
        client.get_transactions_for_account.return_value = []

        result = collect_transactions_by_account(client, [ACCOUNTS[0]])

        assert result == {"Lönekonto": []}


# ---------------------------------------------------------------------------
# log_summary
# ---------------------------------------------------------------------------


class TestLogSummary:
    def test_returns_total_count(self) -> None:
        total = log_summary({"Lönekonto": ["10", "11"], "Sparkonto": ["20"]})
        assert total == 3

    def test_zero_transactions(self) -> None:
        assert log_summary({"Lönekonto": []}) == 0

    def test_logs_per_account_and_total(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO):
            log_summary({"Lönekonto": ["10", "11"]})
        assert "Lönekonto" in caplog.text
        assert "2" in caplog.text


# ---------------------------------------------------------------------------
# confirm_deletion
# ---------------------------------------------------------------------------


class TestConfirmDeletion:
    def test_ja_confirms(self) -> None:
        with patch("builtins.input", return_value="JA"):
            assert confirm_deletion() is True

    def test_other_input_does_not_confirm(self) -> None:
        with patch("builtins.input", return_value="nej"):
            assert confirm_deletion() is False

    def test_empty_input_does_not_confirm(self) -> None:
        with patch("builtins.input", return_value=""):
            assert confirm_deletion() is False


# ---------------------------------------------------------------------------
# delete_transactions
# ---------------------------------------------------------------------------


class TestDeleteTransactions:
    def test_deletes_every_transaction_id(self) -> None:
        client = make_client()
        counts = delete_transactions(client, {"Lönekonto": ["10", "11"], "Sparkonto": ["20"]})

        assert counts == {"Lönekonto": 2, "Sparkonto": 1}
        assert client.delete_transaction.call_args_list == [
            (("10",),),
            (("11",),),
            (("20",),),
        ]

    def test_account_with_no_transactions_deletes_nothing(self) -> None:
        client = make_client()
        counts = delete_transactions(client, {"Lönekonto": []})

        assert counts == {"Lönekonto": 0}
        client.delete_transaction.assert_not_called()


# ---------------------------------------------------------------------------
# _parse_cli_args
# ---------------------------------------------------------------------------


class TestParseCliArgs:
    def test_all_flag(self) -> None:
        account_names, dry_run = _parse_cli_args(["prog", "--all"])
        assert account_names is None
        assert dry_run is False

    def test_all_flag_with_dry_run(self) -> None:
        account_names, dry_run = _parse_cli_args(["prog", "--all", "--dry-run"])
        assert account_names is None
        assert dry_run is True

    def test_accounts_flag(self) -> None:
        account_names, dry_run = _parse_cli_args(["prog", "--accounts", "Lönekonto,Sparkonto"])
        assert account_names == ["Lönekonto", "Sparkonto"]
        assert dry_run is False

    def test_accounts_flag_strips_whitespace(self) -> None:
        account_names, _ = _parse_cli_args(["prog", "--accounts", " Lönekonto , Sparkonto "])
        assert account_names == ["Lönekonto", "Sparkonto"]

    def test_missing_selection_raises(self) -> None:
        with pytest.raises(ValueError, match="Användning"):
            _parse_cli_args(["prog"])

    def test_both_all_and_accounts_raises(self) -> None:
        with pytest.raises(ValueError, match="antingen"):
            _parse_cli_args(["prog", "--all", "--accounts", "Lönekonto"])

    def test_accounts_flag_without_value_raises(self) -> None:
        with pytest.raises(ValueError, match="kräver"):
            _parse_cli_args(["prog", "--accounts"])

    def test_accounts_flag_with_empty_value_raises(self) -> None:
        with pytest.raises(ValueError, match="kräver"):
            _parse_cli_args(["prog", "--accounts", "  , "])


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


class TestMain:
    def _patch_setup(self, accounts: list[Account]) -> tuple[MagicMock, MagicMock]:
        client = make_client()
        client_cls = MagicMock(return_value=client)
        return client, client_cls

    def test_dry_run_does_not_delete_and_does_not_prompt(self) -> None:
        client = make_client()
        client.get_transactions_for_account.return_value = ["10"]

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(module, "build_account_map", return_value=({"Lönekonto": 1}, [ACCOUNTS[0]])),
            patch.object(module, "confirm_deletion") as mock_confirm,
        ):
            result = main(["prog", "--all", "--dry-run"])

        assert result == 0
        mock_confirm.assert_not_called()
        client.delete_transaction.assert_not_called()

    def test_declined_confirmation_does_not_delete(self) -> None:
        client = make_client()
        client.get_transactions_for_account.return_value = ["10"]

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(module, "build_account_map", return_value=({"Lönekonto": 1}, [ACCOUNTS[0]])),
            patch.object(module, "confirm_deletion", return_value=False),
        ):
            result = main(["prog", "--all"])

        assert result == 0
        client.delete_transaction.assert_not_called()

    def test_confirmed_deletion_deletes_all_selected_accounts(self) -> None:
        client = make_client()
        client.get_transactions_for_account.side_effect = [["10", "11"], ["20"]]

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(
                module,
                "build_account_map",
                return_value=({"Lönekonto": 1, "Sparkonto": 2}, ACCOUNTS[:2]),
            ),
            patch.object(module, "confirm_deletion", return_value=True),
        ):
            result = main(["prog", "--all"])

        assert result == 0
        assert client.delete_transaction.call_count == 3

    def test_accounts_selection_only_deletes_named_accounts(self) -> None:
        client = make_client()
        client.get_transactions_for_account.return_value = ["10"]

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(
                module,
                "build_account_map",
                return_value=({"Lönekonto": 1, "Sparkonto": 2}, ACCOUNTS[:2]),
            ),
            patch.object(module, "confirm_deletion", return_value=True),
        ):
            result = main(["prog", "--accounts", "Sparkonto"])

        assert result == 0
        client.get_transactions_for_account.assert_called_once_with("2")

    def test_unknown_account_name_aborts_without_deleting(self) -> None:
        client = make_client()

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(module, "build_account_map", return_value=({"Lönekonto": 1}, [ACCOUNTS[0]])),
        ):
            result = main(["prog", "--accounts", "Okänt konto"])

        assert result == 1
        client.get_transactions_for_account.assert_not_called()
        client.delete_transaction.assert_not_called()

    def test_no_transactions_skips_confirmation(self) -> None:
        client = make_client()
        client.get_transactions_for_account.return_value = []

        with (
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "load_api_token", return_value="tok"),
            patch.object(module, "load_firefly_url", return_value="http://x"),
            patch.object(module, "build_account_map", return_value=({"Lönekonto": 1}, [ACCOUNTS[0]])),
            patch.object(module, "confirm_deletion") as mock_confirm,
        ):
            result = main(["prog", "--all"])

        assert result == 0
        mock_confirm.assert_not_called()

    def test_invalid_args_returns_error_code(self) -> None:
        result = main(["prog"])
        assert result == 1
