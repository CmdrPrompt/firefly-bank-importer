import logging
import sys

from firefly_python_api import FireflyClient

from firefly_bank_importer.config import load_api_token, load_firefly_url
from firefly_bank_importer.import_firefly import Account, build_account_map, setup_logging

CONFIRMATION_PHRASE = "JA"


def resolve_target_accounts(accounts: list[Account], account_names: list[str] | None) -> list[Account]:
    if account_names is None:
        return accounts

    by_name = {a["name"]: a for a in accounts}
    resolved: list[Account] = []
    missing: list[str] = []
    for name in account_names:
        account = by_name.get(name)
        if account is None:
            missing.append(name)
        else:
            resolved.append(account)

    if missing:
        raise ValueError(f"Okänt/okända kontonamn: {', '.join(missing)}")

    return resolved


def collect_transactions_by_account(client: FireflyClient, accounts: list[Account]) -> dict[str, list[str]]:
    return {account["name"]: client.get_transactions_for_account(str(account["id"])) for account in accounts}


def log_summary(transactions_by_account: dict[str, list[str]]) -> int:
    total = 0
    for name, ids in transactions_by_account.items():
        logging.info(f"  {name}: {len(ids)} transaktion(er)")
        total += len(ids)
    logging.info(f"Totalt: {total} transaktion(er) skulle raderas.")
    return total


def confirm_deletion() -> bool:
    answer = input(f'Skriv "{CONFIRMATION_PHRASE}" för att bekräfta radering: ')
    return answer.strip() == CONFIRMATION_PHRASE


def delete_transactions(client: FireflyClient, transactions_by_account: dict[str, list[str]]) -> dict[str, int]:
    deleted_counts: dict[str, int] = {}
    for name, ids in transactions_by_account.items():
        for tx_id in ids:
            client.delete_transaction(tx_id)
        deleted_counts[name] = len(ids)
        logging.info(f"  {name}: {len(ids)} transaktion(er) raderade.")

    logging.info(f"Klart. Totalt {sum(deleted_counts.values())} transaktion(er) raderade.")
    return deleted_counts


def _parse_cli_args(argv: list[str]) -> tuple[list[str] | None, bool]:
    dry_run = "--dry-run" in argv
    has_all = "--all" in argv
    has_accounts = "--accounts" in argv

    if has_all and has_accounts:
        raise ValueError("Ange antingen --all eller --accounts, inte båda.")

    if has_all:
        return None, dry_run

    if has_accounts:
        idx = argv.index("--accounts")
        raw_value = argv[idx + 1] if idx + 1 < len(argv) else ""
        names = [n.strip() for n in raw_value.split(",") if n.strip()]
        if not names:
            raise ValueError("--accounts kräver en kommaseparerad lista på kontonamn.")
        return names, dry_run

    raise ValueError("Användning: python3 clear_transactions.py (--all | --accounts <namn1,namn2,...>) [--dry-run]")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv

    try:
        account_names, dry_run = _parse_cli_args(argv)
    except ValueError as exc:
        print(str(exc))
        return 1

    setup_logging()

    token = load_api_token()
    firefly_url = load_firefly_url()
    client = FireflyClient(firefly_url, token)

    _, accounts = build_account_map(client)

    try:
        targets = resolve_target_accounts(accounts, account_names)
    except ValueError as exc:
        logging.error(str(exc))
        return 1

    if not targets:
        logging.info("Inga konton matchade urvalet.")
        return 0

    logging.info(f"Hämtar transaktioner för {len(targets)} konto(n)...")
    transactions_by_account = collect_transactions_by_account(client, targets)
    total = log_summary(transactions_by_account)

    if total == 0:
        logging.info("Inga transaktioner att radera.")
        return 0

    if dry_run:
        logging.info("=== DRY RUN -- inga transaktioner raderas ===")
        return 0

    if not confirm_deletion():
        logging.info("Avbrutet av användaren. Inga transaktioner raderades.")
        return 0

    delete_transactions(client, transactions_by_account)
    return 0


if __name__ == "__main__":
    sys.exit(main())
