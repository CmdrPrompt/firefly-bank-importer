# TASK-065 Sync README and NFR-13 with web UI removal

## Status
in-progress

## Requirements
**Binding:** NFR-13
**BDD mode:** BDD-ABSENT
**Depends on:** TASK-064
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As a developer or user reading this repository's documentation, I want the
README and requirements document to describe the actual, current system
(CLI only, no local web UI), so that I am not misled into running a
non-existent `uv run firefly-web` command or expecting web UI behavior that
no longer exists here.

## Description
TASK-064 removed the local web UI (`web_ui.py` and its tests) and updated
`docs/REQUIREMENTS_import_firefly.md`'s use-case/functional-requirement
sections accordingly, but left two stale references flagged as follow-up:

1. **NFR-13 HTTP session layer** (`docs/REQUIREMENTS_import_firefly.md:539-545`)
   still lists `web_ui.py` among the files that must delegate all HTTP calls
   to `firefly-python-api`. Since `web_ui.py` no longer exists in this repo,
   the file list must drop it.
2. **README.md** still describes and instructs use of the removed web UI:
   - Line 5: describes the project as "a Python CLI tool and a (currently
     really ugly) web UI", and says only SEB/ICA formats are supported
     (Nordea, UC-26, has since been added and is undocumented here too).
   - Line 12: lists "Web UI for folder selection, dry-run preview, live
     import, CSV upload, and import history" as a feature.
   - Line 14: "the web UI is still a work in progress".
   - Line 26: tells the user to configure Firefly settings "via the web UI
     settings page".
   - Lines 30-36: a full "Web UI (recommended)" usage section instructing
     `uv run firefly-web`, a script entry that TASK-064 removed from
     `pyproject.toml`.
   - Lines 55-58: the supported-CSV-formats table is missing Nordea.

## Branch
**Branch name:** `task/065-sync-readme-and-nfr13-web-ui-removal`
**Switch/create:** `git checkout -b task/065-sync-readme-and-nfr13-web-ui-removal`
**Make target:** `make branch-task f=TASK-065`

## Acceptance criteria (Gherkin)
- [x] Scenario: NFR-13 no longer references the removed web UI module
      Given NFR-13 lists `import_firefly.py`, `web_ui.py`, and `config.py` as files that must not construct their own HTTP session
      When this task is completed
      Then NFR-13 lists only `import_firefly.py` and `config.py`
- [x] Scenario: README no longer describes or instructs use of a web UI
      Given README.md describes a web UI, lists it as a feature, and instructs `uv run firefly-web`
      When this task is completed
      Then README.md describes this repository as a CLI tool and importable service layer only, with no web UI usage instructions or feature bullet, and no reference to `uv run firefly-web`
- [x] Scenario: README documents Nordea as a supported format
      Given the supported-CSV-formats table and intro paragraph mention only SEB and ICA
      When this task is completed
      Then Nordea (UC-26) is listed alongside SEB and ICA with its required headers

## Out of scope
- Documenting the future standalone frontend project or the service-layer's external-consumption interface (FR-71/72/73) in the README — that belongs to a later task once the service layer itself is implemented.

## Blockers
None.

## Completion
**Date:** 2026-08-02
**Summary:** Dropped `web_ui.py` from NFR-13's list of files that must not construct their own HTTP session (only `import_firefly.py` and `config.py` remain). Rewrote README.md to describe this repository as CLI-only: removed the intro's web UI mention, the "Web UI" feature bullet, the web-UI-in-progress note, the web-UI-settings-page reference, and the full "Web UI (recommended)" usage section with `uv run firefly-web`; added Nordea (UC-26) to the intro paragraph and the supported-CSV-formats table with its `Bokföringsdag`/`Belopp`/`Rubrik` headers. Docs-only change; no code or tests affected, so no TDD cycle or coverage baseline applies. Branched `task/065-sync-readme-and-nfr13-web-ui-removal` off the tip of `task/064-retire-local-web-ui` (997f7128) instead of `origin/main`, since TASK-064's branch is not yet merged and both tasks touch `docs/REQUIREMENTS_import_firefly.md`'s NFR-13 section — branching from `origin/main` via `make branch-task` would have recreated `web_ui.py` references this task is meant to remove and produced conflicting edits once TASK-064 merges. `make branch-task f=TASK-065` was not used for branch creation as a result.
**Files changed:**
- `docs/REQUIREMENTS_import_firefly.md` - modified (NFR-13 file list)
- `README.md` - modified (removed web UI content, added Nordea)
- `CHANGELOG.md` - modified (new entries under `### Removed`)
- `docs/tasks/TASK-065-sync-readme-and-nfr13-web-ui-removal.md` - modified (Status/Completion)
**Branch:** `git checkout task/065-sync-readme-and-nfr13-web-ui-removal`
**Stage:** `README.md docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-065-sync-readme-and-nfr13-web-ui-removal.md`
**Commit:** `git commit -m "Sync README and NFR-13 with web UI removal"`
