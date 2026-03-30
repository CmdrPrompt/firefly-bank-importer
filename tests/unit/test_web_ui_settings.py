"""Tests for web UI settings endpoints — TASK-021.

Covers FR-37, FR-38, FR-39, FR-40 (UC-15).

TDD cycle: tests written before implementation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from firefly_bank_importer.web_ui import create_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_client(tmp_path: Path) -> TestClient:
    import_base = tmp_path / "bankImports"
    import_base.mkdir()
    app = create_app(base_folder=import_base)
    return TestClient(app, raise_server_exceptions=True)


# ---------------------------------------------------------------------------
# GET /settings — FR-37
# ---------------------------------------------------------------------------


class TestGetSettings:
    def test_returns_200(self, tmp_path: Path) -> None:
        client = make_client(tmp_path)
        response = client.get("/settings")
        assert response.status_code == 200

    def test_returns_url_when_config_exists(self, tmp_path: Path) -> None:
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"firefly_url": "http://firefly.local"}), encoding="utf-8")

        with patch("firefly_bank_importer.web_ui.CONFIG_FILE", config):
            client = make_client(tmp_path)
            response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["firefly_url"] == "http://firefly.local"

    def test_returns_none_url_when_config_missing(self, tmp_path: Path) -> None:
        with patch("firefly_bank_importer.web_ui.CONFIG_FILE", tmp_path / "config.json"):
            client = make_client(tmp_path)
            response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["firefly_url"] is None

    def test_token_exists_true_when_secrets_present(self, tmp_path: Path) -> None:
        secrets = tmp_path / "secrets.json"
        secrets.write_text(json.dumps({"api_token": "sometoken"}), encoding="utf-8")
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"firefly_url": "http://firefly.local"}), encoding="utf-8")

        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", config),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", secrets),
        ):
            client = make_client(tmp_path)
            response = client.get("/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["token_exists"] is True

    def test_token_exists_false_when_secrets_missing(self, tmp_path: Path) -> None:
        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", tmp_path / "config.json"),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", tmp_path / "secrets.json"),
            patch("firefly_bank_importer.web_ui.TOKEN_FILE", tmp_path / "token"),
        ):
            client = make_client(tmp_path)
            response = client.get("/settings")

        assert response.status_code == 200
        assert response.json()["token_exists"] is False

    def test_does_not_return_token_value(self, tmp_path: Path) -> None:
        """Token secret must never be returned in the API response."""
        secrets = tmp_path / "secrets.json"
        secrets.write_text(json.dumps({"api_token": "secretvalue"}), encoding="utf-8")

        with patch("firefly_bank_importer.web_ui.SECRETS_FILE", secrets):
            client = make_client(tmp_path)
            response = client.get("/settings")

        body = response.text
        assert "secretvalue" not in body


# ---------------------------------------------------------------------------
# POST /api/settings — FR-38, FR-39, FR-40
# ---------------------------------------------------------------------------


class TestPostSettings:
    def _post(
        self,
        client: TestClient,
        url: str,
        token: str,
    ) -> Any:
        return client.post(
            "/api/settings",
            json={"firefly_url": url, "api_token": token},
        )

    def test_saves_url_and_token_on_valid_url(self, tmp_path: Path) -> None:
        config = tmp_path / "config.json"
        secrets = tmp_path / "secrets.json"

        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", config),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", secrets),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=True),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "http://firefly.local", "mytoken")

        assert response.status_code == 200
        assert response.json()["success"] is True
        assert json.loads(config.read_text())["firefly_url"] == "http://firefly.local"
        assert json.loads(secrets.read_text())["api_token"] == "mytoken"

    def test_does_not_persist_on_validation_failure(self, tmp_path: Path) -> None:
        """FR-39: If URL validation fails, no files are written."""
        config = tmp_path / "config.json"
        secrets = tmp_path / "secrets.json"

        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", config),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", secrets),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=False),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "http://bad.url", "mytoken")

        assert response.status_code == 422
        assert response.json()["detail"]["success"] is False
        assert not config.exists()
        assert not secrets.exists()

    def test_returns_error_message_on_validation_failure(self, tmp_path: Path) -> None:
        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", tmp_path / "config.json"),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", tmp_path / "secrets.json"),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=False),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "http://bad.url", "tok")

        assert "error" in response.json()["detail"]
        assert len(response.json()["detail"]["error"]) > 0

    def test_updates_existing_url_and_token(self, tmp_path: Path) -> None:
        """FR-40: Updates existing values on successful validation."""
        config = tmp_path / "config.json"
        secrets = tmp_path / "secrets.json"
        config.write_text(json.dumps({"firefly_url": "http://old.local"}), encoding="utf-8")
        secrets.write_text(json.dumps({"api_token": "oldtoken"}), encoding="utf-8")

        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", config),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", secrets),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=True),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "http://new.local", "newtoken")

        assert response.status_code == 200
        assert json.loads(config.read_text())["firefly_url"] == "http://new.local"
        assert json.loads(secrets.read_text())["api_token"] == "newtoken"

    def test_preserves_other_config_keys_on_update(self, tmp_path: Path) -> None:
        """Saving settings must not delete other existing config.json keys."""
        config = tmp_path / "config.json"
        config.write_text(json.dumps({"firefly_url": "http://old.local", "other_key": "preserved"}), encoding="utf-8")

        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", config),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", tmp_path / "secrets.json"),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=True),
        ):
            client = make_client(tmp_path)
            self._post(client, "http://new.local", "tok")

        saved = json.loads(config.read_text())
        assert saved["other_key"] == "preserved"

    def test_rejects_empty_url(self, tmp_path: Path) -> None:
        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", tmp_path / "config.json"),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", tmp_path / "secrets.json"),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=True),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "", "tok")

        assert response.status_code == 422
        assert response.json()["detail"]["success"] is False

    def test_rejects_empty_token(self, tmp_path: Path) -> None:
        with (
            patch("firefly_bank_importer.web_ui.CONFIG_FILE", tmp_path / "config.json"),
            patch("firefly_bank_importer.web_ui.SECRETS_FILE", tmp_path / "secrets.json"),
            patch("firefly_bank_importer.web_ui.validate_firefly_url", return_value=True),
        ):
            client = make_client(tmp_path)
            response = self._post(client, "http://firefly.local", "")

        assert response.status_code == 422
        assert response.json()["detail"]["success"] is False
