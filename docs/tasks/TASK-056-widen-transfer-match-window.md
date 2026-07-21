# TASK-056 Bredda datumfönster för överföringsmatchning

## Status

done

## Description

Reviderar överförings-matchningen (UC-31/FR-66, TASK-054) baserat på analys
av en riktig dry-run mot användarens bankexportfiler: 229 överföringar
detekterades korrekt, men flera troliga överföringar missades eftersom
samma-bank-fönstret idag är 0 dagar (kräver exakt samma datum). Exempel:
`ALY DÄCK` (konto 75, 2025-05-09) och `ALY DÄCKBYTE` (konto 8, 2025-05-12),
samma belopp (1890,00 kr), matchande text, men 3 dagars mellanrum — missas
idag.

Ny regel:

1. Samma-bank- och olika-bank-fönstret slås ihop till ett enda fönster:
   **0–3 dagars skillnad**, oavsett bankformat.
2. Vid **exakt samma datum (diff=0)**: matchning sker som idag — belopp
   räcker för att para ihop en ensam kandidat; textöverlappning används bara
   som tiebreaker vid flera kandidater.
3. Vid **1–3 dagars skillnad**: en matchning kräver **alltid**
   textöverlappning (delsträng i endera riktningen) — även om det bara
   finns en kandidat med rätt belopp. Ett rent beloppsmatch över skilda
   datum ska aldrig godkännas. Finns ingen, eller mer än en, kandidat med
   textöverlappning inom fönstret: raden lämnas omatchad.

Detta minskar risken för falska träffar vid bredare fönster (t.ex. två
orelaterade transaktioner på 5000 kr med 1 dags mellanrum ska inte matchas
utan gemensam text), samtidigt som legitima överföringar med några dagars
bokföringsfördröjning fångas.

Realiserar den reviderade UC-31 och FR-66 i
`docs/REQUIREMENTS_import_firefly.md`.

Berörda kodställen: `_is_amount_and_date_match`, `_candidates_for_row`,
`_choose_candidate`, `_resolve_row_choice` i `import_firefly.py` (TASK-054).

## Branch

**Branch name:** `task/056-widen-transfer-match-window`
**Switch/create:** `git checkout -b task/056-widen-transfer-match-window`
**Make target:** `make branch-task f=TASK-056`

## Acceptance criteria (Gherkin)

- [x] Scenario: Samma datum matchas på belopp ensamt, som idag
      Given två rader med samma belopp, motsatt tecken, olika konton, samma
      datum
      When matchningen körs
      Then raderna paras ihop utan krav på textöverlappning

- [x] Scenario: 1–3 dagars skillnad matchas endast med textöverlappning
      Given två rader med samma belopp, motsatt tecken, olika konton, och
      datum som skiljer 1–3 dagar
      And beskrivningarna delar en delsträng (skiftlägesokänsligt)
      When matchningen körs
      Then raderna paras ihop

- [x] Scenario: 1–3 dagars skillnad utan textöverlappning matchas inte
      Given två rader med samma belopp, motsatt tecken, olika konton, och
      datum som skiljer 1–3 dagar
      And beskrivningarna inte delar någon delsträng
      When matchningen körs
      Then raderna paras INTE ihop, även om de är den enda kandidaten var
      And båda postas som withdrawal/deposit som vanligt

- [x] Scenario: Mer än 3 dagars skillnad matchas aldrig
      Given två rader med samma belopp, motsatt tecken, olika konton, och
      datum som skiljer mer än 3 dagar
      When matchningen körs
      Then raderna paras inte ihop, oavsett textöverlappning

- [x] Scenario: Samma-bank och olika-bank behandlas nu identiskt
      Given två konton med samma bankformat respektive två konton med olika
      bankformat, i övrigt identiska förutsättningar (belopp, datumdiff,
      textöverlappning)
      When matchningen körs
      Then resultatet blir detsamma oavsett bankformat

- [x] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Ändring av `_description_overlap`s definition (delsträng,
  skiftlägesokänsligt) — endast NÄR den krävs ändras, inte HUR den
  beräknas.
- Ändring av opening balance-logiken (TASK-053) eller progressbaren
  (TASK-055) — orörda av denna task.
- Manuell efterhandskonvertering av redan importerade withdrawal/deposit-par
  som nu skulle matchas med det bredare fönstret — endast framtida importer
  påverkas.

## Blockers

None.

## Completion

**Date:** 2026-07-21
**Summary:** Widened the transfer-matching date window from the previous same-bank-0-day/cross-bank-2-day split to a unified `0`–`3`-day window (`MAX_TRANSFER_DATE_DIFF_DAYS = 3`) regardless of bank format, and added a safety rule: same-day (`0`-day) candidates still match on amount alone (single unambiguous candidate wins; ties broken by description overlap, unchanged from TASK-054); candidates `1`–`3` days apart now *require* description overlap to be chosen at all — an amount-only match across differing dates is never made, even when it's the only same-amount candidate in the window. Implemented by splitting `_choose_candidate` into a same-day check and a fallback to a new `_choose_among` helper (shared disambiguation logic) applied separately to the near-day candidate group. `_is_amount_and_date_match` now uses the single `MAX_TRANSFER_DATE_DIFF_DAYS` constant instead of branching on `bank_format` equality (the `bank_format` field on `PendingRow` is kept for other uses but no longer affects the window). Verified against a real dry-run of the user's own bank export data: transfers detected went from 229 to 232 (3 additional matches, e.g. `ALY DÄCK`/`ALY DÄCKBYTE`, 3 days apart with matching text), while a known false-positive risk (`THOMAS LINDQ`/`WYK47R AMORT`, same amount, 1 day apart, no shared text) correctly remains unmatched. Also compared against a 4-day window during analysis and found it added no further real matches (all diff=4 candidates lacked description overlap and would stay unmatched under the text-required rule regardless), so 3 days was kept. 6 new/revised tests plus updates to existing ones in `tests/unit/test_transfer_detection.py` (`TestMatchTransferPairsSameDay`, `TestMatchTransferPairsNearDay` replacing the old same-bank/cross-bank split, plus new `_choose_candidate`-level cases). 429 tests pass (up from 425), coverage 93.03%→93.06% (no regression). `make lint` clean.
**Files changed:**

- `src/firefly_bank_importer/import_firefly.py` — modified (`MAX_TRANSFER_DATE_DIFF_DAYS` added; `_is_amount_and_date_match`, `_choose_candidate` revised; `_choose_among` added)
- `tests/unit/test_transfer_detection.py` — modified
- `docs/REQUIREMENTS_import_firefly.md` — modified (UC-31, FR-66 revised)
- `CHANGELOG.md` — modified
- `docs/tasks/TASK-056-widen-transfer-match-window.md` — modified

**Branch:** `git checkout task/056-widen-transfer-match-window`
**Stage:** `git add src/firefly_bank_importer/import_firefly.py tests/unit/test_transfer_detection.py docs/REQUIREMENTS_import_firefly.md CHANGELOG.md docs/tasks/TASK-056-widen-transfer-match-window.md`
**Commit:** `git commit -m "Widen cross-account transfer matching to a unified 0-3 day window with text-required disambiguation (TASK-056)"`
