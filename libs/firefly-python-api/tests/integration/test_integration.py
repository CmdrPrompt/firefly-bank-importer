"""Integration tests — connect to a real Firefly III instance.

Run with:
    make test-integration

Skipped automatically when FIREFLY_URL or FIREFLY_TOKEN is absent.
No write operations are performed.
"""

from __future__ import annotations

import os

import pytest

from firefly_python_api import FireflyClient, load_config


def _credentials_present() -> bool:
    return bool(os.environ.get("FIREFLY_URL")) and bool(os.environ.get("FIREFLY_TOKEN"))


skip_if_no_credentials = pytest.mark.skipif(
    not _credentials_present(),
    reason="FIREFLY_URL and/or FIREFLY_TOKEN not set",
)


@pytest.fixture(scope="module")
def client() -> FireflyClient:
    try:
        url, token = load_config()
    except ValueError:
        pytest.skip("FIREFLY_URL and/or FIREFLY_TOKEN not set")
    return FireflyClient(url=url, token=token)


# ---------------------------------------------------------------------------
# UC-004-1: validate_connection
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_validate_connection(client: FireflyClient) -> None:
    assert client.validate_connection() is True


# ---------------------------------------------------------------------------
# UC-004-2: get_asset_accounts
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_asset_accounts_returns_list(client: FireflyClient) -> None:
    accounts = client.get_asset_accounts()
    assert isinstance(accounts, list)
    assert len(accounts) > 0, "Expected at least one asset account"


@skip_if_no_credentials
def test_get_asset_accounts_items_have_id_and_name(client: FireflyClient) -> None:
    accounts = client.get_asset_accounts()
    for account in accounts:
        assert "id" in account
        assert "name" in account
        assert isinstance(account["id"], str)
        assert isinstance(account["name"], str)


# ---------------------------------------------------------------------------
# UC-004-3: get_latest_transaction_date
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_latest_transaction_date(client: FireflyClient) -> None:
    accounts = client.get_asset_accounts()
    account_id = accounts[0]["id"]
    result = client.get_latest_transaction_date(account_id)
    if result is not None:
        assert len(result) == 10, f"Expected YYYY-MM-DD, got: {result}"
        assert result[4] == "-" and result[7] == "-"


# ---------------------------------------------------------------------------
# UC-004-4: reporting methods
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_bills_returns_list(client: FireflyClient) -> None:
    result = client.get_bills()
    assert isinstance(result, list)


@skip_if_no_credentials
def test_get_budgets_returns_list(client: FireflyClient) -> None:
    result = client.get_budgets()
    assert isinstance(result, list)


@skip_if_no_credentials
def test_get_categories_returns_list(client: FireflyClient) -> None:
    result = client.get_categories()
    assert isinstance(result, list)


@skip_if_no_credentials
def test_get_summary_returns_dict(client: FireflyClient) -> None:
    result = client.get_summary(start="2024-01-01", end="2024-12-31")
    assert isinstance(result, dict)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# UC-010-1: get_opening_balance
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_opening_balance_returns_balance_and_date(client: FireflyClient) -> None:
    accounts = client.get_asset_accounts()
    account_id = accounts[0]["id"]
    result = client.get_opening_balance(account_id)
    assert "balance" in result
    assert "date" in result
    if result["date"] is not None:
        assert len(result["date"]) == 10, f"Expected YYYY-MM-DD, got: {result['date']}"


# ---------------------------------------------------------------------------
# UC-011-1: get_transactions_by_type
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_transactions_by_type_returns_list_of_transaction_read(client: FireflyClient) -> None:
    result = client.get_transactions_by_type(
        "withdrawal,deposit", start="2024-01-01", end="2024-12-31"
    )
    assert isinstance(result, list)
    for transaction in result:
        assert "date" in transaction
        assert "amount" in transaction
        assert "destination_id" in transaction
        assert transaction["destination_id"] is None or isinstance(
            transaction["destination_id"], str
        )


@skip_if_no_credentials
def test_get_withdrawal_transactions_still_works_after_refactor(client: FireflyClient) -> None:
    result = client.get_withdrawal_transactions(start="2024-01-01", end="2024-12-31")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# UC-004-5: get_transactions_for_account, get_budget_limits
# ---------------------------------------------------------------------------


@skip_if_no_credentials
def test_get_transactions_for_account_returns_list_of_ids(client: FireflyClient) -> None:
    accounts = client.get_asset_accounts()
    account_id = accounts[0]["id"]
    result = client.get_transactions_for_account(account_id)
    assert isinstance(result, list)
    for transaction_id in result:
        assert isinstance(transaction_id, str)


@skip_if_no_credentials
def test_get_budget_limits_returns_list(client: FireflyClient) -> None:
    budgets = client.get_budgets()
    if not budgets:
        pytest.skip("No budgets on the configured Firefly III instance")
    budget_id = budgets[0]["id"]
    result = client.get_budget_limits(budget_id)
    assert isinstance(result, list)
