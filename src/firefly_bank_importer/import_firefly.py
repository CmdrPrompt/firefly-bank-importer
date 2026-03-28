import contextlib
import csv
import json
import logging
import re
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from typing import Any, TypedDict, cast

import requests

from firefly_bank_importer.config import load_api_token, load_firefly_url

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
ACCOUNT_CACHE_FILE = _PROJECT_ROOT / "accounts_cache.json"

MAX_WORKERS = 5
BLOCK_TRANSACTION_POSTS = False


class Account(TypedDict):
    id: int
    name: str
    type: str


PendingTransaction = tuple[str, str, str]


def setup_logging() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"import_{timestamp}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def fetch_accounts_from_firefly(session: requests.Session, firefly_url: str) -> list[Account]:
    accounts: list[Account] = []
    page = 1
    while True:
        response = session.get(
            f"{firefly_url}/api/v1/accounts",
            params={"type": "asset", "page": str(page)},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Konto-hämtning misslyckades: {response.status_code} {response.text[:100]}")
        data = cast(dict[str, Any], response.json())
        for item in data.get("data", []):
            accounts.append(
                {
                    "id": int(item["id"]),
                    "name": item["attributes"]["name"],
                    "type": item["attributes"].get("type", "asset"),
                }
            )
        pagination = data.get("meta", {}).get("pagination", {})
        if page >= pagination.get("total_pages", 1):
            break
        page += 1
    return accounts


def save_account_cache(accounts: list[Account]) -> None:
    cache = {
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "accounts": accounts,
    }
    Path(ACCOUNT_CACHE_FILE).write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info(f"Sparade {len(accounts)} konton i {ACCOUNT_CACHE_FILE}.")


def load_account_cache() -> list[Account] | None:
    cache_path = Path(ACCOUNT_CACHE_FILE)
    if not cache_path.exists():
        return None
    try:
        cache_data = cast(dict[str, Any], json.loads(cache_path.read_text(encoding="utf-8")))
        raw_accounts = cache_data.get("accounts", [])
        if not isinstance(raw_accounts, list):
            logging.error(f"Ogiltig cache-fil {ACCOUNT_CACHE_FILE}: accounts är inte en lista")
            return None

        accounts: list[Account] = []
        for item in raw_accounts:
            if not isinstance(item, dict):
                continue
            raw_id = item.get("id")
            raw_name = item.get("name")
            raw_type = item.get("type", "asset")
            if isinstance(raw_id, int) and isinstance(raw_name, str) and isinstance(raw_type, str):
                accounts.append({"id": raw_id, "name": raw_name, "type": raw_type})

        fetched_at = cache_data.get("fetched_at", "okänt")
        logging.info(f"Laddade {len(accounts)} konton från cache ({ACCOUNT_CACHE_FILE}, hämtad {fetched_at}).")
        return accounts
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Ogiltig cache-fil {ACCOUNT_CACHE_FILE}: {e}")
        return None


def build_account_map(
    session: requests.Session,
    firefly_url: str,
    refresh: bool = False,
) -> tuple[dict[str, int], list[Account]]:
    accounts: list[Account] | None = None
    if not refresh:
        accounts = load_account_cache()

    if accounts is None:
        logging.info("Hämtar konton från Firefly...")
        try:
            accounts = fetch_accounts_from_firefly(session, firefly_url)
            save_account_cache(accounts)
        except RuntimeError as e:
            logging.error(str(e))
            if not refresh:
                accounts = load_account_cache()
            if accounts is None:
                logging.error(
                    "Ingen cache tillgänglig och Firefly-anrop misslyckades. "
                    "Kör med --refresh-accounts när Firefly är nåbart."
                )
                sys.exit(1)

    return {a["name"]: a["id"] for a in accounts}, accounts


def sanitize_folder_name(name: str) -> str:
    name = name.replace("å", "a").replace("Å", "A")
    name = name.replace("ä", "a").replace("Ä", "A")
    name = name.replace("ö", "o").replace("Ö", "O")
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    name = name.replace(" ", "_")
    return name.strip("_")


def create_import_folders(base: Path, accounts: list[Account]) -> None:
    created = 0
    for account in accounts:
        folder_name = f"kontoutdrag_{sanitize_folder_name(account['name'])}"
        folder_path = base / folder_name
        if not folder_path.exists():
            folder_path.mkdir(parents=True)
            logging.info(f"  Skapade importmapp: {folder_name}")
            created += 1
    if created:
        logging.info(f"  {created} ny(a) importmapp(ar) skapades i {base}.")
    else:
        logging.info("  Inga nya importmappar behövde skapas.")


def find_account_id(folder_name: str, account_map: dict[str, int]) -> int | None:
    matches: list[tuple[str, int]] = []
    folder_key = folder_name
    if folder_key.startswith("kontoutdrag_"):
        folder_key = folder_key[len("kontoutdrag_") :]
    folder_lower = sanitize_folder_name(folder_key).lower()

    for name, account_id in account_map.items():
        account_lower = sanitize_folder_name(name).lower()
        if account_lower in folder_lower or folder_lower in account_lower:
            matches.append((name, account_id))
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0][1]
    matches.sort(key=lambda x: len(x[0]), reverse=True)
    logging.info(f"  Flera kontomatchningar för '{folder_name}': {[m[0] for m in matches]}. Väljer '{matches[0][0]}'.")
    return matches[0][1]


