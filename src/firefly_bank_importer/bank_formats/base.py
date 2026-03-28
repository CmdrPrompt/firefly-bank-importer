from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(frozen=True)
class HeaderBankFormat:
    name: str
    required_headers: frozenset[str]
    date_header: str
    description_header: str
    amount_header: str
    transaction_type_header: str | None = None
    balance_header: str | None = None

    def matches(self, headers: list[str]) -> bool:
        return self.required_headers.issubset(set(headers))

    def build_column_mapping(self, headers: list[str]) -> ColumnMapping:
        return ColumnMapping(
            date_idx=headers.index(self.date_header),
            description_idx=headers.index(self.description_header),
            amount_idx=headers.index(self.amount_header),
            transaction_type_idx=headers.index(self.transaction_type_header)
            if self.transaction_type_header is not None
            else None,
            balance_idx=headers.index(self.balance_header) if self.balance_header in headers else None,
        )
