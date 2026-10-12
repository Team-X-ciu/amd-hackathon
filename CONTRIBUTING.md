# Contributing

How the three of us work in this repo. Read it once before your first task.

## 1. Start every task from the latest `main`

```bash
git checkout main
git pull origin main
git checkout -b <branch-name>
```

Starting from an old `main` is the most common cause of merge conflicts.

## 2. Branch names

Every task gets its own branch. Nobody pushes to `main` directly (the ruleset blocks it).

```
<name>/<type>/<short-description>
```

| Type | Use for |
| --- | --- |
| `feat` | new feature |
| `fix` | bug fix |
| `docs` | documentation |
| `chore` | setup, config, dependencies |
| `refactor` | restructuring without changing behaviour |
| `test` | tests only |

Examples:

```
abror/feat/classifier-training
abror/chore/amd-rocm-setup
<backend-name>/feat/inspections-endpoint
<frontend-name>/fix/mask-overlay-scaling
```

## 3. Commit messages

[Conventional Commits](https://www.conventionalcommits.org/) format, with the area in brackets:

```
<type>(<area>): <what changed>
```

Areas: `ml`, `backend`, `frontend`, `contracts`, `infra`, `docs`.

```
feat(ml): add autoencoder anomaly gate
fix(backend): handle ML service timeout on /explain
docs(contracts): add defect_type enum
chore(infra): add Postgres healthcheck to compose
```

Small, focused commits. Present tense, lowercase, no full stop.

## 4. Before opening a pull request: test it

- Check that what you built matches the issue.
- Run it locally: the service on its own, or `docker compose up` for the whole app.
- Run the checks CI will run:
  - ML: `uv run ruff check app && uv run ruff format --check app`
  - Backend: `npm run typecheck`
  - Frontend: `npm run build`
- If you changed a contract: regenerate types on both sides (`npm run gen:types`).

Don't open a PR for something you haven't run yourself.

## 5. Pull requests

```bash
git push -u origin <branch-name>
```

Then open a PR into `main` on GitHub.

- **Title:** issue number first, then what it does: `Closes #24 - Add classifier training on MVTec AD`.
  GitHub copies the title into the merge commit, so the issue closes when the PR is merged.
  `Fixes #` and `Resolves #` work too.
- Keep PRs small. Merge at least once a day; don't sit on a branch for days.

Copy this into every PR description and fill it in:

```markdown
## What
<one or two lines on what this PR does>

## Area
ml / backend / frontend / contracts / docs

## Checklist
- [ ] Tested locally (service on its own, or `docker compose up`)
- [ ] Lint / typecheck / build pass locally
- [ ] If a contract changed: types regenerated on both sides
- [ ] No secrets, datasets or model weights committed
```

## 6. Merge rules

- CI must be green.
- One approval from a teammate.
- **Contract changes (`contracts/`) need all three people to review**, because they change
  everyone's code. Change the contract in its own PR, before the code that uses it.
- If your branch has conflicts, you resolve them on your branch:
  ```bash
  git checkout main && git pull origin main
  git checkout <branch-name> && git merge main
  # fix conflicts, test again, then push
  ```
- Delete the branch after merging.

## 7. Never commit

- `.env` or any API key, token or password. Add new variables to `.env.example` with a dummy value.
- Datasets (`ml-service/data/`). Link to them in the README instead; some licences forbid redistribution.
- Model weights (`*.pt`, `*.pth`, `*.safetensors`). Upload to Hugging Face and link.
- `node_modules/`, `.venv/`, `dist/`.

If you committed a secret by mistake, tell the team immediately and revoke the key; deleting the file is not enough.
