# TASK-063 Web UI saknar CLI:ns senare importfunktioner

## Status
cancelled

## Requirements
**Binding:** UC-29, UC-30, UC-31, UC-33, UC-34, UC-35, FR-64, FR-65, FR-66, FR-68, FR-69, FR-70
**BDD mode:** BDD-ABSENT
**Depends on:** none
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a user of the web UI, I want the same import behavior I get from the CLI,
so that dry-run previews and live imports done through the browser are not
silently less correct than a terminal-run import.

## Description
`web_ui.py` does not call `process_folder` / `_run_multi_folder_import` from
`import_firefly.py`. Instead it has its own parallel implementation of
dry-run preview and live import (`_build_dry_run_summary`,
`_process_live_import_folder`, `_run_live_import_job`), built directly on
low-level primitives (`create_transaction`, `get_latest_transaction_date`,
`find_account_id`). Every CLI feature added to the shared import core since
the web UI was written never reached the web path:

| Feature | Requirement | CLI | Web UI |
|---|---|---|---|
| Automatic opening balance | UC-30 / FR-65 | Implemented | Not implemented |
| Cross-account transfer detection (incl. widened match window) | UC-31 / FR-66 | Implemented | Not implemented |
| Transfers excluded from latest-date duplicate check | FR-66-adjacent fix (TASK-057) | Implemented | Not implemented |
| Period-scoped import (`--period YYYY-MM`) | UC-33 / FR-68 | Implemented | Not implemented |
| Account names in log lines | UC-34 / FR-69 | Implemented | Not implemented (web UI uses its own log format) |
| Import duration logging | UC-35 / FR-70 | Implemented | Not implemented |
| Clear transactions for reimport | UC-29 / FR-64 | Implemented (CLI command) | Not implemented (never requested for web) |

The `docs/REQUIREMENTS_import_firefly.md` traceability table also currently
marks these UC/FR rows as "Not implemented" outright, which is stale — they
are implemented in the CLI, just not in the web UI. That table should be
corrected to distinguish CLI vs. web UI coverage as part of this task.

This task tracks the gap for prioritization. It does not decide the
implementation approach (e.g., whether the web UI should be refactored to
call the shared `process_folder`/`_run_multi_folder_import` core instead of
its own duplicated logic, or reimplement each feature independently) — that
decision, and any resulting requirements text, must be confirmed with the
user before implementation starts, per this project's spec-driven workflow.
It is related to but independent of TASK-033 (missing `POST
/account-mapping` route), which blocks the web import flow entirely
regardless of this gap.

## Branch
**Branch name:** `task/063-web-ui-cli-parity-gap`
**Switch/create:** `git checkout -b task/063-web-ui-cli-parity-gap`
**Make target:** `make branch-task f=TASK-063`

## Acceptance criteria (Gherkin)
- [ ] Scenario: Web UI dry-run applies automatic opening balance
      Given an account's current opening balance is 0 and its bank format has a balance_header
      When a dry-run preview is generated through the web UI for that account's folder
      Then the preview reports the opening balance and date it would set and excludes that row from the previewed transactions, matching FR-65
- [ ] Scenario: Web UI live import detects cross-account transfers
      Given two or more account folders are selected for a live import through the web UI, with a matching withdrawal/deposit pair between them
      When the live import runs
      Then a single transfer transaction is posted for the matched pair instead of two separate withdrawal/deposit transactions, matching FR-66
- [ ] Scenario: Web UI latest-date check ignores transfers
      Given an account has only transfer transactions in Firefly after a given date
      When the web UI computes the latest-date floor for that account
      Then transfer transactions are excluded from that floor, matching the CLI behavior fixed in TASK-057
- [ ] Scenario: Web UI supports period-scoped import
      Given the user selects a period in the web UI equivalent to CLI's `--period YYYY-MM`
      When a dry-run or live import runs
      Then only rows from the matching `<period>.csv` file per folder are processed, matching FR-68
- [ ] Scenario: Web UI logs account names and import duration
      When a live import runs through the web UI
      Then result lines include the resolved account name per FR-69 and the run duration is recorded per FR-70
- [ ] Scenario: Requirements traceability table reflects web UI coverage
      Given the UC-30/31/33/34/35 and FR-64/65/66/68/69/70 rows in docs/REQUIREMENTS_import_firefly.md
      When this task is completed
      Then each row's status distinguishes CLI implementation from web UI implementation instead of a single "Not implemented"/"Implemented" value

## Out of scope
- Deciding or implementing the refactor approach (shared-core reuse vs. reimplementation) — a separate, user-confirmed decision required before any code is written.
- TASK-033 (missing `POST /account-mapping` route) — tracked separately, blocks the web flow independently of this gap.
- Adding a "clear transactions" UI action (UC-29/FR-64) unless the user asks for it — listed here for completeness only.

## Blockers
- Implementation approach (refactor to shared core vs. reimplement per feature) must be decided with the user before this task can move to `in-progress`.

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout task/063-web-ui-cli-parity-gap`
**Stage:** `git add docs/tasks/TASK-063-web-ui-cli-parity-gap.md CHANGELOG.md`
**Commit:** `git commit -m "Document CLI/web UI import feature parity gap"`

> **Superseded (2026-08-01):** The web UI (`web_ui.py` and its tests) has been removed from this repository. The web frontend is being rebuilt as a standalone application in a separate repository, consuming this project's service layer as a library. This task's original status was `todo`; its scope no longer applies here.
