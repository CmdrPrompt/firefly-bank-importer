from typing import cast

from firefly_bank_importer.bank_formats.base import BankFormat, ColumnMapping
from firefly_bank_importer.bank_formats.ica import ICA_FORMAT
from firefly_bank_importer.bank_formats.seb import SEB_FORMAT

_REGISTERED_BANK_FORMATS = cast(tuple[BankFormat, ...], (SEB_FORMAT, ICA_FORMAT))


def get_registered_bank_formats() -> tuple[BankFormat, ...]:
    return _REGISTERED_BANK_FORMATS


def resolve_bank_format(headers: list[str]) -> BankFormat | None:
    for bank_format in _REGISTERED_BANK_FORMATS:
        if bank_format.matches(headers):
            return bank_format
    return None


__all__ = ["BankFormat", "ColumnMapping", "get_registered_bank_formats", "resolve_bank_format"]
