# firefly-bank-importer

I didn't quite like the built-in Firefly III import tool for several reasons, one of them being that it seemed very slow and probably very serial.

So, here's another import tool for importing bank transactions into Firefly III. This one is a Python CLI tool (and importable service layer) for importing bank transactions from CSV exports (currently SEB, ICA, and Nordea formats) into [Firefly III](https://www.firefly-iii.org/) via its REST API. See [`docs/SERVICE_LAYER_INTERFACE.md`](docs/SERVICE_LAYER_INTERFACE.md) for the stable, documented public interface external applications can import (`firefly_bank_importer.service`).

- Multi-threaded imports makes this faster than the original one
- Discovers asset accounts from Firefly and caches them locally
- Automatically prevents duplicate imports via latest-date filtering per account
- Automatically splits multi-month CSV exports into monthly files
- Dry-run mode, parallel posting, and timestamped log files

## Installation

Requires Python ≥ 3.11 and a running Firefly III instance.

```bash
git clone https://github.com/CmdrPrompt/firefly-bank-importer.git
cd firefly-bank-importer
uv sync
```

On first CLI run, configure your Firefly III URL and API token interactively.

## Usage

```text
uv run firefly-import <path> [--dry-run] [--ignore-latest-date-check] [--refresh-accounts]
```

| Argument | Description |
|---|---|
| `<path>` | Single account folder or base directory with account subfolders |
| `--dry-run` | Log planned transactions without posting to Firefly |
| `--ignore-latest-date-check` | Import all rows, including already-imported dates |
| `--refresh-accounts` | Re-fetch accounts from Firefly and recreate import folders |

On first run (or with `--refresh-accounts`), the tool discovers all Firefly asset accounts, caches them in `accounts_cache.json`, and creates matching import folders under `<path>`.

## Supported CSV Formats

| Format | Required Headers |
|---|---|
| SEB | `Bokföringsdatum`, `Text`, `Belopp` |
| ICA | `Datum`, `Text`, `Typ`, `Belopp` |
| Nordea | `Bokföringsdag`, `Belopp`, `Rubrik` |

## Development

```bash
uv sync && uv run pre-commit install
make lint && make test
```

## License

See [LICENSE](LICENSE).
