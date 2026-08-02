Feature: Decouple logging and tqdm, emit structured events, make CLI a thin adapter
  As a developer, I want the posting and orchestration functions to communicate
  results via structured events instead of calling logging.info/error and
  passing tqdm progress bars as parameters, and I want the CLI to become a
  thin adapter that consumes those events and renders them to the
  terminal/log/progress bar exactly as before, so that the service layer can
  be imported and used independently by external applications and the CLI
  can be tested against mocked clients without behavior change.

  All scenarios run against a mocked FireflyClient (MagicMock/monkeypatch).
  No real HTTP calls are made to any Firefly instance, and the module-level
  BLOCK_TRANSACTION_POSTS guard is enabled for non-dry-run scenarios to
  prevent accidental POSTs, per the task's Test Safety Constraint.

  Scenario: Transaction posting emits structured results, not logging
    Given a posting function processes a transaction
    When the function executes per FR-71
    Then it returns a structured result object containing date, amount, description, account ID, account name, status, and error message
    And it does not call logging.info or logging.error directly

  Scenario: Progress tracking uses events, not tqdm parameters
    Given posting and orchestration functions previously accepted a tqdm progress bar as a parameter
    When refactored per FR-71
    Then they no longer accept a pbar parameter
    And they emit progress events that the CLI consumes and renders to tqdm, producing output identical to the unrefactored tqdm bar

  Scenario: CLI log output for single-folder dry-run matches pre-refactor behavior
    Given a representative single-folder import scenario with known CSV data, run against a mocked FireflyClient in dry-run mode
    When the refactored CLI processes this scenario
    Then the terminal output and log file format, log line content, account names, transaction counts, "Klar!" message, and elapsed duration all match the pre-refactor golden-master version captured against the same mocked setup

  Scenario: CLI log output for multi-folder non-dry-run matches pre-refactor behavior
    Given a representative multi-folder import scenario with transfer detection, run against a mocked FireflyClient with BLOCK_TRANSACTION_POSTS enabled and the dry-run flag omitted
    When the refactored CLI processes this scenario
    Then the terminal output and log file format, log line content, transfer-detection count, per-transaction OK/ERROR status, account names, and elapsed duration all match the pre-refactor golden-master version captured against the same mocked setup

  Scenario: Opening-balance detection result is communicated via events
    Given automatic opening-balance detection with an opening balance of 0
    When the service layer sets the opening balance via set_opening_balance per FR-71
    Then a structured result event includes the balance amount, the date set, and confirmation that the earliest row was excluded from import
    And the CLI renders this to the log identically to before

  Scenario: Transfer detection result includes source and destination account names
    Given transfer detection during a multi-folder import
    When a transfer is matched between accounts
    Then the result event includes source account ID, source account name, destination account ID, destination account name, amount, and date
    And the CLI logs the transfer line in the format "[OK] [transfer] <amount> SEK | <date> | <source name> -> <destination name> | <description>"

  Scenario: Account-name transaction logging works via events
    Given account-name transaction logging
    When each transaction result event is emitted
    Then it includes the account name resolved from the discovered/cached account list
    And the CLI logs the transaction line in the format "[OK] [<account name>] [<type>] <amount> SEK | <date> | <description>" (or "[DRY RUN]" in dry-run mode)

  Scenario: Period scoping works via events
    Given a period-scoped import with a --period YYYY-MM filter
    When folders are processed with the period filter applied
    Then the service layer only emits result events for rows from that period's CSV file
    And the CLI renders the transaction count accurately for that period only

  Scenario: BLOCK_TRANSACTION_POSTS guard is handled consistently for postings and transfers
    Given the event-based refactor introduces a single structured error-handling path per FR-71
    When a regular transaction posting or a transfer posting hits the BLOCK_TRANSACTION_POSTS guard
    Then both emit a structured ERROR result event with status ERROR and an error message, instead of raising
    And the run continues instead of crashing

  Scenario: Duration and average-time logging works via events
    Given an import completes after processing a number of transactions in a known duration
    When the CLI receives final summary events from the service layer
    Then it logs total elapsed time in H:MM:SS format
    And it logs average time per transaction in seconds, identical to the unrefactored version
