"""Tests for configuration loading (URL and token) — TASK-002.

Follows TDD: tests are written against the spec (FR-29, FR-30, FR-31, UC-12)
before the implementation exists.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import requests

from firefly_bank_importer.config import (
    load_api_token,
    load_firefly_url,
    validate_firefly_url,
)

# ---------------------------------------------------------------------------
# validate_firefly_url
# ---------------------------------------------------------------------------


class TestValidateFireflyUrl:
    def test_returns_true_on_200(self) -> None:
        mock_get = MagicMock()
        mock_get.return_value.status_code = 200
        assert validate_firefly_url("http://example.local", get_fn=mock_get) is True

    def test_returns_false_on_non_200(self) -> None:
        mock_get = MagicMock()
        mock_get.return_value.status_code = 401
        assert validate_firefly_url("http://example.local", get_fn=mock_get) is False

    def test_returns_false_on_connection_error(self) -> None:
        mock_get = MagicMock(side_effect=requests.ConnectionError)
        assert validate_firefly_url("http://unreachable.local", get_fn=mock_get) is False

    def test_calls_about_endpoint(self) -> None:
        mock_get = MagicMock()
        mock_get.return_value.status_code = 200
        validate_firefly_url("http://example.local:8080", get_fn=mock_get)
        url = mock_get.call_args[0][0]
        assert url == "http://example.local:8080/api/v1/about"

    def test_returns_false_on_timeout(self) -> None:
        mock_get = MagicMock(side_effect=requests.Timeout)
        assert validate_firefly_url("http://slow.local", get_fn=mock_get) is False


# ---------------------------------------------------------------------------
# load_firefly_url — reading from existing config.json
# ---------------------------------------------------------------------------


class TestLoadFireflyUrlFromConfig:
    def test_reads_url_from_existing_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": "http://my-firefly.local"}), encoding="utf-8")
        url = load_firefly_url(config_path=config_path)
        assert url == "http://my-firefly.local"

    def test_no_prompt_when_config_has_valid_url(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": "http://exists.local"}), encoding="utf-8")
        prompt_calls: list[str] = []
        load_firefly_url(config_path=config_path, prompt_fn=lambda msg: prompt_calls.append(msg) or "")  # type: ignore[func-returns-value]
        assert len(prompt_calls) == 0

    def test_returns_url_without_trailing_slash_from_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": "http://my-firefly.local/"}), encoding="utf-8")
        url = load_firefly_url(config_path=config_path)
        assert url == "http://my-firefly.local/"  # stored value is returned as-is


# ---------------------------------------------------------------------------
# load_firefly_url — interactive prompt when config is missing/empty
# ---------------------------------------------------------------------------


class TestLoadFireflyUrlInteractive:
    def test_prompts_when_config_missing(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        prompt_calls: list[str] = []

        def mock_prompt(msg: str) -> str:
            prompt_calls.append(msg)
            return "http://prompted.local"

        url = load_firefly_url(config_path=config_path, prompt_fn=mock_prompt, validate_fn=lambda u: True)
        assert url == "http://prompted.local"
        assert len(prompt_calls) == 1

    def test_prompts_when_url_empty_in_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": ""}), encoding="utf-8")
        prompt_calls: list[str] = []

        def mock_prompt(msg: str) -> str:
            prompt_calls.append(msg)
            return "http://prompted.local"

        url = load_firefly_url(config_path=config_path, prompt_fn=mock_prompt, validate_fn=lambda u: True)
        assert url == "http://prompted.local"
        assert len(prompt_calls) == 1

    def test_prompts_when_config_has_no_url_key(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"other_key": "value"}), encoding="utf-8")

        url = load_firefly_url(
            config_path=config_path,
            prompt_fn=lambda _: "http://new.local",
            validate_fn=lambda u: True,
        )
        assert url == "http://new.local"

    def test_strips_trailing_slash_from_prompted_url(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        url = load_firefly_url(
            config_path=config_path,
            prompt_fn=lambda _: "http://test.local/",
            validate_fn=lambda u: True,
        )
        assert url == "http://test.local"

    def test_saves_url_to_config_after_prompt(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        load_firefly_url(
            config_path=config_path,
            prompt_fn=lambda _: "http://saved.local",
            validate_fn=lambda u: True,
        )
        assert config_path.exists()
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["firefly_url"] == "http://saved.local"

    def test_retries_on_validation_failure(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        responses = iter(["http://bad.local", "http://good.local"])
        validate_calls: list[str] = []

        def mock_validate(url: str) -> bool:
            validate_calls.append(url)
            return url == "http://good.local"

        url = load_firefly_url(
            config_path=config_path,
            prompt_fn=lambda _: next(responses),
            validate_fn=mock_validate,
        )
        assert url == "http://good.local"
        assert len(validate_calls) == 2

    def test_skips_empty_prompt_input(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        responses = iter(["", "http://valid.local"])

        url = load_firefly_url(
            config_path=config_path,
            prompt_fn=lambda _: next(responses),
            validate_fn=lambda u: True,
        )
        assert url == "http://valid.local"


# ---------------------------------------------------------------------------
# load_firefly_url — --configure / force=True
# ---------------------------------------------------------------------------


class TestLoadFireflyUrlForce:
    def test_force_prompts_even_when_config_exists(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": "http://existing.local"}), encoding="utf-8")
        prompt_calls: list[str] = []

        def mock_prompt(msg: str) -> str:
            prompt_calls.append(msg)
            return "http://new.local"

        url = load_firefly_url(
            config_path=config_path,
            force=True,
            prompt_fn=mock_prompt,
            validate_fn=lambda u: True,
        )
        assert url == "http://new.local"
        assert len(prompt_calls) == 1

    def test_force_overwrites_existing_config(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps({"firefly_url": "http://old.local"}), encoding="utf-8")

        load_firefly_url(
            config_path=config_path,
            force=True,
            prompt_fn=lambda _: "http://updated.local",
            validate_fn=lambda u: True,
        )
        data = json.loads(config_path.read_text(encoding="utf-8"))
        assert data["firefly_url"] == "http://updated.local"


# ---------------------------------------------------------------------------
# load_api_token — reading from secrets.json
# ---------------------------------------------------------------------------


class TestLoadApiTokenFromSecrets:
    def test_reads_token_from_secrets_json(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"api_token": "my-secret-token"}), encoding="utf-8")
        token_path = tmp_path / "token"
        token = load_api_token(secrets_path=secrets_path, token_path=token_path)
        assert token == "my-secret-token"

    def test_no_prompt_when_secrets_has_token(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"api_token": "token-abc"}), encoding="utf-8")
        token_path = tmp_path / "token"
        prompt_calls: list[str] = []
        load_api_token(
            secrets_path=secrets_path,
            token_path=token_path,
            prompt_fn=lambda msg: prompt_calls.append(msg) or "",  # type: ignore[func-returns-value]
        )
        assert len(prompt_calls) == 0


# ---------------------------------------------------------------------------
# load_api_token — fallback to legacy token file
# ---------------------------------------------------------------------------


class TestLoadApiTokenFromLegacyFile:
    def test_falls_back_to_token_file_when_no_secrets(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        token_path = tmp_path / "token"
        token_path.write_text("legacy-token\n", encoding="utf-8")
        token = load_api_token(secrets_path=secrets_path, token_path=token_path)
        assert token == "legacy-token"

    def test_falls_back_when_secrets_has_no_api_token_key(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"other_key": "value"}), encoding="utf-8")
        token_path = tmp_path / "token"
        token_path.write_text("fallback-token", encoding="utf-8")
        token = load_api_token(secrets_path=secrets_path, token_path=token_path)
        assert token == "fallback-token"

    def test_falls_back_when_secrets_has_empty_token(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"api_token": ""}), encoding="utf-8")
        token_path = tmp_path / "token"
        token_path.write_text("fallback-token", encoding="utf-8")
        token = load_api_token(secrets_path=secrets_path, token_path=token_path)
        assert token == "fallback-token"


# ---------------------------------------------------------------------------
# load_api_token — interactive prompt
# ---------------------------------------------------------------------------


class TestLoadApiTokenInteractive:
    def test_prompts_when_neither_exists(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        token_path = tmp_path / "token"
        prompt_calls: list[str] = []

        def mock_prompt(msg: str) -> str:
            prompt_calls.append(msg)
            return "prompted-token"

        token = load_api_token(secrets_path=secrets_path, token_path=token_path, prompt_fn=mock_prompt)
        assert token == "prompted-token"
        assert len(prompt_calls) == 1

    def test_saves_token_to_secrets_after_prompt(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        token_path = tmp_path / "token"
        load_api_token(
            secrets_path=secrets_path,
            token_path=token_path,
            prompt_fn=lambda _: "saved-token",
        )
        assert secrets_path.exists()
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        assert data["api_token"] == "saved-token"


# ---------------------------------------------------------------------------
# load_api_token — force=True
# ---------------------------------------------------------------------------


class TestLoadApiTokenForce:
    def test_force_prompts_even_when_secrets_exist(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"api_token": "existing-token"}), encoding="utf-8")
        token_path = tmp_path / "token"
        prompt_calls: list[str] = []

        def mock_prompt(msg: str) -> str:
            prompt_calls.append(msg)
            return "new-token"

        token = load_api_token(
            secrets_path=secrets_path,
            token_path=token_path,
            force=True,
            prompt_fn=mock_prompt,
        )
        assert token == "new-token"
        assert len(prompt_calls) == 1

    def test_force_overwrites_secrets_file(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        secrets_path.write_text(json.dumps({"api_token": "old-token"}), encoding="utf-8")
        token_path = tmp_path / "token"

        load_api_token(
            secrets_path=secrets_path,
            token_path=token_path,
            force=True,
            prompt_fn=lambda _: "updated-token",
        )
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
        assert data["api_token"] == "updated-token"

    def test_force_ignores_token_file_fallback(self, tmp_path: Path) -> None:
        secrets_path = tmp_path / "secrets.json"
        token_path = tmp_path / "token"
        token_path.write_text("legacy-token", encoding="utf-8")

        token = load_api_token(
            secrets_path=secrets_path,
            token_path=token_path,
            force=True,
            prompt_fn=lambda _: "forced-token",
        )
        assert token == "forced-token"