MONTHLY_FILE_RE = re.compile(r"^\d{4}-\d{2}\.csv$")


def split_file_in_place(input_file: Path) -> None:
    months: defaultdict[str, list[list[str]]] = defaultdict(list)

    with open(input_file, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

        csv_format = detect_csv_format(headers)
        if csv_format == "seb":
            datum_idx = headers.index("Bokföringsdatum")
        elif csv_format == "ica":
            datum_idx = headers.index("Datum")
        else:
            logging.warning(f"  Okänt format i {input_file.name}, hoppar över split.")
            return

        belopp_idx = headers.index("Belopp")
        saldo_idx = headers.index("Saldo") if "Saldo" in headers else None

        for row in reader:
            for idx in (belopp_idx, saldo_idx):
                if idx is None:
                    continue
                with contextlib.suppress(ValueError):
                    row[idx] = f"{parse_amount(row[idx]):.2f}"
            year_month = row[datum_idx][:7]
            months[year_month].append(row)

    for year_month, rows in sorted(months.items()):
        rows.sort(key=lambda row: row[datum_idx])
        output_file = input_file.parent / f"{year_month}.csv"
        with open(output_file, "w", encoding="utf-8", newline="") as f:
            csv.writer(f, delimiter=";").writerows([headers] + rows)
        logging.info(f"  Splittat: {output_file.name} ({len(rows)} rader)")

    if months:
        input_file.unlink()
        logging.info(f"  Tog bort ursprungsfil: {input_file.name}")


def auto_split_folder(folder: Path) -> None:
    to_split = [f for f in folder.glob("*.csv") if not MONTHLY_FILE_RE.match(f.name)]
    if to_split:
        logging.info(f"  Splittar {len(to_split)} icke-månadssplittad(e) fil(er)...")
        for f in sorted(to_split):
            split_file_in_place(f)


def get_latest_transaction_date(session: requests.Session, account_id: int, firefly_url: str) -> date | None:
    response = session.get(
        f"{firefly_url}/api/v1/accounts/{account_id}/transactions",
        params={"limit": 1, "page": 1},
    )

    if response.status_code != 200:
        logging.warning(f"Kunde inte hamta senaste transaktion for konto {account_id} ({response.status_code}).")
        return None

    data = cast(dict[str, Any], response.json()).get("data", [])
    if not data:
        return None

    tx_list = data[0].get("attributes", {}).get("transactions", [])
    if not tx_list:
        return None

    latest_date_str = tx_list[0]["date"][:10]
    return datetime.strptime(latest_date_str, "%Y-%m-%d").date()


def parse_amount(raw_amount: str) -> float:
    cleaned = raw_amount.strip()
    cleaned = re.sub(r"\s*(kr|sek)\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace(" ", "")
    cleaned = cleaned.replace(",", ".")
    return float(cleaned)


def detect_csv_format(headers: list[str]) -> str:
    header_set = set(headers)

    if {"Bokföringsdatum", "Text", "Belopp"}.issubset(header_set):
        return "seb"

    if {"Datum", "Text", "Typ", "Belopp"}.issubset(header_set):
        return "ica"

    return "unknown"


def _build_transaction_payload(date: str, description: str, amount: float, account_id: int) -> dict[str, str]:
    if amount < 0:
        return {
            "type": "withdrawal",
            "date": date,
            "amount": f"{abs(amount):.2f}",
            "description": description,
            "source_id": str(account_id),
            "currency_code": "SEK",
        }
    return {
        "type": "deposit",
        "date": date,
        "amount": f"{amount:.2f}",
        "description": description,
        "destination_id": str(account_id),
        "currency_code": "SEK",
    }


def _log_tx_result(
    response: requests.Response,
    transaction_type: str,
    amount_abs: float,
    date: str,
    description: str,
) -> bool:
    if response.status_code in (200, 201):
        logging.info(f"  [OK] [{transaction_type}] {amount_abs:.2f} SEK | {date} | {description}")
        return True
    logging.error(
        f"  [FEL] [{transaction_type}] {amount_abs:.2f} SEK | {date} | {description} -> {response.text[:100]}"
    )
    return False


def create_transaction(
    session: requests.Session,
    date: str,
    description: str,
    amount: str | float,
    account_id: int,
    firefly_url: str = "",
    dry_run: bool = False,
    log: bool = True,
) -> tuple[requests.Response, str, float] | None:
    parsed_amount = parse_amount(str(amount))
    payload = _build_transaction_payload(date, description, parsed_amount, account_id)
    transaction_type = payload["type"]
    amount_abs = abs(parsed_amount)

    if dry_run:
        logging.info(
            "  [DRY RUN] [%s] %.2f SEK | %s | %s",
            transaction_type,
            amount_abs,
            date,
            description,
        )
        return None

    if BLOCK_TRANSACTION_POSTS:
        raise RuntimeError("POST av transaktion blockerad eftersom dry-run-skydd är aktivt.")

    response = session.post(f"{firefly_url}/api/v1/transactions", json={"transactions": [payload]})

    if log:
        _log_tx_result(response, transaction_type, amount_abs, date, description)

    return response, transaction_type, amount_abs


def _get_csv_indices(csv_format: str, headers: list[str]) -> tuple[int, int, int, int | None]:
    if csv_format == "seb":
        return (
            headers.index("Bokföringsdatum"),
            headers.index("Text"),
            headers.index("Belopp"),
            None,
        )
    return (
        headers.index("Datum"),
        headers.index("Text"),
        headers.index("Belopp"),
        headers.index("Typ"),
    )


def _collect_pending_rows(
    reader: Any,
    datum_idx: int,
    text_idx: int,
    belopp_idx: int,
    type_idx: int | None,
    latest_date: date | None,
) -> tuple[list[PendingTransaction], int]:
    skipped = 0
    pending: list[PendingTransaction] = []
    for row in reader:
        row_date = datetime.strptime(row[datum_idx], "%Y-%m-%d").date()
        if latest_date is not None and row_date <= latest_date:
            skipped += 1
            continue
        description = row[text_idx].strip()
        if type_idx is not None:
            description = f"{description} [{row[type_idx].strip()}]"
        pending.append((row[datum_idx], description, row[belopp_idx]))
    return pending, skipped


def _run_threaded_import(
    session: requests.Session,
    pending: list[PendingTransaction],
    account_id: int,
    firefly_url: str,
) -> None:
    ok = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for batch_start in range(0, len(pending), MAX_WORKERS):
            batch = pending[batch_start : batch_start + MAX_WORKERS]
            futures = [
                executor.submit(
                    create_transaction,
                    session,
                    tx_date,
                    desc,
                    amount,
                    account_id,
                    firefly_url,
                    False,
                    log=False,
                )
                for tx_date, desc, amount in batch
            ]
            for fut, (tx_date, desc, _amount) in zip(futures, batch, strict=True):
                result = fut.result()
                if result is None:
                    errors += 1
                    continue
                response, transaction_type, amount_abs = result
                if _log_tx_result(response, transaction_type, amount_abs, tx_date, desc):
                    ok += 1
                else:
                    errors += 1
    logging.info(f"  Summa: {ok} ok, {errors} fel")


def process_csv(
    session: requests.Session,
    csv_path: Path,
    account_id: int,
    firefly_url: str,
    dry_run: bool = False,
    latest_date: date | None = None,
) -> None:
    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)

        csv_format = detect_csv_format(headers)
        if csv_format == "unknown":
            logging.error(f"Okant CSV-format i {csv_path.name}. Hittade headers: {headers}")
            return

        datum_idx, text_idx, belopp_idx, type_idx = _get_csv_indices(csv_format, headers)
        logging.info(f"  Format: {csv_format.upper()}")
        if latest_date is not None:
            logging.info(f"  Senaste i Firefly: {latest_date} (hoppar over <= detta datum)")

        pending, skipped = _collect_pending_rows(reader, datum_idx, text_idx, belopp_idx, type_idx, latest_date)

    if dry_run:
        for date, description, amount in pending:
            create_transaction(session, date, description, amount, account_id, firefly_url, dry_run=True)
        logging.info(f"  Summa: {len(pending)} transaktioner")
    else:
        _run_threaded_import(session, pending, account_id, firefly_url)

    if skipped:
        logging.info(f"  Hoppade over: {skipped} rader")


def process_folder(
    session: requests.Session,
    folder: Path,
    account_map: dict[str, int],
    firefly_url: str,
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
) -> None:
    account_id = find_account_id(folder.name, account_map)
    if not account_id:
        logging.warning(f"Inget konto hittat för {folder.name}, hoppar över.")
        return

    auto_split_folder(folder)

    csv_files = sorted(folder.glob("*.csv"))
    if not csv_files:
        logging.warning(f"Inga CSV-filer i {folder.name}, hoppar över.")
        return

    latest_date = None
    if not ignore_latest_date_check:
        latest_date = get_latest_transaction_date(session, account_id, firefly_url)

    logging.info(f"Konto ID {account_id}: {folder.name}")
    if ignore_latest_date_check:
        logging.info("  Ignorerar senaste datum-kontroll.")
    elif latest_date is None:
        logging.info("  Ingen tidigare transaktion hittades i Firefly.")

    for csv_path in csv_files:
        logging.info(f"Bearbetar: {csv_path.name}")
        process_csv(session, csv_path, account_id, firefly_url, dry_run, latest_date)


def _parse_cli_args(argv: list[str]) -> tuple[str, bool, bool, bool, bool]:
    if len(argv) < 2:
        raise ValueError(
            "Användning: python3 import_firefly.py <sökväg> "
            "[--dry-run] [--ignore-latest-date-check] [--refresh-accounts] [--configure]"
        )

    dry_run = "--dry-run" in argv
    ignore_latest_date_check = "--ignore-latest-date-check" in argv
    refresh_accounts = "--refresh-accounts" in argv
    configure = "--configure" in argv

    try:
        folder = next(arg for arg in argv[1:] if not arg.startswith("--"))
    except StopIteration as exc:
        raise ValueError("Sökväg saknas. Ange en mapp före eller efter flaggor.") from exc

    return folder, dry_run, ignore_latest_date_check, refresh_accounts, configure


def main(
    base_folder: str | None = None,
    dry_run: bool = False,
    ignore_latest_date_check: bool = False,
    refresh_accounts: bool = False,
    configure: bool = False,
) -> int:
    global BLOCK_TRANSACTION_POSTS

    if base_folder is None:
        try:
            (
                base_folder,
                dry_run,
                ignore_latest_date_check,
                refresh_accounts,
                configure,
            ) = _parse_cli_args(sys.argv)
        except ValueError as exc:
            print(str(exc))
            return 1

    BLOCK_TRANSACTION_POSTS = dry_run

    log_file = setup_logging()

    token = load_api_token(force=configure)
    firefly_url = load_firefly_url(force=configure)

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )

    base = Path(base_folder)
    account_map, accounts = build_account_map(session, firefly_url, refresh=refresh_accounts)

    if any(base.glob("*.csv")):
        folders = [base]
    else:
        logging.info("Säkerställer importmappar för alla konton...")
        create_import_folders(base, accounts)
        folders = sorted([f for f in base.iterdir() if f.is_dir()])

    if not folders:
        logging.error("Inga mappar hittades.")
        return 1

    if dry_run:
        logging.info("=== DRY RUN -- inga transaktioner skapas ===")

    logging.info(f"Hittade {len(folders)} kontomapp(ar).")
    logging.info(f"Loggar till: {log_file}")

    for folder in folders:
        process_folder(session, folder, account_map, firefly_url, dry_run, ignore_latest_date_check)

    logging.info("Klar!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
