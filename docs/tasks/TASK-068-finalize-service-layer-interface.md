# TASK-068 Finalize stable, documented service-layer interface for external consumption

## Status
todo

## Requirements
**Binding:** FR-71, FR-72, FR-73
**BDD mode:** BDD-ABSENT
**Depends on:** TASK-067
**Precedence:** The requirements above are the binding definition of this task.
The story and scenarios below are derived from them. On any discrepancy, the
requirements document wins. Stop and report discrepancies; do not build from
the story.

## Story (context, not binding)
As an external application developer (e.g. a separate web frontend project), I want a
stable, well-documented public interface to the service layer that I can import and
use independently, with clear documentation of function signatures, parameters,
return types, and event types, so that I can integrate this importer's logic into
my own application without being forced to depend on the CLI or re-implement the
business logic myself.

## Description
FR-73 requires the service layer to be "importable as a Python library by an external
application via a stable module path and function/class signatures, without this
repository running its own HTTP server." This task finalizes that interface after
TASK-067 completes the refactor. Specifically:

1. Define the public module path (e.g. `firefly_bank_importer.service` or similar).
2. Document all public functions, classes, event types, and their parameters,
   return types, and exceptions with clear docstrings and/or an interface guide.
3. Verify that the service layer has no dependency on web frameworks (Flask, FastAPI)
   or HTTP servers (uvicorn, gunicorn, waitress).
4. Confirm that external applications provide their own `FireflyClient` instance
   (constructed in their own code, real in production, mocked in tests) rather than
   the service layer constructing the client.

The result is a stable, importable library interface suitable for consumption by
projects outside this repository.

## Branch
**Branch name:** `task/068-finalize-service-layer-interface`
**Switch/create:** `git checkout -b task/068-finalize-service-layer-interface`
**Make target:** `make branch-task f=TASK-068`

## Acceptance criteria (Gherkin)
- [ ] Scenario: Service layer has stable, documented public interface
      Given the refactored service layer from TASK-067
      When external documentation (docstrings, interface guide, or README section) describes the importable module path and public functions/classes per FR-71/FR-73
      Then the public functions, classes, event types, and their parameters, return types, and exceptions are clearly documented so an external application can use them

- [ ] Scenario: Service layer can be imported and used without CLI code
      Given an external application (not this repo) imports the service layer per FR-73
      When it instantiates a FireflyClient separately (or provides a mocked one for testing) and calls a public service-layer function with configuration (folder paths, flags, client instance)
      Then the import succeeds, the function runs without argparse or sys.exit logic, and all results are delivered through return values and event objects (not logging or stdout)

- [ ] Scenario: Service layer has no web framework or HTTP server dependency
      Given the service-layer module and its test suite
      When the module dependencies are analyzed (import statements, pyproject.toml dependencies)
      Then no web framework (Flask, FastAPI, Django) or HTTP server (uvicorn, gunicorn, waitress) appears as a dependency or import within the service layer itself; only `firefly-python-api` and standard library are used for HTTP

- [ ] Scenario: Service layer results are communicated via return values and event objects
      Given an external application calls service-layer functions
      When it provides a callback or event listener for progress/result events
      Then all transaction results, folder summaries, and progress updates are delivered through those event objects and return values, with no reliance on globals, direct logging configuration, or stdout/stderr redirection from the calling environment

## Out of scope
- Building an actual web frontend or HTTP API in this repository (that belongs to the consuming project).
- Creating a separate Python package or PyPI publication (the service layer is used via internal import from within the repo or via git subtree in consuming projects).
- Documentation of how the consuming project should implement HTTP APIs or web UIs on top of the service layer.

## Blockers
None

## Completion
