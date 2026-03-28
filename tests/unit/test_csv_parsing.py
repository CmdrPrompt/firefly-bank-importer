"""Characterisation tests for detect_csv_format() and _get_csv_indices().

Documents current behavior as-is.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import _get_csv_indices, detect_csv_format

SEB_REQUIRED = {"Bokföringsdatum", "Text", "Belopp"}
ICA_REQUIRED = {"Datum", "Text", "Typ", "Belopp"}


class TestDetectCsvFormatSEB:
    def test_minimal_seb_headers(self) -> None:
        assert detect_csv_format(["Bokföringsdatum", "Text", "Belopp"]) == "seb"

    def test_full_seb_headers(self) -> None:
        assert detect_csv_format(["Bokföringsdatum", "Valutadatum", "Text", "Belopp", "Saldo"]) == "seb"

    def test_seb_missing_one_required_returns_unknown(self) -> None:
        assert detect_csv_format(["Bokföringsdatum", "Text"]) == "unknown"

    def test_seb_missing_belopp_returns_unknown(self) -> None:
        assert detect_csv_format(["Bokföringsdatum", "Text", "Datum"]) == "unknown"


class TestDetectCsvFormatICA:
    def test_minimal_ica_headers(self) -> None:
        assert detect_csv_format(["Datum", "Text", "Typ", "Belopp"]) == "ica"

    def test_full_ica_headers(self) -> None:
        assert detect_csv_format(["Datum", "Text", "Typ", "Belopp", "Saldo"]) == "ica"

    def test_ica_missing_typ_returns_unknown(self) -> None:
        assert detect_csv_format(["Datum", "Text", "Belopp"]) == "unknown"

    def test_ica_missing_datum_returns_unknown(self) -> None:
        assert detect_csv_format(["Text", "Typ", "Belopp"]) == "unknown"


class TestDetectCsvFormatUnknown:
    def test_empty_headers(self) -> None:
        assert detect_csv_format([]) == "unknown"

    def test_unrelated_headers(self) -> None:
        assert detect_csv_format(["Foo", "Bar", "Baz"]) == "unknown"

    def test_case_sensitive_seb(self) -> None:
        # SURPRISING: matching is case-sensitive — lowercase fails
        assert detect_csv_format(["bokföringsdatum", "text", "belopp"]) == "unknown"

    def test_case_sensitive_ica(self) -> None:
        assert detect_csv_format(["datum", "text", "typ", "belopp"]) == "unknown"


class TestDetectCsvFormatHypothesis:
    @given(extra=st.lists(st.text(min_size=1, max_size=20), max_size=5))
    @settings(max_examples=200)
    def test_seb_headers_with_extra_columns_still_seb(self, extra: list[str]) -> None:
        headers = list(SEB_REQUIRED) + extra
        result = detect_csv_format(headers)
        assert result in (
            "seb",
            "ica",
        )  # extra cols might accidentally add ICA required set

    @given(headers=st.lists(st.text(min_size=1, max_size=20), min_size=0, max_size=10))
    @settings(max_examples=300)
    def test_random_headers_never_crash(self, headers: list[str]) -> None:
        result = detect_csv_format(headers)
        assert result in ("seb", "ica", "unknown")


class TestGetCsvIndicesSEB:
    def test_seb_returns_correct_indices(self) -> None:
        headers = ["Bokföringsdatum", "Valutadatum", "Text", "Belopp", "Saldo"]
        datum_idx, text_idx, belopp_idx, type_idx = _get_csv_indices("seb", headers)
        assert datum_idx == headers.index("Bokföringsdatum")
        assert text_idx == headers.index("Text")
        assert belopp_idx == headers.index("Belopp")
        assert type_idx is None

    def test_seb_type_idx_is_none(self) -> None:
        headers = ["Bokföringsdatum", "Text", "Belopp"]
        _, _, _, type_idx = _get_csv_indices("seb", headers)
        assert type_idx is None


class TestGetCsvIndicesICA:
    def test_ica_returns_correct_indices(self) -> None:
        headers = ["Datum", "Text", "Typ", "Belopp", "Saldo"]
        datum_idx, text_idx, belopp_idx, type_idx = _get_csv_indices("ica", headers)
        assert datum_idx == headers.index("Datum")
        assert text_idx == headers.index("Text")
        assert belopp_idx == headers.index("Belopp")
        assert type_idx == headers.index("Typ")

    def test_ica_type_idx_is_not_none(self) -> None:
        headers = ["Datum", "Text", "Typ", "Belopp"]
        _, _, _, type_idx = _get_csv_indices("ica", headers)
        assert type_idx is not None

    def test_ica_missing_column_raises(self) -> None:
        # ValueError from list.index() if column is missing
        with pytest.raises(ValueError):
            _get_csv_indices("ica", ["Datum", "Text", "Belopp"])  # "Typ" missing
