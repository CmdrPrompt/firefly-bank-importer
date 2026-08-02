Feature: Finalize stable, documented service-layer interface for external consumption
  As an external application developer (e.g. a separate web frontend project), I want a
  stable, well-documented public interface to the service layer that I can import and
  use independently, with clear documentation of function signatures, parameters,
  return types, and event types, so that I can integrate this importer's logic into
  my own application without being forced to depend on the CLI or re-implement the
  business logic myself.

  All scenarios run against a mocked FireflyClient (MagicMock/monkeypatch). No real
  HTTP calls are made to any Firefly instance.

  Scenario: Service layer has stable, documented public interface
    Given the refactored service layer from TASK-067
    When external documentation (docstrings, interface guide, or README section) describes the importable module path and public functions/classes per FR-71/FR-73
    Then the public functions, classes, event types, and their parameters, return types, and exceptions are clearly documented so an external application can use them

  Scenario: Service layer can be imported and used without CLI code
    Given an external application (not this repo) imports the service layer per FR-73
    When it instantiates a FireflyClient separately (or provides a mocked one for testing) and calls a public service-layer function with configuration (folder paths, flags, client instance)
    Then the import succeeds, the function runs without argparse or sys.exit logic, and all results are delivered through return values and event objects (not logging or stdout)

  Scenario: Service layer has no web framework or HTTP server dependency
    Given the service-layer module and its test suite
    When the module dependencies are analyzed (import statements, pyproject.toml dependencies)
    Then no web framework (Flask, FastAPI, Django) or HTTP server (uvicorn, gunicorn, waitress) appears as a dependency or import within the service layer itself; only `firefly-python-api` and standard library are used for HTTP

  Scenario: Service layer results are communicated via return values and event objects
    Given an external application calls service-layer functions
    When it provides a callback or event listener for progress/result events
    Then all transaction results, folder summaries, and progress updates are delivered through those event objects and return values, with no reliance on globals, direct logging configuration, or stdout/stderr redirection from the calling environment
