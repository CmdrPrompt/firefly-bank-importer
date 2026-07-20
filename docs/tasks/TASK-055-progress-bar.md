# TASK-055 Progress bar vid import

## Status

done

## Description

Lägg till en `tqdm`-baserad progressbar för transaktionspostningen vid
import, i både dry-run och live-läge, för både en-mapp- och
flerkonto-import.

Realiserar UC-32 och FR-67 i `docs/REQUIREMENTS_import_firefly.md`.

Ny beroende: `tqdm>=4.66` läggs till i `pyproject.toml`.

Flöde:

1. Innan transaktioner postas för en körning bestäms det totala antalet
   rader som ska bearbetas: för en enskild mapp — antalet väntande rader för
   det kontot; för en flerkonto-körning — summan av överföringspar plus
   omatchade rader över samtliga mappar.
2. En `tqdm`-progressbar visas som avancerar en gång per bearbetad rad
   (oavsett om den postas live eller loggas som dry-run-förhandsvisning).
3. Progressbaren skrivs till terminalen (stderr) och stör inte de
   befintliga `INFO`-loggraderna som skrivs till stdout och loggfilen.
4. Vid avslut stängs progressbaren; befintliga summeringsloggrader
   (`Summa: X ok, Y fel` osv.) påverkas inte.

Berörda kodställen:

- `process_csv` (en-mapp-vägen): posonings-loopen i dry-run-grenen och
  `_run_threaded_import`.
- `_post_unmatched_rows` och transfer-postnings-loopen i
  `_run_multi_folder_import` (flerkonto-vägen).

## Branch

**Branch name:** `task/055-progress-bar`
**Switch/create:** `git checkout -b task/055-progress-bar`
**Make target:** `make branch-task f=TASK-055`

## Acceptance criteria (Gherkin)

- [x] Scenario: Progressbar visas vid live-import, en mapp
      Given ett konto med flera väntande rader att importera
      When importen körs utan `--dry-run`
      Then en `tqdm`-progressbar avancerar en gång per postad rad
      And progressbaren stängs när kontots rader är klara

- [x] Scenario: Progressbar visas vid dry-run, en mapp
      Given ett konto med flera väntande rader
      When importen körs med `--dry-run`
      Then en `tqdm`-progressbar avancerar en gång per rad som loggas som
      dry-run-förhandsvisning
      And inga transaktioner postas

- [x] Scenario: Progressbar visas vid flerkonto-import
      Given en körning med flera kontomappar, inklusive detekterade
      överföringar och omatchade rader
      When importen körs (live eller dry-run)
      Then progressbaren avancerar en gång per bearbetad rad, inklusive
      både överföringspar och omatchade rader

- [x] Scenario: Befintlig loggning påverkas inte
      Given en pågående import
      When progressbaren visas
      Then befintliga `INFO`-loggrader (t.ex. "Bearbetar:", "Summa: X ok, Y
      fel") skrivs som idag till stdout och loggfilen

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Progressbar för `firefly-clear-transactions` eller andra kommandon —
  endast import (`process_csv`/`_run_multi_folder_import`) omfattas.
- Progressbar i web UI:ts live-import-flöde (som redan har egen
  polling-baserad progressvisning).
- Konfigurerbar avstängning av progressbaren (t.ex. `--no-progress`) — inte
  efterfrågat.

## Blockers

None.

## Completion

**Date:** 2026-07-21
**Summary:** Added `tqdm>=4.66` as a runtime dependency and wrapped the transaction-posting loops with a progress bar: `process_csv` now wraps both its dry-run preview loop and its call to `_run_threaded_import` in a `tqdm(total=len(pending), ...)` context, advancing once per row (live or dry-run). `_run_multi_folder_import` creates a single shared `tqdm(total=len(pairs)+len(unmatched), desc="Import", ...)` covering the whole multi-folder run, passed through to `_post_transfer` (advances in a `finally` block so it advances even on error) and `_post_unmatched_rows` (advances per dry-run row, or passes the bar into `_run_threaded_import` for live posting). `_run_threaded_import` gained an optional `pbar` parameter; extracted `_submit_batch`/`_handle_batch_result` helpers out of it to keep it under the complexipy 15 threshold after adding the pbar branches (was 24 in the first version). Added `tqdm[Any] | None` as the pbar type — quoted as a full string annotation (`"tqdm[Any] | None"`) because `"tqdm[Any]" | None` evaluates at runtime as `str.__or__(None)` and raises `TypeError` at import time; caught this by running the test suite, which failed all collection with that error. Added `types-tqdm` to dev dependencies for `mypy --strict`. 9 new tests in `tests/unit/test_progress_bar.py` using a `FakeTqdm` test double (patched in via `monkeypatch.setattr(module, "tqdm", FakeTqdm)`) that records `total`/`updates` without needing real terminal rendering, covering live/dry-run/empty/error paths for both the single-folder and multi-folder posting code paths. 425 tests pass (up from 416), coverage 92.41%→93.03% (no regression — the first pass actually dropped to 91.80% due to new untested error branches; added targeted tests for `_run_threaded_import`'s exception path, `_post_transfer`'s `FireflyConnectionError` path, and `_post_unmatched_rows`' dry-run path to recover it). `make lint` (ruff, ruff format, mypy, bandit, pymarkdown, complexipy) all clean.
**Files changed:**

- `pyproject.toml` — modified (`tqdm>=4.66` runtime dependency, `types-tqdm` dev dependency)
- `.pre-commit-config.yaml` — modified (`types-tqdm` added to the mypy hook's `additional_dependencies`, since its isolated environment doesn't inherit project dev deps)
- `uv.lock` — modified
- `src/firefly_bank_importer/import_firefly.py` — modified (`_submit_batch`, `_handle_batch_result` added; `_run_threaded_import`, `process_csv`, `_post_transfer`, `_post_unmatched_rows`, `_run_multi_folder_import` updated for `pbar` support)
- `tests/unit/test_progress_bar.py` — added
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-32, FR-67 — already present from requirements confirmation)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-055-progress-bar.md` — modified

**Branch:** `git checkout task/055-progress-bar`
**Stage:** `git add pyproject.toml .pre-commit-config.yaml uv.lock src/firefly_bank_importer/import_firefly.py tests/unit/test_progress_bar.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-055-progress-bar.md`
**Commit:** `git commit -m "Add tqdm progress bar during transaction import (TASK-055)"`
