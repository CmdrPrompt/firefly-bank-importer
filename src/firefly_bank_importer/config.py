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

import requests

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

CONFIG_FILE = _PROJECT_ROOT / "config.json"
SECRETS_FILE = _PROJECT_ROOT / "secrets.json"
TOKEN_FILE = _PROJECT_ROOT / "token"


def validate_firefly_url(
    url: str,
    *,
    get_fn: Callable[..., requests.Response] = requests.get,
) -> bool:
    """Return True if *url* hosts a reachable Firefly III instance.

    Calls ``/api/v1/about`` and returns True when the response is HTTP 200.
    Returns False on any non-200 status or network error.
    """
    try:
        response = get_fn(f"{url}/api/v1/about", timeout=10)
        return bool(response.status_code == 200)
    except requests.RequestException:
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
    if not force and config_path.exists():
        try:
            data: dict[str, object] = json.loads(config_path.read_text(encoding="utf-8"))
            url_raw = data.get("firefly_url", "")
            url = str(url_raw).strip() if url_raw else ""
            if url:
                return url
        except (json.JSONDecodeError, KeyError):
            pass

    while True:
        raw = prompt_fn("Ange Firefly III URL (t.ex. http://truenas.local:30105): ").strip()
        if not raw:
            continue
        url = raw.rstrip("/")
        if validate_fn is not None:
            logging.info("Validerar URL %s...", url)
            if validate_fn(url):
                logging.info("URL validerad.")
                break
            logging.warning("Validering misslyckades. Försök igen.")
        else:
            break

    config: dict[str, object] = {}
    if config_path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            config = json.loads(config_path.read_text(encoding="utf-8"))
    config["firefly_url"] = url
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Sparade URL till %s.", config_path)
    return url


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
    if token_path is None:
        token_path = TOKEN_FILE

    if not force:
        if secrets_path.exists():
            try:
                data = json.loads(secrets_path.read_text(encoding="utf-8"))
                token = str(data.get("api_token", "")).strip()
                if token:
                    return token
            except (json.JSONDecodeError, KeyError):
                pass

        if token_path.exists():
            token = token_path.read_text(encoding="utf-8").strip()
            if token:
                return token

    token = prompt_fn("Ange Firefly III API-token: ").strip()

    secrets: dict[str, object] = {}
    if secrets_path.exists():
        with contextlib.suppress(json.JSONDecodeError):
            secrets = json.loads(secrets_path.read_text(encoding="utf-8"))
    secrets["api_token"] = token
    secrets_path.write_text(json.dumps(secrets, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Sparade token till %s.", secrets_path)
    return token
