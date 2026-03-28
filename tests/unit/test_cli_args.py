"""Characterisation tests for _parse_cli_args().

Documents current behavior as-is.
"""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from firefly_bank_importer.import_firefly import _parse_cli_args


class TestParseCLIArgsValidInput:
    def test_folder_only(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(["prog", "/some/path"])
        assert folder == "/some/path"
        assert dry_run is False
        assert ignore is False
        assert refresh is False
        assert configure is False

    def test_folder_with_dry_run(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(["prog", "/path", "--dry-run"])
        assert folder == "/path"
        assert dry_run is True
        assert ignore is False
        assert refresh is False
        assert configure is False

    def test_folder_with_ignore_latest_date_check(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(["prog", "/path", "--ignore-latest-date-check"])
        assert folder == "/path"
        assert dry_run is False
        assert ignore is True
        assert refresh is False
        assert configure is False

    def test_folder_with_refresh_accounts(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(["prog", "/path", "--refresh-accounts"])
        assert folder == "/path"
        assert dry_run is False
        assert ignore is False
        assert refresh is True
        assert configure is False

    def test_all_flags_after_folder(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(
            ["prog", "/path", "--dry-run", "--ignore-latest-date-check", "--refresh-accounts"]
        )
        assert folder == "/path"
        assert dry_run is True
        assert ignore is True
        assert refresh is True
        assert configure is False

    def test_folder_after_flags(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(["prog", "--dry-run", "/path"])
        assert folder == "/path"
        assert dry_run is True
        assert configure is False

    def test_all_flags_before_folder(self) -> None:
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(
            [
                "prog",
                "--dry-run",
                "--ignore-latest-date-check",
                "--refresh-accounts",
                "/path",
            ]
        )
        assert folder == "/path"
        assert dry_run is True
        assert ignore is True
        assert refresh is True
        assert configure is False


class TestParseCLIArgsAllFlagCombinations:
    @pytest.mark.parametrize(
        "flags,expect_dry,expect_ignore,expect_refresh",
        [
            ([], False, False, False),
            (["--dry-run"], True, False, False),
            (["--ignore-latest-date-check"], False, True, False),
            (["--refresh-accounts"], False, False, True),
            (["--dry-run", "--ignore-latest-date-check"], True, True, False),
            (["--dry-run", "--refresh-accounts"], True, False, True),
            (["--ignore-latest-date-check", "--refresh-accounts"], False, True, True),
            (["--dry-run", "--ignore-latest-date-check", "--refresh-accounts"], True, True, True),
        ],
    )
    def test_flag_combination(
        self,
        flags: list[str],
        expect_dry: bool,
        expect_ignore: bool,
        expect_refresh: bool,
    ) -> None:
        argv = ["prog", "/path"] + flags
        folder, dry_run, ignore, refresh, configure = _parse_cli_args(argv)
        assert folder == "/path"
        assert dry_run == expect_dry
        assert ignore == expect_ignore
        assert refresh == expect_refresh
        assert configure is False


class TestParseCLIArgsConfigureFlag:
    def test_configure_flag_detected(self) -> None:
        _, _, _, _, configure = _parse_cli_args(["prog", "/path", "--configure"])
        assert configure is True

    def test_configure_before_folder(self) -> None:
        folder, _, _, _, configure = _parse_cli_args(["prog", "--configure", "/path"])
        assert folder == "/path"
        assert configure is True

    def test_configure_with_dry_run(self) -> None:
        _, dry_run, _, _, configure = _parse_cli_args(["prog", "/path", "--configure", "--dry-run"])
        assert dry_run is True
        assert configure is True

    def test_no_configure_flag_returns_false(self) -> None:
        _, _, _, _, configure = _parse_cli_args(["prog", "/path"])
        assert configure is False


class TestParseCLIArgsInvalidInput:
    def test_empty_argv_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _parse_cli_args([])

    def test_only_prog_name_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _parse_cli_args(["prog"])

    def test_only_flags_no_path_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            _parse_cli_args(["prog", "--dry-run", "--refresh-accounts"])


class TestParseCLIArgsHypothesis:
    @given(
        folder=st.text(
            alphabet=st.characters(blacklist_categories=["C"], blacklist_characters="-"),
            min_size=1,
        ).filter(lambda s: not s.startswith("--")),
        flags=st.lists(
            st.sampled_from(["--dry-run", "--ignore-latest-date-check", "--refresh-accounts", "--configure"]),
            unique=True,
        ),
    )
    def test_folder_always_extracted(self, folder: str, flags: list[str]) -> None:
        argv = ["prog"] + flags + [folder]
        result_folder, _, _, _, _ = _parse_cli_args(argv)
        assert result_folder == folder

    @given(
        folder=st.text(
            alphabet=st.characters(blacklist_categories=["C"], blacklist_characters="-"),
            min_size=1,
        ).filter(lambda s: not s.startswith("--")),
    )
    def test_dry_run_flag_detection(self, folder: str) -> None:
        folder_val, dry, _, _, _ = _parse_cli_args(["prog", folder, "--dry-run"])
        assert dry is True
        _, no_dry, _, _, _ = _parse_cli_args(["prog", folder])
        assert no_dry is False
