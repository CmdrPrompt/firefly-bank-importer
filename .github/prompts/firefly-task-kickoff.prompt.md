---
name: Firefly Task Kickoff
description: "Start a firefly-bank-importer task with TASK-ID, requirement-scope clarification, and requirements-confirmation gate handling."
argument-hint: "TASK-ID=TASK-XXX; change=<what to build/change>; requirements-approved=yes|no"
agent: "Firefly Workflow Guardian"
---

Run the firefly-bank-importer workflow gate process for this request:

{{input}}

Required behavior:
- Extract TASK-ID, requested change, and requirements approval status from input.
- Report current branch and whether it matches task branch policy.
- If requirements are not approved:
  - Propose exact requirements/use-case updates for docs/REQUIREMENTS_import_firefly.md.
  - Ask exactly: "Is this what you intended?"
  - Stop before implementation.
- If requirements are approved:
  - Continue with task-file and branch gate checks.
  - Proceed via implementation worker and include test/check commands.
