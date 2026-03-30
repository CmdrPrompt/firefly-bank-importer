# firefly-bank-importer

Python CLI tool and web UI for importing bank transactions from CSV exports (currently SEB and ICA formats) into [Firefly III](https://www.firefly-iii.org/) via its REST API.

- Discovers asset accounts from Firefly and caches them locally
- Prevents duplicate imports via latest-date filtering per account
- Automatically splits multi-month CSV exports into monthly files
- Dry-run mode, parallel posting, and timestamped log files
- Web UI for folder selection, dry-run preview, live import, CSV upload, and import history

## Installation

Requires Python ≥ 3.11 and a running Firefly III instance.

```bash
git clone https://github.com/CmdrPrompt/firefly-bank-importer.git
cd firefly-bank-importer
uv sync
```

On first run, configure your Firefly III URL and API token interactively — or via the web UI settings page.

## Usage

**Web UI** (recommended):

```bash
uv run firefly-web
```

Opens at `http://127.0.0.1:8000`. Use the UI to select folders, preview imports, upload CSV files, and view history.

**CLI**:

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

## Development

```bash
uv sync && uv run pre-commit install
make lint && make test
```

## License

See [LICENSE](LICENSE).
