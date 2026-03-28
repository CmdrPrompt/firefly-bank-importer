"""Characterisation tests for parse_amount().

Documents current behavior as-is. Surprising behaviors noted with SURPRISING comments.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import parse_amount


class TestParseAmountKnownFormats:
    def test_swedish_decimal_comma(self) -> None:
        assert parse_amount("100,50") == pytest.approx(100.50)

    def test_negative_swedish_decimal_comma(self) -> None:
        assert parse_amount("-200,00") == pytest.approx(-200.0)

    def test_dot_decimal(self) -> None:
        assert parse_amount("100.50") == pytest.approx(100.50)

    def test_negative_dot_decimal(self) -> None:
        assert parse_amount("-200.00") == pytest.approx(-200.0)

    def test_integer_string(self) -> None:
        assert parse_amount("500") == pytest.approx(500.0)

    def test_negative_integer_string(self) -> None:
        assert parse_amount("-500") == pytest.approx(-500.0)

    def test_zero(self) -> None:
        assert parse_amount("0") == pytest.approx(0.0)

    def test_trailing_kr_lowercase(self) -> None:
        assert parse_amount("100.50 kr") == pytest.approx(100.50)

    def test_trailing_kr_uppercase(self) -> None:
        assert parse_amount("100.50 KR") == pytest.approx(100.50)

    def test_trailing_sek_lowercase(self) -> None:
        assert parse_amount("100.50 sek") == pytest.approx(100.50)

    def test_trailing_sek_uppercase(self) -> None:
        assert parse_amount("100.50 SEK") == pytest.approx(100.50)

    def test_whitespace_stripped(self) -> None:
        assert parse_amount("  100,50  ") == pytest.approx(100.50)

    def test_thousands_space_separator(self) -> None:
        # Swedish format: "1 000,50" — spaces between thousands
        assert parse_amount("1 000,50") == pytest.approx(1000.50)

    def test_large_negative_with_space_separator(self) -> None:
        assert parse_amount("-1 500,00") == pytest.approx(-1500.0)


class TestParseAmountEdgeCases:
    def test_empty_string_raises(self) -> None:
        # SURPRISING: no explicit validation — raises ValueError from float()
        with pytest.raises(ValueError):
            parse_amount("")

    def test_non_numeric_raises(self) -> None:
        # SURPRISING: passes through silently unless float() fails
        with pytest.raises(ValueError):
            parse_amount("abc")

    def test_kr_only_raises(self) -> None:
        # After stripping "kr", remaining "" causes ValueError
        with pytest.raises(ValueError):
            parse_amount("kr")


class TestParseAmountHypothesis:
    @given(
        whole=st.integers(min_value=-999_999, max_value=999_999),
        frac=st.integers(min_value=0, max_value=99),
    )
    @settings(max_examples=200)
    def test_dot_decimal_roundtrip(self, whole: int, frac: int) -> None:
        raw = f"{whole}.{frac:02d}"
        result = parse_amount(raw)
        expected = float(f"{whole}.{frac:02d}")
        assert result == pytest.approx(expected)

    @given(
        whole=st.integers(min_value=-999_999, max_value=999_999),
        frac=st.integers(min_value=0, max_value=99),
    )
    @settings(max_examples=200)
    def test_comma_decimal_roundtrip(self, whole: int, frac: int) -> None:
        raw = f"{whole},{frac:02d}"
        result = parse_amount(raw)
        expected = float(f"{whole}.{frac:02d}")
        assert result == pytest.approx(expected)

    @given(value=st.floats(min_value=-999_999, max_value=999_999, allow_nan=False, allow_infinity=False))
    @settings(max_examples=200)
    def test_float_formatted_as_dot_string_roundtrip(self, value: float) -> None:
        raw = f"{value:.2f}"
        result = parse_amount(raw)
        # Compare against the rounded representation, not the original float
        assert result == pytest.approx(float(raw), rel=1e-5)
