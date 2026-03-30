from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True)
class ColumnMapping:
    date_idx: int
    description_idx: int
    amount_idx: int
    transaction_type_idx: int | None = None
    balance_idx: int | None = None


class BankFormat(Protocol):
    name: str

    def matches(self, headers: list[str]) -> bool: ...

    def build_column_mapping(self, headers: list[str]) -> ColumnMapping: ...

    def normalise_date(self, raw: str) -> str: ...


@dataclass(frozen=True)
class HeaderBankFormat:
    name: str
    required_headers: frozenset[str]
    date_header: str
    description_header: str
    amount_header: str
    transaction_type_header: str | None = None
    balance_header: str | None = None
    date_format: str = field(default="%Y-%m-%d")

    def matches(self, headers: list[str]) -> bool:
        return self.required_headers.issubset(set(headers))

    def normalise_date(self, raw: str) -> str:
        """Convert a raw date string to ISO 8601 (YYYY-MM-DD).

        If parsing with the bank's own date_format fails, falls back to
        ISO 8601 (%Y-%m-%d) so that already-normalised dates (e.g. from
        split output files) are returned unchanged.
        """
        cleaned = raw.strip()
        try:
            return datetime.strptime(cleaned, self.date_format).strftime("%Y-%m-%d")
        except ValueError:
            return datetime.strptime(cleaned, "%Y-%m-%d").strftime("%Y-%m-%d")

    def build_column_mapping(self, headers: list[str]) -> ColumnMapping:
        def _optional_index(header: str | None) -> int | None:
            if header is None or header not in headers:
                return None
            return headers.index(header)

        return ColumnMapping(
            date_idx=headers.index(self.date_header),
            description_idx=headers.index(self.description_header),
            amount_idx=headers.index(self.amount_header),
            transaction_type_idx=_optional_index(self.transaction_type_header),
            balance_idx=_optional_index(self.balance_header),
        )
