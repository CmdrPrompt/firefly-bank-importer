"""Configuration loading for Firefly Bank Importer.

Handles reading the Firefly III base URL from config.json and the API token
from secrets.json, with interactive prompts on first run and a legacy fallback
to the plain ``token`` file.
"""

import contextlib
import getpass
import json
import logging
from collections.abc import Callable
from pathlib import Path

from firefly_python_api import FireflyClient, FireflyConnectionError

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_FILE = _PROJECT_ROOT / "config.json"
SECRETS_FILE = _PROJECT_ROOT / "secrets.json"
TOKEN_FILE = _PROJECT_ROOT / "token"


def validate_firefly_url(url: str) -> bool:
    """Return True if *url* hosts a reachable Firefly III instance.

    Delegates to FireflyClient.validate_connection() via GET /api/v1/about.
    Returns False on any network error or non-2xx response.
    """
    try:
        result: bool = FireflyClient(url, "").validate_connection()
        return result
    except FireflyConnectionError:
        return False


def load_firefly_url(
    config_path: Path = CONFIG_FILE,
    *,
    force: bool = False,
    prompt_fn: Callable[[str], str] = input,
    validate_fn: Callable[[str], bool] | None = None,
) -> str:
    """Return the Firefly III base URL, prompting and saving when needed.

    Resolution order:
    1. If *force* is False, try reading from *config_path*.
    2. If not found or *force* is True, prompt the user interactively.
    3. If *validate_fn* is provided, keep prompting until validation succeeds.
    4. Save the URL to *config_path* and return it.

    The stored URL is returned as-is (no trailing-slash stripping on read).
    Trailing slashes are stripped only from interactively entered values.
    """
    if not force:
        existing_url = _read_url_from_config(config_path)
        if existing_url:
            return existing_url

    url = _prompt_firefly_url(prompt_fn=prompt_fn, validate_fn=validate_fn)
    _save_firefly_url(config_path, url)
    return url


def _read_url_from_config(config_path: Path) -> str:
    if not config_path.exists():
        return ""

    try:
        data: dict[str, object] = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""

    url_raw = data.get("firefly_url", "")
    return str(url_raw).strip() if url_raw else ""


def _prompt_firefly_url(
    *,
    prompt_fn: Callable[[str], str],
    validate_fn: Callable[[str], bool] | None,
) -> str:
    while True:
        raw = prompt_fn("Ange Firefly III URL (t.ex. http://truenas.local:30105): ").strip()
        if not raw:
            continue

        url = raw.rstrip("/")
        if not _is_url_valid(url, validate_fn):
            continue
        return url


def _is_url_valid(url: str, validate_fn: Callable[[str], bool] | None) -> bool:
    if validate_fn is None:
        return True

    logging.info("Validerar URL %s...", url)
    if validate_fn(url):
        logging.info("URL validerad.")
        return True

    logging.warning("Validering misslyckades. Försök igen.")
    return False


def _save_firefly_url(config_path: Path, url: str) -> None:
    config: dict[str, object] = {}
    if config_path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            config = json.loads(config_path.read_text(encoding="utf-8"))

    config["firefly_url"] = url
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Sparade URL till %s.", config_path)


def load_api_token(
    secrets_path: Path = SECRETS_FILE,
    token_path: Path | None = None,
    *,
    force: bool = False,
    prompt_fn: Callable[[str], str] = getpass.getpass,
) -> str:
    """Return the Firefly III API token, prompting and saving when needed.

    Resolution order:
    1. If *force* is False, try ``secrets_path`` (``secrets.json``).
    2. If not found, fall back to the legacy plain *token_path* file.
    3. If neither exists (or *force* is True), prompt using hidden input.
    4. Save the token to *secrets_path* and return it.
    """
    token_path = token_path or TOKEN_FILE

    if not force:
        existing_token = _read_token_from_paths(secrets_path=secrets_path, token_path=token_path)
        if existing_token:
            return existing_token

    token = prompt_fn("Ange Firefly III API-token: ").strip()
    _save_api_token(secrets_path, token)
    return token


def _read_token_from_paths(*, secrets_path: Path, token_path: Path) -> str:
    token_from_secrets = _read_token_from_secrets(secrets_path)
    if token_from_secrets:
        return token_from_secrets

    if not token_path.exists():
        return ""
    return token_path.read_text(encoding="utf-8").strip()


def _read_token_from_secrets(secrets_path: Path) -> str:
    if not secrets_path.exists():
        return ""

    try:
        data = json.loads(secrets_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""

    return str(data.get("api_token", "")).strip()


def _save_api_token(secrets_path: Path, token: str) -> None:

    secrets: dict[str, object] = {}
    if secrets_path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    secrets["api_token"] = token
    secrets_path.write_text(json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Sparade token till %s.", secrets_path)
