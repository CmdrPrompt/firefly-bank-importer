# TASK-031 Fix paginering avbryts vid saknad pagination-metadata

## Status
todo

## Description
I `fetch_accounts_from_firefly()` (rad 70 i `import_firefly.py`) defaultar `total_pages`
till 1 om `meta.pagination` saknas i API-svaret. Eftersom `page` börjar på 1 avslutas
paginerings-loopen direkt efter första sidan — även om det finns fler. Detta bryter
FR-18 (hämta alla asset-konton) och UC-8 steg 1.

```python
pagination = data.get("meta", {}).get("pagination", {})
if page >= pagination.get("total_pages", 1):
    break
```

Felet kan triggas vid API-versionsmismatch eller oväntad responsstruktur.

## Branch
**Branch name:** `task/031-fix-pagination-cutoff`
**Switch/create:** `git checkout -b task/031-fix-pagination-cutoff`
**Make target:** `make branch-task f=TASK-031`

## Acceptance criteria
- [ ] Om `meta.pagination` saknas i API-svaret hanteras det explicit (t.ex. logga varning och fortsätt/avbryt med tydligt felmeddelande)
- [ ] Paginerings-loopen avslutas inte i förtid när `total_pages` inte kan läsas
- [ ] Test täcker scenariot att `meta.pagination` saknas i API-svaret

## Completion
**Date:**
**Summary:**
**Files changed:**
**Branch:** `git checkout -b task/031-fix-pagination-cutoff`
**Stage:** `git add docs/tasks/TASK-031-fix-pagination-cutoff.md`
**Commit:** `git commit -m "Fix pagination cutoff when meta.pagination is missing"`
