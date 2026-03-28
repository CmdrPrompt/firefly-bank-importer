"""Characterisation tests for build_account_map().

Stubs load_account_cache, fetch_accounts_from_firefly, and save_account_cache
so no real files or HTTP calls are needed.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
import requests

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import Account, build_account_map

ACCOUNTS: list[Account] = [
    {"id": 1, "name": "Lönekonto", "type": "asset"},
    {"id": 2, "name": "Sparkonto", "type": "asset"},
]


def make_session() -> MagicMock:
    return MagicMock(spec=requests.Session)


# ---------------------------------------------------------------------------
# refresh=False, cache hit
# ---------------------------------------------------------------------------


class TestCacheHit:
    def test_returns_map_from_cache(self) -> None:
        with (
            patch.object(module, "load_account_cache", return_value=ACCOUNTS),
            patch.object(module, "fetch_accounts_from_firefly") as mock_fetch,
        ):
            account_map, accounts = build_account_map(make_session(), refresh=False)
            mock_fetch.assert_not_called()
        assert account_map == {"Lönekonto": 1, "Sparkonto": 2}
        assert accounts == ACCOUNTS

    def test_fetch_not_called_when_cache_hit(self) -> None:
        with (
            patch.object(module, "load_account_cache", return_value=ACCOUNTS),
            patch.object(module, "fetch_accounts_from_firefly") as mock_fetch,
            patch.object(module, "save_account_cache") as mock_save,
        ):
            build_account_map(make_session(), refresh=False)
            mock_fetch.assert_not_called()
            mock_save.assert_not_called()


# ---------------------------------------------------------------------------
# refresh=True — cache is skipped, fetch is called
# ---------------------------------------------------------------------------


class TestRefreshTrue:
    def test_fetch_called_even_when_cache_exists(self) -> None:
        with (
            patch.object(module, "load_account_cache", return_value=ACCOUNTS) as mock_load,
            patch.object(module, "fetch_accounts_from_firefly", return_value=ACCOUNTS) as mock_fetch,
            patch.object(module, "save_account_cache"),
        ):
            build_account_map(make_session(), refresh=True)
            mock_load.assert_not_called()
            mock_fetch.assert_called_once()

    def test_cache_saved_after_fetch(self) -> None:
        with (
            patch.object(module, "load_account_cache"),
            patch.object(module, "fetch_accounts_from_firefly", return_value=ACCOUNTS),
            patch.object(module, "save_account_cache") as mock_save,
        ):
            build_account_map(make_session(), refresh=True)
            mock_save.assert_called_once_with(ACCOUNTS)

    def test_returns_correct_map_after_fetch(self) -> None:
        with (
            patch.object(module, "load_account_cache"),
            patch.object(module, "fetch_accounts_from_firefly", return_value=ACCOUNTS),
            patch.object(module, "save_account_cache"),
        ):
            account_map, _ = build_account_map(make_session(), refresh=True)
        assert account_map == {"Lönekonto": 1, "Sparkonto": 2}


# ---------------------------------------------------------------------------
# refresh=False, cache miss, fetch succeeds
# ---------------------------------------------------------------------------


class TestCacheMissFetchSuccess:
    def test_fetches_and_saves_when_no_cache(self) -> None:
        with (
            patch.object(module, "load_account_cache", return_value=None),
            patch.object(module, "fetch_accounts_from_firefly", return_value=ACCOUNTS),
            patch.object(module, "save_account_cache") as mock_save,
        ):
            account_map, accounts = build_account_map(make_session(), refresh=False)
            mock_save.assert_called_once_with(ACCOUNTS)
        assert account_map == {"Lönekonto": 1, "Sparkonto": 2}


# ---------------------------------------------------------------------------
# refresh=False, cache miss, fetch fails, fallback cache hit
# ---------------------------------------------------------------------------


class TestCacheMissFetchFailFallback:
    def test_returns_fallback_cache_on_fetch_error(self, caplog: pytest.LogCaptureFixture) -> None:
        load_call_count = 0

        def load_side_effect() -> list[Account] | None:
            nonlocal load_call_count
            load_call_count += 1
            # First call (before fetch) returns None; second call (fallback) returns ACCOUNTS
            return None if load_call_count == 1 else ACCOUNTS

        with (
            patch.object(module, "load_account_cache", side_effect=load_side_effect),
            patch.object(module, "fetch_accounts_from_firefly", side_effect=RuntimeError("timeout")),
            patch.object(module, "save_account_cache"),
            caplog.at_level(logging.ERROR),
        ):
            account_map, accounts = build_account_map(make_session(), refresh=False)

        assert accounts == ACCOUNTS
        assert account_map == {"Lönekonto": 1, "Sparkonto": 2}


# ---------------------------------------------------------------------------
# refresh=False, cache miss, fetch fails, no fallback → sys.exit(1)
# ---------------------------------------------------------------------------


class TestCacheMissFetchFailNoFallback:
    def test_exits_when_no_cache_and_fetch_fails(self) -> None:
        with (
            patch.object(module, "load_account_cache", return_value=None),
            patch.object(module, "fetch_accounts_from_firefly", side_effect=RuntimeError("timeout")),
            patch.object(module, "save_account_cache"),
            pytest.raises(SystemExit) as exc_info,
        ):
            build_account_map(make_session(), refresh=False)
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# refresh=True, fetch fails, no cache → sys.exit(1)
# ---------------------------------------------------------------------------


class TestRefreshFetchFailNoCache:
    def test_exits_when_refresh_and_fetch_fails(self) -> None:
        with (
            patch.object(module, "load_account_cache"),
            patch.object(module, "fetch_accounts_from_firefly", side_effect=RuntimeError("unreachable")),
            patch.object(module, "save_account_cache"),
            pytest.raises(SystemExit) as exc_info,
        ):
            build_account_map(make_session(), refresh=True)
        assert exc_info.value.code == 1
