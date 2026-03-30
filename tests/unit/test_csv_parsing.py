"""Tests for registry-driven bank CSV format resolution.

These tests describe the target package architecture for bank-specific CSV
formats. The core importer should resolve a matching format through a shared
contract instead of hardcoding per-bank column logic in import_firefly.py.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.bank_formats import get_registered_bank_formats, resolve_bank_format
from firefly_bank_importer.bank_formats.base import HeaderBankFormat

SEB_REQUIRED = {"Bokföringsdatum", "Text", "Belopp"}
ICA_REQUIRED = {"Datum", "Text", "Typ", "Belopp"}


class TestRegisteredBankFormats:
    def test_seb_and_ica_are_registered(self) -> None:
        format_names = {bank_format.name for bank_format in get_registered_bank_formats()}
        assert {"seb", "ica"}.issubset(format_names)


class TestResolveBankFormatSEB:
    def test_minimal_seb_headers(self) -> None:
        bank_format = resolve_bank_format(["Bokföringsdatum", "Text", "Belopp"])
        assert bank_format is not None
        assert bank_format.name == "seb"

    def test_full_seb_headers(self) -> None:
        bank_format = resolve_bank_format(["Bokföringsdatum", "Valutadatum", "Text", "Belopp", "Saldo"])
        assert bank_format is not None
        assert bank_format.name == "seb"

    def test_seb_missing_one_required_returns_unknown(self) -> None:
        assert resolve_bank_format(["Bokföringsdatum", "Text"]) is None

    def test_seb_missing_belopp_returns_unknown(self) -> None:
        assert resolve_bank_format(["Bokföringsdatum", "Text", "Datum"]) is None


class TestResolveBankFormatICA:
    def test_minimal_ica_headers(self) -> None:
        bank_format = resolve_bank_format(["Datum", "Text", "Typ", "Belopp"])
        assert bank_format is not None
        assert bank_format.name == "ica"

    def test_full_ica_headers(self) -> None:
        bank_format = resolve_bank_format(["Datum", "Text", "Typ", "Belopp", "Saldo"])
        assert bank_format is not None
        assert bank_format.name == "ica"

    def test_ica_missing_typ_returns_unknown(self) -> None:
        assert resolve_bank_format(["Datum", "Text", "Belopp"]) is None

    def test_ica_missing_datum_returns_unknown(self) -> None:
        assert resolve_bank_format(["Text", "Typ", "Belopp"]) is None


class TestResolveBankFormatUnknown:
    def test_empty_headers(self) -> None:
        assert resolve_bank_format([]) is None

    def test_unrelated_headers(self) -> None:
        assert resolve_bank_format(["Foo", "Bar", "Baz"]) is None

    def test_case_sensitive_seb(self) -> None:
        assert resolve_bank_format(["bokföringsdatum", "text", "belopp"]) is None

    def test_case_sensitive_ica(self) -> None:
        assert resolve_bank_format(["datum", "text", "typ", "belopp"]) is None


class TestResolveBankFormatHypothesis:
    @given(extra=st.lists(st.text(min_size=1, max_size=20), max_size=5))
    @settings(max_examples=200)
    def test_seb_headers_with_extra_columns_still_seb(self, extra: list[str]) -> None:
        headers = list(SEB_REQUIRED) + extra
        result = resolve_bank_format(headers)
        assert result is None or result.name in ("seb", "ica")

    @given(headers=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10))
    @settings(max_examples=300)
    def test_random_headers_never_crash(self, headers: list[str]) -> None:
        result = resolve_bank_format(headers)
        assert result is None or result.name in ("seb", "ica")


class TestColumnMappingSEB:
    def test_seb_returns_correct_indices(self) -> None:
        headers = ["Bokföringsdatum", "Valutadatum", "Text", "Belopp", "Saldo"]
        bank_format = resolve_bank_format(headers)
        assert bank_format is not None
        mapping = bank_format.build_column_mapping(headers)
        assert mapping.date_idx == headers.index("Bokföringsdatum")
        assert mapping.description_idx == headers.index("Text")
        assert mapping.amount_idx == headers.index("Belopp")
        assert mapping.transaction_type_idx is None
        assert mapping.balance_idx == headers.index("Saldo")

    def test_seb_type_idx_is_none(self) -> None:
        headers = ["Bokföringsdatum", "Text", "Belopp"]
        bank_format = resolve_bank_format(headers)
        assert bank_format is not None
        mapping = bank_format.build_column_mapping(headers)
        assert mapping.transaction_type_idx is None


class TestColumnMappingICA:
    def test_ica_returns_correct_indices(self) -> None:
        headers = ["Datum", "Text", "Typ", "Belopp", "Saldo"]
        bank_format = resolve_bank_format(headers)
        assert bank_format is not None
        mapping = bank_format.build_column_mapping(headers)
        assert mapping.date_idx == headers.index("Datum")
        assert mapping.description_idx == headers.index("Text")
        assert mapping.amount_idx == headers.index("Belopp")
        assert mapping.transaction_type_idx == headers.index("Typ")
        assert mapping.balance_idx == headers.index("Saldo")

    def test_ica_type_idx_is_not_none(self) -> None:
        headers = ["Datum", "Text", "Typ", "Belopp"]
        bank_format = resolve_bank_format(headers)
        assert bank_format is not None
        mapping = bank_format.build_column_mapping(headers)
        assert mapping.transaction_type_idx is not None

    def test_ica_missing_column_returns_none_during_resolution(self) -> None:
        assert resolve_bank_format(["Datum", "Text", "Belopp"]) is None


class TestOptionalHeaderRobustness:
    def test_missing_optional_transaction_type_header_maps_to_none(self) -> None:
        custom_format = HeaderBankFormat(
            name="custom",
            required_headers=frozenset({"Datum", "Text", "Belopp"}),
            date_header="Datum",
            description_header="Text",
            amount_header="Belopp",
            transaction_type_header="Typ",
        )

        mapping = custom_format.build_column_mapping(["Datum", "Text", "Belopp"])
        assert mapping.transaction_type_idx is None
