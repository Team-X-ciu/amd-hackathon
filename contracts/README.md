# API contracts

These two files are the source of truth for how the three parts talk to each other.

| File | Provider | Consumer |
| --- | --- | --- |
| `backend.openapi.yaml` | backend (Node) | frontend |
| `ml-service.openapi.yaml` | ML service (FastAPI) | backend |

## Rules

1. Change a contract **before** changing code, in its own pull request.
2. All three people review contract PRs.
3. After a change, regenerate types on the consuming side and fix the compile errors.
4. Prefer adding optional fields over renaming or removing fields.

## Open decisions

- [ ] Final `defect_type` list — depends on the dataset. Fill in here and in both contracts as an `enum`.
- [ ] `part_type` values (one product or several).
- [ ] Severity thresholds (area ratio → low / medium / high).

## Validate

```bash
pip install openapi-spec-validator
openapi-spec-validator contracts/*.yaml
```

## Mock server for the frontend

```bash
npx @stoplight/prism-cli mock contracts/backend.openapi.yaml -p 4010
```
