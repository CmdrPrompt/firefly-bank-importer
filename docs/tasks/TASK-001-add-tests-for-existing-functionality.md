# TASK-001 Add characterisation tests for date parsing and duplicate detection

## Status
todo

## Description
The date parsing and duplicate-detection logic has no unit tests. This is the highest-risk
area of the codebase since incorrect behavior could cause missed imports or false duplicate
detection against live Firefly data.

Covers:
- Parsing of date strings from SEB and ICA CSV formats
- Comparison logic for deduplication (dates ≤ latest transaction date in Firefly)
- Edge cases: end of month, year boundaries, empty date fields

## Acceptance criteria
- [ ] Characterisation tests written for all date parsing functions
- [ ] Characterisation tests written for duplicate detection logic
- [ ] Hypothesis strategies used for date string fuzzing
- [ ] Any surprising or incorrect behavior noted and raised with user
- [ ] Tests pass with `make test`

## Completion
**Date:**
**Summary:**