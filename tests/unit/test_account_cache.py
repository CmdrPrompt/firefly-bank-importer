"""Characterisation tests for load_account_cache().

Documents current behavior as-is. Uses tmp_path and monkeypatching to avoid
touching the real accounts_cache.json.
"""

import json
from pathlib import Path

import pytest

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import load_account_cache


@pytest.fixture()
def cache_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "accounts_cache.json"
    monkeypatch.setattr(module, "ACCOUNT_CACHE_FILE", path)
    return path


class TestLoadAccountCacheMissingFile:
    def test_missing_file_returns_none(self, cache_path: Path) -> None:
        assert load_account_cache() is None


class TestLoadAccountCacheValidData:
    def test_single_account_returned(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps({"accounts": [{"id": 1, "name": "Lönekonto", "type": "asset"}]}),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 1, "name": "Lönekonto", "type": "asset"}]

    def test_multiple_accounts_returned(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {"id": 1, "name": "Lönekonto", "type": "asset"},
                        {"id": 2, "name": "Sparkonto", "type": "asset"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result is not None
        assert len(result) == 2

    def test_fetched_at_absent_does_not_crash(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps({"accounts": [{"id": 1, "name": "X", "type": "asset"}]}),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result is not None

    def test_fetched_at_present_does_not_crash(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": "2025-01-01T00:00:00",
                    "accounts": [{"id": 1, "name": "X", "type": "asset"}],
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result is not None


class TestLoadAccountCacheTypeField:
    def test_type_defaults_to_asset_when_absent(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps({"accounts": [{"id": 1, "name": "Konto"}]}),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 1, "name": "Konto", "type": "asset"}]


class TestLoadAccountCacheInvalidData:
    def test_invalid_json_returns_none(self, cache_path: Path) -> None:
        cache_path.write_text("not json", encoding="utf-8")
        assert load_account_cache() is None

    def test_accounts_not_a_list_returns_none(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps({"accounts": {"id": 1, "name": "X"}}),
            encoding="utf-8",
        )
        assert load_account_cache() is None

    def test_item_missing_id_is_skipped(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {"name": "No ID", "type": "asset"},
                        {"id": 2, "name": "Valid", "type": "asset"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 2, "name": "Valid", "type": "asset"}]

    def test_item_missing_name_is_skipped(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {"id": 1, "type": "asset"},
                        {"id": 2, "name": "Valid", "type": "asset"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 2, "name": "Valid", "type": "asset"}]

    def test_item_with_wrong_id_type_is_skipped(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        {"id": "not-an-int", "name": "Bad", "type": "asset"},
                        {"id": 2, "name": "Valid", "type": "asset"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 2, "name": "Valid", "type": "asset"}]

    def test_non_dict_item_is_skipped(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "accounts": [
                        "not a dict",
                        {"id": 1, "name": "Valid", "type": "asset"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == [{"id": 1, "name": "Valid", "type": "asset"}]

    def test_all_invalid_items_returns_empty_list(self, cache_path: Path) -> None:
        cache_path.write_text(
            json.dumps({"accounts": [{"name": "no id"}, {"id": "bad", "name": "also bad"}]}),
            encoding="utf-8",
        )
        result = load_account_cache()
        assert result == []
