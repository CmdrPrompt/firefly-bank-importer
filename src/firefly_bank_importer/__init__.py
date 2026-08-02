"""firefly_bank_importer: CLI tool and importable service layer (FR-73).

Re-exports the stable, documented public service-layer surface from
`firefly_bank_importer.service` so external applications can import it
directly from the top-level package. See
`docs/SERVICE_LAYER_INTERFACE.md` for the full interface guide.
"""

from firefly_bank_importer.service import (
    Account,
    FolderResult,
    OpeningBalanceResult,
    PendingRow,
    ProgressEvent,
    TransactionResult,
    TransactionStatus,
    TransferDetectionSummary,
    TransferResult,
    apply_auto_opening_balance,
    create_transaction,
    fetch_accounts_from_firefly,
    post_transfer,
    run_multi_folder_import,
)

__all__ = [
    "Account",
    "FolderResult",
    "OpeningBalanceResult",
    "PendingRow",
    "ProgressEvent",
    "TransactionResult",
    "TransactionStatus",
    "TransferDetectionSummary",
    "TransferResult",
    "apply_auto_opening_balance",
    "create_transaction",
    "fetch_accounts_from_firefly",
    "post_transfer",
    "run_multi_folder_import",
]
