# TASK-004 Tests for _build_transaction_payload and _log_tx_result

## Status
done

## Description
Add characterisation tests for `_build_transaction_payload` and `_log_tx_result`.
Both are pure or near-pure functions with no real I/O.

`_build_transaction_payload` returns a withdrawal payload for negative amounts and a deposit
payload for positive amounts, with the correct field names and formatted amount string.

`_log_tx_result` inspects the HTTP response status code: 200/201 → logs info and returns True,
any other status → logs error and returns False.

## Acceptance criteria
- [ ] Tests for `_build_transaction_payload`: negative amount → type=withdrawal, source_id set;
      positive amount → type=deposit, destination_id set; amount formatted to 2 decimals;
      all required fields present (date, description, currency_code)
- [ ] Hypothesis test for `_build_transaction_payload`: sign of amount determines type
- [ ] Tests for `_log_tx_result`: status 200 → True, 201 → True, 400/404/500 → False
- [ ] Tests pass with `make test`

## Completion
**Date:** 2026-03-28
**Summary:** 21 characterisation tests written in tests/unit/test_transaction_payload_log.py.
Covers withdrawal vs deposit type selection, source_id/destination_id presence, amount
formatting to 2 decimals, required fields (date, description, currency_code), 2 Hypothesis
invariants (negative → withdrawal, positive → deposit), and _log_tx_result for status 200,
201, and 400/404/422/500. All 21 tests pass.
**Files changed:**
- `tests/unit/test_transaction_payload_log.py` — created
**Stage:** `git add tests/unit/test_transaction_payload_log.py docs/tasks/TASK-004-tests-transaction-payload-log.md`
**Commit:** `git commit -m "Add characterisation tests for _build_transaction_payload and _log_tx_result"`
