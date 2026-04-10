# TASK-045 Cross-Repo Sync Checklist

Purpose: Publish TASK-045 changes to both repositories in the correct order.

Scope:
- Source workspace repo: firefly-bank-importer
- Shared repo: python-commons

## 0. Preconditions

- [ ] You are in the firefly-bank-importer workspace root.
- [ ] Current branch is task/045-generalize-commons-governance-and-ci.
- [ ] Local branch is clean.

Run:

```bash
git branch --show-current
git status --short
```

Expected:
- branch output: task/045-generalize-commons-governance-and-ci
- status output: empty

## 1. Push TASK-045 branch to firefly-bank-importer

- [ ] Push the task branch.

```bash
git push -u origin task/045-generalize-commons-governance-and-ci
```

- [ ] Open PR in firefly-bank-importer.

```bash
gh pr create \
  --base main \
  --head task/045-generalize-commons-governance-and-ci \
  --title "TASK-045 Generalize commons governance templates and reusable CI baseline" \
  --body "Implements TASK-045: shared governance templates, generation flow, and reusable CI wrapper model."
```

## 2. Publish only .commons history to python-commons

- [ ] Create subtree split branch from .commons.

```bash
git subtree split --prefix=.commons -b commons-sync-task-045
```

- [ ] Ensure python-commons remote exists.

```bash
git remote -v
```

If missing, add it:

```bash
git remote add python-commons https://github.com/CmdrPrompt/python-commons.git
```

- [ ] Push split branch to python-commons task branch.

```bash
git push python-commons commons-sync-task-045:task-045-governance-ci
```

## 3. Create and merge PR in python-commons

- [ ] Open PR against python-commons main.

```bash
gh pr create \
  --repo CmdrPrompt/python-commons \
  --base main \
  --head task-045-governance-ci \
  --title "Generalize governance templates and reusable CI baseline" \
  --body "Exports TASK-045 .commons updates from firefly-bank-importer via subtree split."
```

- [ ] Wait for checks/review, then merge PR in python-commons.

Optional merge command:

```bash
gh pr merge --repo CmdrPrompt/python-commons --squash --delete-branch
```

## 4. Pull merged python-commons back into firefly-bank-importer

- [ ] Switch to TASK-045 branch in firefly-bank-importer.

```bash
git checkout task/045-generalize-commons-governance-and-ci
```

- [ ] Pull latest .commons from python-commons main.

```bash
git subtree pull --prefix=.commons https://github.com/CmdrPrompt/python-commons.git main --squash
```

- [ ] Regenerate governance files from templates.

```bash
make generate-governance-files
```

- [ ] Run quality gates.

```bash
make lint && make test
```

## 5. Commit any reconciliation changes in firefly-bank-importer

Only if subtree pull or regeneration changed files.

- [ ] Check for changes.

```bash
git status --short
```

- [ ] If changed, update task metadata and commit via project workflow:

```bash
make stage-current-task
make commit-current-task
```

- [ ] Push updated task branch.

```bash
git push
```

## 6. Final merge order

- [ ] Ensure python-commons PR is merged first.
- [ ] Then complete and merge firefly-bank-importer PR.

Optional command in firefly-bank-importer after PR is ready:

```bash
make merge-current-task
```

## 7. Cleanup (optional)

- [ ] Remove temporary local split branch.

```bash
git branch -D commons-sync-task-045
```
