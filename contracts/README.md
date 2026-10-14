# API contracts

These two files are the source of truth for how the three parts talk to each other.

| File | Provider | Consumer |
| --- | --- | --- |
| `backend.openapi.yaml` | backend (Node) | frontend |
| `ml-service.openapi.yaml` | ML service (FastAPI) | backend |

## Rules

1. Change a contract **before** changing code, in its own pull request.
2. All three people review contract PRs.
3. After a change, regenerate on both sides and fix what breaks: `npm run gen:types` (backend, frontend) and `./scripts/gen-schemas.sh` (ml-service).
4. Prefer adding optional fields over renaming or removing fields.

## Open decisions

- [x] `defect_type`: `bent`, `melt`, `scratch`, `missing`, `unknown` (VisA pcb1), an `enum` in both contracts
- [x] `part_type`: `pcb1`
- [x] Severity: `missing` always high; otherwise by area, < 1% low, 1–5% medium, > 5% high

See [`docs/DECISIONS.md`](../docs/DECISIONS.md).

## Validate

```bash
pip install openapi-spec-validator
openapi-spec-validator contracts/*.yaml
```

## Mock server for the frontend

```bash
npx @stoplight/prism-cli mock contracts/backend.openapi.yaml -p 4010
```
