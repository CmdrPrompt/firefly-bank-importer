"""Characterisation tests for cross-account transfer detection (UC-31, FR-66).

Covers the pure matching logic (_match_transfer_pairs, _candidates_for_row,
_choose_candidate, _description_overlap) and its integration into main() for
multi-folder imports. Uses tmp_path for CSV fixtures and unittest.mock for
FireflyClient so no real API calls are made.
"""

import csv
import logging
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from firefly_python_api import FireflyClient
from hypothesis import given
from hypothesis import strategies as st

import firefly_bank_importer.import_firefly as module
from firefly_bank_importer.import_firefly import (
    PendingRow,
    _choose_candidate,
    _description_overlap,
    _match_transfer_pairs,
    main,
)

SEB_HEADERS = ["Bokföringsdatum", "Valutadatum", "Verifikationsnummer", "Text", "Belopp", "Saldo"]
ICA_HEADERS = ["Datum", "Text", "Typ", "Belopp"]


def write_seb_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(SEB_HEADERS)
        writer.writerows(rows)


def write_ica_csv(path: Path, rows: list[list[str]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(ICA_HEADERS)
        writer.writerows(rows)


def row(account_id: int, iso_date: str, description: str, amount: str, bank_format: str = "seb") -> PendingRow:
    return PendingRow(
        account_id=account_id,
        iso_date=iso_date,
        description=description,
        amount=amount,
        bank_format=bank_format,
        row_date=date.fromisoformat(iso_date),
    )


# ---------------------------------------------------------------------------
# _description_overlap()
# ---------------------------------------------------------------------------


class TestDescriptionOverlap:
    def test_substring_either_direction(self) -> None:
        assert _description_overlap("K*Amazon", "K*Amazon SE") is True
        assert _description_overlap("K*Amazon SE", "K*Amazon") is True

    def test_case_insensitive(self) -> None:
        assert _description_overlap("Overforing", "OVERFORING till sparkonto") is True

    def test_no_overlap(self) -> None:
        assert _description_overlap("Lon", "Hyra") is False


# ---------------------------------------------------------------------------
# _choose_candidate()
# ---------------------------------------------------------------------------


class TestChooseCandidate:
    def test_single_candidate_is_chosen(self) -> None:
        rows = [row(1, "2025-01-05", "X", "-100.00"), row(2, "2025-01-05", "Y", "100.00")]
        assert _choose_candidate(rows[0], rows, [1]) == 1

    def test_ambiguous_resolved_by_overlap(self) -> None:
        rows = [
            row(1, "2025-01-05", "K*Amazon", "-100.00"),
            row(2, "2025-01-05", "K*Amazon SE", "100.00"),
            row(3, "2025-01-05", "Unrelated", "100.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1, 2]) == 1

    def test_ambiguous_without_overlap_returns_none(self) -> None:
        rows = [
            row(1, "2025-01-05", "X", "-100.00"),
            row(2, "2025-01-05", "Y", "100.00"),
            row(3, "2025-01-05", "Z", "100.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1, 2]) is None

    def test_ambiguous_with_multiple_overlaps_returns_none(self) -> None:
        rows = [
            row(1, "2025-01-05", "K*Amazon", "-100.00"),
            row(2, "2025-01-05", "K*Amazon SE", "100.00"),
            row(3, "2025-01-05", "K*Amazon DE", "100.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1, 2]) is None

    def test_single_near_day_candidate_requires_overlap_to_be_chosen(self) -> None:
        rows = [
            row(1, "2025-05-09", "ALY DACK", "-1890.00"),
            row(2, "2025-05-12", "ALY DACKBYTE", "1890.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1]) == 1

    def test_single_near_day_candidate_without_overlap_is_not_chosen(self) -> None:
        rows = [
            row(1, "2025-07-02", "THOMAS LINDQ", "-5000.00"),
            row(2, "2025-07-03", "WYK47R AMORT", "5000.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1]) is None

    def test_exact_same_day_candidate_preferred_over_near_day_candidate(self) -> None:
        rows = [
            row(1, "2025-01-05", "X", "-100.00"),
            row(2, "2025-01-05", "Unrelated", "100.00"),
            row(3, "2025-01-06", "Unrelated too", "100.00"),
        ]
        assert _choose_candidate(rows[0], rows, [1, 2]) == 1


# ---------------------------------------------------------------------------
# _match_transfer_pairs()
# ---------------------------------------------------------------------------


class TestMatchTransferPairsSameDay:
    def test_matches_same_day_on_amount_alone(self) -> None:
        rows = [row(1, "2025-01-05", "Overforing", "-100.00"), row(2, "2025-01-05", "Unrelated text", "100.00")]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == [(0, 1)]
        assert matched == {0, 1}

    def test_does_not_match_same_account(self) -> None:
        rows = [row(1, "2025-01-05", "X", "-100.00"), row(1, "2025-01-05", "Y", "100.00")]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == []


class TestMatchTransferPairsNearDay:
    def test_matches_within_three_days_with_text_overlap(self) -> None:
        rows = [
            row(1, "2025-05-09", "ALY DACK", "-1890.00", bank_format="seb"),
            row(2, "2025-05-12", "ALY DACKBYTE", "1890.00", bank_format="seb"),
        ]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == [(0, 1)]

    def test_does_not_match_within_three_days_without_text_overlap(self) -> None:
        rows = [
            row(1, "2025-07-02", "THOMAS LINDQ", "-5000.00", bank_format="seb"),
            row(2, "2025-07-03", "WYK47R AMORT", "5000.00", bank_format="seb"),
        ]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == []
        assert matched == set()

    def test_does_not_match_beyond_three_days_even_with_text_overlap(self) -> None:
        rows = [
            row(1, "2025-01-05", "Overforing sparkonto", "-100.00", bank_format="seb"),
            row(2, "2025-01-09", "Overforing sparkonto", "100.00", bank_format="ica"),
        ]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == []

    def test_same_bank_and_different_bank_treated_identically(self) -> None:
        same_bank_rows = [
            row(1, "2025-01-05", "Overforing", "-100.00", bank_format="seb"),
            row(2, "2025-01-07", "Overforing", "100.00", bank_format="seb"),
        ]
        different_bank_rows = [
            row(1, "2025-01-05", "Overforing", "-100.00", bank_format="seb"),
            row(2, "2025-01-07", "Overforing", "100.00", bank_format="ica"),
        ]
        same_pairs, _ = _match_transfer_pairs(same_bank_rows)
        diff_pairs, _ = _match_transfer_pairs(different_bank_rows)
        assert same_pairs == diff_pairs == [(0, 1)]


class TestMatchTransferPairsAmbiguous:
    def test_resolved_by_description_overlap(self) -> None:
        rows = [
            row(1, "2025-01-05", "K*Amazon", "-100.00"),
            row(2, "2025-01-05", "K*Amazon SE", "100.00"),
            row(3, "2025-01-05", "Unrelated", "100.00"),
        ]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == [(0, 1)]
        assert 2 not in matched

    def test_unresolved_ambiguity_leaves_all_unmatched(self) -> None:
        rows = [
            row(1, "2025-01-05", "X", "-100.00"),
            row(2, "2025-01-05", "Y", "100.00"),
            row(3, "2025-01-05", "Z", "100.00"),
        ]
        pairs, matched = _match_transfer_pairs(rows)
        assert pairs == []
        assert matched == set()


@given(a=st.floats(min_value=1, max_value=10000), b=st.floats(min_value=1, max_value=10000))
def test_only_exact_opposite_amounts_match(a: float, b: float) -> None:
    rows = [row(1, "2025-01-05", "X", f"-{a:.2f}"), row(2, "2025-01-05", "Y", f"{b:.2f}")]
    pairs, _ = _match_transfer_pairs(rows)
    if round(a, 2) == round(b, 2):
        assert pairs == [(0, 1)]
    else:
        assert pairs == []


# ---------------------------------------------------------------------------
# Integration with main() for multi-folder imports
# ---------------------------------------------------------------------------


def make_client() -> MagicMock:
    client = MagicMock(spec=FireflyClient)
    client.create_transaction.return_value = None
    client.get_opening_balance.return_value = {"balance": "100.00", "date": None}
    return client


@pytest.fixture(autouse=True)
def reset_block(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(module, "BLOCK_TRANSACTION_POSTS", False)


class TestMainMultiFolderIntegration:
    def test_matched_transfer_posted_once_not_as_withdrawal_deposit(self, tmp_path: Path) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"]])
        write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "100,00", "1100,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
        ):
            main(base_folder=str(tmp_path))

        assert client.create_transaction.call_count == 1
        payload = client.create_transaction.call_args.args[0]["transactions"][0]
        assert payload["type"] == "transfer"
        assert payload["source_id"] == "1"
        assert payload["destination_id"] == "2"
        assert payload["amount"] == "100.00"

    def test_unmatched_rows_posted_as_withdrawal_deposit(self, tmp_path: Path) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-50,00", "950,00"]])
        write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Salary", "2000,00", "3000,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
        ):
            main(base_folder=str(tmp_path))

        payload_types = {c.args[0]["transactions"][0]["type"] for c in client.create_transaction.call_args_list}
        assert payload_types == {"withdrawal", "deposit"}

    def test_dry_run_logs_transfer_without_posting(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "-100,00", "900,00"]])
        write_seb_csv(folder_b / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Overforing", "100,00", "1100,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            caplog.at_level(logging.INFO),
        ):
            main(base_folder=str(tmp_path), dry_run=True)

        client.create_transaction.assert_not_called()
        assert any("[DRY RUN] [transfer]" in r.message for r in caplog.records)

    def test_single_folder_import_unaffected(self, tmp_path: Path) -> None:
        write_seb_csv(tmp_path / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-50,00", "950,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
            patch.object(module, "find_account_id", return_value=1),
        ):
            main(base_folder=str(tmp_path))

        assert client.create_transaction.call_count == 1
        payload = client.create_transaction.call_args.args[0]["transactions"][0]
        assert payload["type"] == "withdrawal"


class TestPeriodScopedMultiFolderImport:
    def test_period_restricts_import_to_matching_month_across_folders(self, tmp_path: Path) -> None:
        folder_a = tmp_path / "kontoutdrag_Lonekonto"
        folder_b = tmp_path / "kontoutdrag_Sparkonto"
        folder_a.mkdir()
        folder_b.mkdir()
        write_seb_csv(folder_a / "2025-01.csv", [["2025-01-05", "2025-01-05", "V1", "Shop", "-50,00", "950,00"]])
        write_seb_csv(folder_a / "2025-02.csv", [["2025-02-05", "2025-02-05", "V1", "Overforing", "-100,00", "850,00"]])
        write_seb_csv(folder_b / "2025-02.csv", [["2025-02-05", "2025-02-05", "V1", "Overforing", "100,00", "1100,00"]])

        client = make_client()
        account_map = {"Lonekonto": 1, "Sparkonto": 2}
        with (
            patch.object(module, "build_account_map", return_value=(account_map, [])),
            patch.object(module, "get_latest_transaction_date", return_value=None),
            patch.object(module, "load_api_token", return_value="token"),
            patch.object(module, "load_firefly_url", return_value="http://firefly.local"),
            patch.object(module, "FireflyClient", return_value=client),
        ):
            main(base_folder=str(tmp_path), period="2025-02")

        # Only the February transfer should be posted; the January withdrawal
        # (folder_a, not in the selected period) must be excluded entirely.
        assert client.create_transaction.call_count == 1
        payload = client.create_transaction.call_args.args[0]["transactions"][0]
        assert payload["type"] == "transfer"
        assert payload["date"] == "2025-02-05"
