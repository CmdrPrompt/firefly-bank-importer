# TASK-054 Detektera överföringar mellan konton vid import

## Status

not started

## Description

Lägg till detektering och import av överföringar mellan användarens egna
konton vid en flerkonto-import, så att en insättning på ett konto och ett
motsvarande uttag på ett annat konto postas som en enda `transfer`-
transaktion i Firefly III, istället för att postas som två orelaterade
withdrawal/deposit-transaktioner.

Realiserar UC-31 och FR-66 i `docs/REQUIREMENTS_import_firefly.md`.

Detta kräver en arkitekturändring: idag postas varje rad direkt när en mapp
bearbetas (`process_folder`/`process_csv`, per konto, oberoende av andra
mappar). För att kunna para ihop rader mellan konton måste **alla mappars
rader samlas in innan något postas**, sedan paras ihop, och därefter postas
i två steg: matchade par som `transfer`, resterande rader som idag
(withdrawal/deposit).

Matchningsregler (se UC-31 för fullständig beskrivning):

1. Belopp lika stort med motsatt tecken, mellan två olika konton.
2. Datumfönster: samma dag om båda kontona har samma bank-format (t.ex.
   båda SEB), annars upp till 2 dagars skillnad.
3. Vid exakt en kandidat inom fönstret: para ihop direkt.
4. Vid flera kandidater: föredra en kandidat vars text är en
   skiftlägesokänslig delsträng av den andras (i endera riktningen), om
   exakt en sådan kandidat finns. Annars: ingen matchning, raden postas som
   vanligt.
5. Matchade par postas som en `transfer`-transaktion (`source_id` = kontot
   med minusbeloppet, `destination_id` = kontot med plusbeloppet). Båda
   raderna exkluderas från individuell withdrawal/deposit-postning.
6. Med `--dry-run` loggas vilka par som skulle postas som transfers, samt
   vilka rader som förblir omatchade/tvetydiga, utan att något postas.

## Branch

**Branch name:** `task/054-transfer-detection`
**Switch/create:** `git checkout -b task/054-transfer-detection`
**Make target:** `make branch-task f=TASK-054`

## Acceptance criteria (Gherkin)

- [ ] Scenario: Överföring mellan konton hos samma bank matchas samma dag
      Given två konton med samma bank-format
      And ett uttag på det ena kontot och en insättning på det andra, med
      samma belopp och samma datum
      When importen körs för båda kontons mappar i samma körning
      Then en enda `transfer`-transaktion postas mellan kontona
      And ingen av raderna postas som withdrawal eller deposit

- [ ] Scenario: Överföring mellan konton hos olika banker matchas inom 2 dagar
      Given två konton med olika bank-format
      And ett uttag på det ena kontot och en insättning på det andra, med
      samma belopp och datum som skiljer sig med 1 eller 2 dagar
      When importen körs för båda kontons mappar i samma körning
      Then en enda `transfer`-transaktion postas mellan kontona

- [ ] Scenario: Överföring mellan konton hos olika banker matchas inte om
      datumskillnaden överstiger 2 dagar
      Given två konton med olika bank-format
      And rader med samma belopp men datum som skiljer sig med mer än 2 dagar
      When importen körs
      Then ingen transfer postas
      And båda raderna postas som withdrawal respektive deposit som vanligt

- [ ] Scenario: Tvetydig matchning löses med textöverlappning
      Given flera kandidatrader med samma belopp och inom datumfönstret
      And exakt en av kandidaterna har en text som är en delsträng av den
      andra radens text (skiftlägesokänsligt)
      When importen körs
      Then den kandidaten paras ihop och postas som transfer
      And övriga kandidater postas som vanligt

- [ ] Scenario: Tvetydig matchning utan entydig textöverlappning postas som vanligt
      Given flera kandidatrader med samma belopp och inom datumfönstret
      And ingen, eller mer än en, av kandidaterna har textöverlappning
      When importen körs
      Then ingen av kandidaterna paras ihop
      And samtliga postas som withdrawal/deposit som vanligt

- [ ] Scenario: Enstaka mappimport påverkas inte
      Given endast en kontomapp importeras i körningen (UC-1)
      When importen körs
      Then ingen cross-account-matchning görs
      And samtliga rader postas som withdrawal/deposit som idag

- [ ] Scenario: Dry-run visar planerade transfers utan att posta
      Given rader som skulle matchas som en överföring
      When importen körs med `--dry-run`
      Then de planerade transfer-paren loggas
      And omatchade/tvetydiga rader loggas separat
      And inga transaktioner postas

- [ ] Scenario: Kvalitetsgrindar
      When `make lint && make test` körs
      Then båda passerar
      And testtäckningen understiger inte baslinjen vid taskstart

## Out of scope

- Konvertering av redan importerade withdrawal/deposit-par till transfer i
  efterhand (engångsskript mot redan existerande data) — separat, ej
  planerad task tills vidare.
- Textmatchning som primärt kriterium — används endast som tiebreaker vid
  flera kandidater inom belopp/datum-fönstret, inte som ett fristående
  matchningsvillkor.
- Överföringar till/från konton som inte ingår i den aktuella
  importkörningen (dvs. bara en sida av överföringen importeras) — dessa
  rader postas som vanlig withdrawal/deposit, precis som idag.

## Blockers

Beror på TASK-053 (automatisk startsaldo-detektering) endast i den
meningen att båda ändrar samma importflöde (`process_folder`/`process_csv`)
— ingen hård blockering, men TASK-053 bör landas och mergas till `main`
före denna task påbörjas för att undvika stora sammanslagningskonflikter i
`import_firefly.py`.

## Completion

_Not yet completed._
