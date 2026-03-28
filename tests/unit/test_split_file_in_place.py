"""Characterisation tests for split_file_in_place().

Documents current behavior as-is. Creates real CSV files in tmp_path
to avoid touching the actual bankImports directory.
"""

import csv
from pathlib import Path

from firefly_bank_importer.import_firefly import split_file_in_place

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
ICA_HEADERS = ["Datum", "Text", "Typ", "Belopp"]


def write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter=";")
        headers = next(reader)
        rows = list(reader)
    return headers, rows


class TestSebMultiMonth:
    def test_creates_one_file_per_month(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [
                ["2025-01-15", "2025-01-15", "V1", "Shop", "-100,00", "900,00"],
                ["2025-02-10", "2025-02-10", "V2", "Salary", "1000,00", "1900,00"],
            ],
        )
        split_file_in_place(src)
        assert (tmp_path / "2025-01.csv").exists()
        assert (tmp_path / "2025-02.csv").exists()

    def test_original_file_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [["2025-01-15", "2025-01-15", "V1", "Shop", "-100,00", "900,00"]],
        )
        split_file_in_place(src)
        assert not src.exists()

    def test_rows_go_into_correct_month_file(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [
                ["2025-01-15", "2025-01-15", "V1", "Jan", "-50,00", "950,00"],
                ["2025-02-10", "2025-02-10", "V2", "Feb", "100,00", "1050,00"],
            ],
        )
        split_file_in_place(src)
        _, jan_rows = read_csv(tmp_path / "2025-01.csv")
        _, feb_rows = read_csv(tmp_path / "2025-02.csv")
        assert len(jan_rows) == 1
        assert jan_rows[0][3] == "Jan"
        assert len(feb_rows) == 1
        assert feb_rows[0][3] == "Feb"

    def test_rows_sorted_chronologically_within_month(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [
                ["2025-01-20", "2025-01-20", "V2", "Later", "-20,00", "980,00"],
                ["2025-01-05", "2025-01-05", "V1", "Earlier", "-10,00", "990,00"],
            ],
        )
        split_file_in_place(src)
        _, rows = read_csv(tmp_path / "2025-01.csv")
        assert rows[0][0] == "2025-01-05"
        assert rows[1][0] == "2025-01-20"

    def test_output_file_has_correct_headers(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [["2025-01-15", "2025-01-15", "V1", "Shop", "-100,00", "900,00"]],
        )
        split_file_in_place(src)
        headers, _ = read_csv(tmp_path / "2025-01.csv")
        assert headers == SEB_HEADERS


class TestIcaMultiMonth:
    def test_creates_one_file_per_month(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ICA_HEADERS,
            [
                ["2025-03-10", "ICA", "Köp", "-200,00"],
                ["2025-04-05", "ICA", "Köp", "-150,00"],
            ],
        )
        split_file_in_place(src)
        assert (tmp_path / "2025-03.csv").exists()
        assert (tmp_path / "2025-04.csv").exists()

    def test_ica_original_deleted(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ICA_HEADERS,
            [["2025-03-10", "ICA", "Köp", "-200,00"]],
        )
        split_file_in_place(src)
        assert not src.exists()

    def test_ica_rows_sorted_within_month(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ICA_HEADERS,
            [
                ["2025-03-25", "ICA", "Köp", "-50,00"],
                ["2025-03-01", "ICA", "Köp", "-80,00"],
            ],
        )
        split_file_in_place(src)
        _, rows = read_csv(tmp_path / "2025-03.csv")
        assert rows[0][0] == "2025-03-01"
        assert rows[1][0] == "2025-03-25"


class TestSingleMonthFile:
    def test_single_month_creates_one_output(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [
                ["2025-06-01", "2025-06-01", "V1", "A", "-10,00", "990,00"],
                ["2025-06-15", "2025-06-15", "V2", "B", "-20,00", "970,00"],
            ],
        )
        split_file_in_place(src)
        assert (tmp_path / "2025-06.csv").exists()
        assert not src.exists()


class TestAmountNormalisation:
    def test_comma_decimal_converted_to_dot(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "X", "-1 234,56", "8 765,44"]],
        )
        split_file_in_place(src)
        _, rows = read_csv(tmp_path / "2025-01.csv")
        assert "." in rows[0][4]
        assert "," not in rows[0][4]

    def test_saldo_normalised_when_present(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "X", "-100,00", "9 000,00"]],
        )
        split_file_in_place(src)
        _, rows = read_csv(tmp_path / "2025-01.csv")
        assert "." in rows[0][5]
        assert "," not in rows[0][5]

    def test_amount_formatted_to_two_decimal_places(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            SEB_HEADERS,
            [["2025-01-10", "2025-01-10", "V1", "X", "-100,5", "900,5"]],
        )
        split_file_in_place(src)
        _, rows = read_csv(tmp_path / "2025-01.csv")
        assert rows[0][4] == "-100.50"

    def test_ica_no_saldo_column_does_not_crash(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ICA_HEADERS,
            [["2025-05-10", "ICA", "Köp", "-99,00"]],
        )
        split_file_in_place(src)
        assert (tmp_path / "2025-05.csv").exists()


class TestUnknownFormat:
    def test_unknown_format_no_output_files(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ["Col1", "Col2"],
            [["val1", "val2"]],
        )
        split_file_in_place(src)
        output_files = list(tmp_path.glob("????-??.csv"))
        assert output_files == []

    def test_unknown_format_source_untouched(self, tmp_path: Path) -> None:
        src = tmp_path / "export.csv"
        write_csv(
            src,
            ["Col1", "Col2"],
            [["val1", "val2"]],
        )
        split_file_in_place(src)
        assert src.exists()
