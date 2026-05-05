"""Tests for FR-63: CSV filename filter in auto_split_folder.

Two recognized file types:
  1. Bank export  — filename contains 'konto' or 'kontoutdrag' (case-insensitive) → split
  2. Monthly file — filename matches YYYY-MM.csv → leave for direct import
  3. Anything else → log WARNING, skip
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest

from firefly_bank_importer.import_firefly import auto_split_folder


def _touch(folder: Path, name: str) -> Path:
    p = folder / name
    p.write_text("dummy", encoding="utf-8")
    return p


class TestKontoutdragFilesAreSplit:
    def test_kontoutdrag_in_name_is_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "kontoutdrag_seb.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_called_once_with(tmp_path / "kontoutdrag_seb.csv")

    def test_konto_in_name_is_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "konto_nordea.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_called_once_with(tmp_path / "konto_nordea.csv")

    def test_case_insensitive_KONTO(self, tmp_path: Path) -> None:
        _touch(tmp_path, "KONTO_export.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_called_once_with(tmp_path / "KONTO_export.csv")

    def test_case_insensitive_Kontoutdrag(self, tmp_path: Path) -> None:
        _touch(tmp_path, "Kontoutdrag_ICA.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_called_once_with(tmp_path / "Kontoutdrag_ICA.csv")

    def test_multiple_kontoutdrag_files_all_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "kontoutdrag_seb.csv")
        _touch(tmp_path, "konto_ica.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        assert mock_split.call_count == 2


class TestMonthlyFilesAreNotSplit:
    def test_yyyy_mm_csv_is_not_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "2025-01.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_not_called()

    def test_multiple_monthly_files_not_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "2025-01.csv")
        _touch(tmp_path, "2025-02.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_not_called()


class TestUnknownFilesWarnAndSkip:
    def test_unknown_file_is_not_split(self, tmp_path: Path) -> None:
        _touch(tmp_path, "transactions.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_not_called()

    def test_unknown_file_logs_warning(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        _touch(tmp_path, "transactions.csv")
        with caplog.at_level(logging.WARNING), patch("firefly_bank_importer.import_firefly.split_file_in_place"):
            auto_split_folder(tmp_path)
        assert "transactions.csv" in caplog.text
        assert any(r.levelno == logging.WARNING for r in caplog.records)

    def test_unknown_file_warning_message_format(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        _touch(tmp_path, "export.csv")
        with caplog.at_level(logging.WARNING), patch("firefly_bank_importer.import_firefly.split_file_in_place"):
            auto_split_folder(tmp_path)
        assert "Okänd filtyp" in caplog.text
        assert "export.csv" in caplog.text

    def test_multiple_unknown_files_each_warns(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        _touch(tmp_path, "foo.csv")
        _touch(tmp_path, "bar.csv")
        with caplog.at_level(logging.WARNING), patch("firefly_bank_importer.import_firefly.split_file_in_place"):
            auto_split_folder(tmp_path)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 2


class TestMixedFolderContents:
    def test_only_kontoutdrag_is_split_from_mixed_folder(self, tmp_path: Path) -> None:
        _touch(tmp_path, "kontoutdrag_seb.csv")
        _touch(tmp_path, "2025-01.csv")
        _touch(tmp_path, "readme.csv")
        with patch("firefly_bank_importer.import_firefly.split_file_in_place") as mock_split:
            auto_split_folder(tmp_path)
        mock_split.assert_called_once_with(tmp_path / "kontoutdrag_seb.csv")

    def test_mixed_folder_warns_only_for_unknown(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        _touch(tmp_path, "kontoutdrag_seb.csv")
        _touch(tmp_path, "2025-01.csv")
        _touch(tmp_path, "readme.csv")
        with caplog.at_level(logging.WARNING), patch("firefly_bank_importer.import_firefly.split_file_in_place"):
            auto_split_folder(tmp_path)
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "readme.csv" in caplog.text
