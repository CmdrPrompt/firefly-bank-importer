"""Characterisation tests for sanitize_folder_name() and find_account_id()."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import find_account_id, sanitize_folder_name

RESERVED_CHARS = ["<", ">", ":", '"', "/", "\\", "|", "?", "*"]
SWEDISH_LETTERS = set("åäöÅÄÖ")


class TestSanitizeFolderNameSwedishChars:
    def test_a_ring_lower(self) -> None:
        assert sanitize_folder_name("å") == "a"

    def test_a_ring_upper(self) -> None:
        assert sanitize_folder_name("Å") == "A"

    def test_a_umlaut_lower(self) -> None:
        assert sanitize_folder_name("ä") == "a"

    def test_a_umlaut_upper(self) -> None:
        assert sanitize_folder_name("Ä") == "A"

    def test_o_umlaut_lower(self) -> None:
        assert sanitize_folder_name("ö") == "o"

    def test_o_umlaut_upper(self) -> None:
        assert sanitize_folder_name("Ö") == "O"

    def test_mixed_swedish_word(self) -> None:
        assert sanitize_folder_name("Räkningskonto") == "Rakningskonto"

    def test_all_swedish_chars(self) -> None:
        assert sanitize_folder_name("åäöÅÄÖ") == "aaoAAO"


class TestSanitizeFolderNameSpecialChars:
    @pytest.mark.parametrize("char", RESERVED_CHARS)
    def test_reserved_char_replaced_with_underscore(self, char: str) -> None:
        assert sanitize_folder_name(f"a{char}b") == "a_b"

    def test_space_replaced_with_underscore(self) -> None:
        assert sanitize_folder_name("SEB Lönekonto") == "SEB_Lonekonto"

    def test_control_char_at_start_stripped(self) -> None:
        # \x00 is replaced with _ by regex, then stripped as a leading underscore
        assert sanitize_folder_name("\x00foo") == "foo"

    def test_leading_underscore_stripped(self) -> None:
        assert sanitize_folder_name("_foo") == "foo"

    def test_trailing_underscore_stripped(self) -> None:
        assert sanitize_folder_name("foo_") == "foo"

    def test_plain_ascii_unchanged(self) -> None:
        assert sanitize_folder_name("SEB") == "SEB"

    def test_empty_string(self) -> None:
        assert sanitize_folder_name("") == ""


class TestSanitizeFolderNameHypothesis:
    @given(name=st.text(min_size=0, max_size=80))
    @settings(max_examples=500)
    def test_no_swedish_letters_in_output(self, name: str) -> None:
        result = sanitize_folder_name(name)
        for ch in SWEDISH_LETTERS:
            assert ch not in result

    @given(name=st.text(min_size=0, max_size=80))
    @settings(max_examples=500)
    def test_no_reserved_path_chars_in_output(self, name: str) -> None:
        result = sanitize_folder_name(name)
        for ch in RESERVED_CHARS:
            assert ch not in result

    @given(name=st.text(min_size=0, max_size=80))
    @settings(max_examples=500)
    def test_no_leading_or_trailing_underscore(self, name: str) -> None:
        result = sanitize_folder_name(name)
        assert not result.startswith("_")
        assert not result.endswith("_")

    @given(name=st.text(min_size=1, max_size=80))
    @settings(max_examples=500)
    def test_idempotent(self, name: str) -> None:
        once = sanitize_folder_name(name)
        twice = sanitize_folder_name(once)
        assert once == twice


class TestFindAccountIdNoMatch:
    def test_empty_account_map_returns_none(self) -> None:
        assert find_account_id("kontoutdrag_SEB_Lonekonto", {}) is None

    def test_no_matching_account_returns_none(self) -> None:
        account_map = {"Sparkonto": 1, "Buffertkonto": 2}
        assert find_account_id("kontoutdrag_Lonekonto", account_map) is None


class TestFindAccountIdSingleMatch:
    def test_exact_substring_match(self) -> None:
        account_map = {"SEB Lönekonto": 42}
        assert find_account_id("kontoutdrag_SEB_Lonekonto", account_map) == 42

    def test_kontoutdrag_prefix_stripped(self) -> None:
        account_map = {"Buffertkonto": 7}
        assert find_account_id("kontoutdrag_Buffertkonto", account_map) == 7

    def test_folder_without_prefix(self) -> None:
        account_map = {"Sparkonto": 99}
        assert find_account_id("Sparkonto", account_map) == 99

    def test_swedish_chars_in_account_name_matched(self) -> None:
        account_map = {"SEB Räkningskonto": 5}
        assert find_account_id("kontoutdrag_SEB_Rakningskonto", account_map) == 5

    def test_account_name_substring_of_folder_key(self) -> None:
        account_map = {"Löne": 3}
        assert find_account_id("kontoutdrag_Lonekonto", account_map) == 3

    def test_folder_key_substring_of_account_name(self) -> None:
        account_map = {"Thomas Lönekonto": 8}
        assert find_account_id("kontoutdrag_Lonekonto", account_map) == 8


class TestFindAccountIdMultipleMatches:
    def test_multiple_matches_returns_longest(self) -> None:
        account_map = {
            "Lönekonto": 1,
            "Thomas Lönekonto": 2,
        }
        result = find_account_id("kontoutdrag_SEB_Thomas_Lonekonto", account_map)
        assert result == 2

    def test_two_matches_result_is_one_of_them(self) -> None:
        account_map = {
            "Sparkonto": 10,
            "Lonekonto": 20,
        }
        result = find_account_id("kontoutdrag_konto", account_map)
        assert result in (10, 20)
