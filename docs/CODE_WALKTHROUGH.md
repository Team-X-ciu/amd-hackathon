# Code walkthrough

What every file in the starting repo does, and how the pieces connect.
Read [GETTING_STARTED.md](GETTING_STARTED.md) first for setup; this file explains the code itself.

- [1. The big picture: one request, end to end](#1-the-big-picture-one-request-end-to-end)
- [2. Root files](#2-root-files)
- [3. Contracts](#3-contracts)
- [4. ML service (Python, FastAPI)](#4-ml-service-python-fastapi)
- [5. Backend (Node, Express, TypeScript)](#5-backend-node-express-typescript)
- [6. Frontend (React, Vite, TypeScript)](#6-frontend-react-vite-typescript)
- [7. GitHub: CI and templates](#7-github-ci-and-templates)
- [8. What is real and what is a placeholder](#8-what-is-real-and-what-is-a-placeholder)

---

## 1. The big picture: one request, end to end

What happens today when an operator uploads an image on http://localhost:5173:

```
1. Browser (frontend/src/App.tsx)
   user picks a file → FormData with "image" → POST /api/inspections

2. Vite dev server (frontend/vite.config.ts)
   /api/... is proxied to the backend on port 3000

3. Backend (backend/src/index.ts)
   multer reads the file into memory → mlInspect(...) in ml-client.ts
   → POST http://ml-service:8000/inspect (multipart)

4. ML service (ml-service/app/main.py → stub.py)
   checks size and format → stub.inspect() returns a fake but realistic
   InspectResult: anomaly score, defect type, severity, mask as base64 PNG

5. Back up the chain
   backend returns { vision } → App.tsx draws the image, the red mask on top,
   and the numbers
```

Two rules hold everywhere:

- **The frontend only talks to the backend.** The ML service is internal.
- **The data shapes are defined in `contracts/`**. Python models and TypeScript types follow them.

---

## 2. Root files

| File | What it does |
| --- | --- |
| `README.md` | Front page: what the product is, architecture, layout, quick start, AMD notes, results (to fill in). |
| `LICENSE` | MIT licence. lablab requires MIT-compatible submissions. |
| `.gitignore` | Keeps out of git: secrets (`.env`), installed packages (`node_modules/`, `.venv/`), build output (`dist/`), datasets (`ml-service/data/*`), model weights (`*.pt`, `*.pth`, …), uploads. The `.gitkeep` files keep the empty `data/` and `models/` folders in the repo. |
| `.env.example` | Template for `.env`. Every setting the services read: database login, `ML_SERVICE_URL`, `ML_STUB`, LLM endpoint and model, `VITE_API_URL`. Copy it to `.env`; never commit `.env`. |
| `docker-compose.yml` | Starts all four services with one command (details below). |
| `CONTRIBUTING.md` | Team workflow: branches, commits, PRs, merge rules, what never to commit. |
| `docs/TASKS.md` | The original day-by-day plan and cut list. The GitHub issues are now the live version. |
| `docs/GETTING_STARTED.md` | Install tools, setup, first steps per role, how to use the contracts. |

### docker-compose.yml

Four services, each in its own container, on a shared private network where they reach each
other by service name (`db`, `ml-service`, `backend`):

| Service | Built from | Port | Notes |
| --- | --- | --- | --- |
| `db` | image `pgvector/pgvector:pg16` (Postgres 16 + vector extension) | 5432 | Runs `backend/db/init.sql` on first start. Data kept in the `db-data` volume. Has a healthcheck (`pg_isready`). |
| `ml-service` | `ml-service/Dockerfile` | 8000 | `ML_STUB` and LLM settings from `.env`. Mounts `models/` and `manuals/` so weights and manuals can change without rebuilding. |
| `backend` | `backend/Dockerfile` | 3000 | Gets `DATABASE_URL` and `ML_SERVICE_URL`. `depends_on` waits for the database to be healthy. |
| `frontend` | `frontend/Dockerfile` | 5173 → 80 | `VITE_API_URL` is passed as a build argument, because Vite bakes it into the JavaScript at build time. |

`${POSTGRES_USER:-app}` means: use the value from `.env`, or `app` if it isn't set.

---

## 3. Contracts

`contracts/` holds two OpenAPI 3.1 files. They are the agreement between the three parts.

### `ml-service.openapi.yaml` (backend → ML service)

| Endpoint | Request | Response |
| --- | --- | --- |
| `GET /health` | – | `Health`: status, which models are loaded, the GPU in use, stub flag |
| `POST /inspect` | multipart: `image` (+ optional `part_type`) | `InspectResult` |
| `POST /explain` | JSON `ExplainRequest` | `Explanation` |

Key schemas:

- **`InspectResult`**: `anomaly_score` and `anomaly_threshold` (from the anomaly detector),
  `is_defective`, `defect_type` and `defect_confidence` (classifier), `severity`
  (`none/low/medium/high`), `defect_area_ratio`, `bounding_boxes`, `mask_png_base64`,
  optional `heatmap_png_base64`, `model_versions`, `latency_ms`.
- **`ExplainRequest`**: the defect (type, severity, score, area), optional `question` and
  chat `history` for follow-ups.
- **`Explanation`**: `summary`, `likely_causes`, `recommended_action`, `priority`
  (`low/medium/high/stop_line`), optional `answer`, `sources` (manual sections cited),
  `needs_human_review`.
- **`Error`**: `{ error, detail }`, used by every error response.

### `backend.openapi.yaml` (frontend → backend)

Built around one object, **`Inspection`**: `id`, `status`, line and part, `image_url`,
`created_at`, and three parts that fill in over time: `vision` (copied from the ML result, with
the mask stored as a file and exposed as `mask_url`), `explanation`, `decision`, plus `chat`.

`status` moves through: `explaining` → `explained` → `decided` for a defective board (good boards stay
`inspected`). The explanation runs in the background after the upload; if it fails the status is
`explain_failed` and it can be retried. `failed` means the vision step itself failed.

Endpoints, grouped:

| Group | Endpoints |
| --- | --- |
| Inspections | `POST /inspections` (upload), `GET /inspections` (filters + cursor paging), `GET /inspections/{id}`, `/image`, `/mask` |
| Agent | `POST /inspections/{id}/explain` (retry, answers `202`), `POST /inspections/{id}/chat` |
| Operator | `POST /inspections/{id}/decision` (accept / reject / rework, records `time_to_decision_ms`) |
| Dashboard | `GET /stats` (counts, rates, averages), `/simulator`, `/simulator/start`, `/simulator/stop` |
| Live | `GET /events`: Server-Sent Events `inspection.created`, `.explained`, `.explain_failed`, `.decided` |
| Ops | `GET /health` (backend + ML status) |

`contracts/README.md` lists the rules for changing contracts and the open decisions.

---

## 4. ML service (Python, FastAPI)

### Project files

| File | What it does |
| --- | --- |
| `scripts/gen-schemas.sh` | Regenerates `app/schemas.py` from the contract. |
| `pyproject.toml` | Python project definition for uv. `dependencies` = the API layer (FastAPI, uvicorn, python-multipart for uploads, Pydantic, Pillow). `[project.optional-dependencies] ml` = models and agent (numpy, OpenCV, albumentations, anomalib for PatchCore, timm, scikit-learn, sentence-transformers, FAISS, pypdf, openai, LangGraph). `[dependency-groups] dev` = httpx (for tests), ruff (linter/formatter) and datamodel-code-generator (schemas from the contract). |
| `uv.lock` | Exact versions of every package. Commit it with every dependency change. |
| `.python-version` | `3.12`: uv downloads and uses this Python version. |
| `Dockerfile` | CPU / stub image: `python:3.12-slim` + the uv binary, installs only the locked API dependencies (`uv sync --locked --no-dev --no-install-project`), copies the code, runs `uvicorn app.main:app` on port 8000. Dependencies are installed before copying code, so code changes don't reinstall packages. |
| `Dockerfile.rocm` | GPU image for AMD: starts from `rocm/pytorch` (ROCm torch preinstalled) and installs the `ml` extra **into that Python** with `uv pip install --system`, so the ROCm torch is kept. The build fails if torch is not the ROCm build. |
| `.dockerignore` | Keeps `.venv`, data and weights out of the Docker build. |
| `manuals/README.md` | What the QC manual sections should contain. The agent will search this folder. |

**Why torch isn't a normal dependency:** `pip`/`uv` would install the NVIDIA (CUDA) build from
PyPI, which can't use AMD GPUs. On AMD we use the torch that comes with AMD's image.

### `app/config.py`

Reads settings from environment variables once, at import:

- `STUB`: `True` when `ML_STUB=1` (the default).
- `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`: where the LLM lives (vLLM or another OpenAI-compatible API).
- `MODELS_DIR`, `MANUALS_DIR`: where weights and manuals are.
- `ANOMALY_THRESHOLD`: default `0.5`.
- `DEFECT_TYPES`: placeholder list until the dataset is chosen.
- `MAX_IMAGE_BYTES`: 10 MB upload limit.

### `app/schemas.py` (generated)

**Generated** from `ml-service.openapi.yaml` by `scripts/gen-schemas.sh`
([datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator)), the same way
the TypeScript types are generated on the other side. Never edit it by hand; CI regenerates it and
fails if it differs. Models: `BoundingBox`,
`ModelVersions`, `InspectResult`, `ChatTurn`, `ExplainRequest`, `Source`, `Explanation`,
`ModelsLoaded`, `Health`, `Error`.

They do two jobs: FastAPI **validates** incoming requests against them (wrong JSON → 400), and
**serialises** responses through them, so a response can't silently drift from the contract.
`Literal["none", "low", ...]` restricts a field to fixed values, like an enum.
`str | None = None` means the field may be missing. The endpoints use
`response_model_exclude_none=True`, so fields that are `None` are left out of the JSON instead of
being sent as `null` (the contract allows optional fields to be absent, not null).

### `app/stub.py`

Fake results in the exact contract shape, so the backend and frontend can be built before any model exists.

- **Deterministic:** the random generator is seeded with the SHA-256 hash of the image bytes
  (`random.Random(hashlib.sha256(raw).hexdigest())`). The same image always gives the same result,
  so bugs are reproducible.
- **`inspect()`**: about 35% of images come back defective. For those it picks a random ellipse
  inside the image, draws it into a black-and-white mask with Pillow, computes the share of pixels
  it covers (`defect_area_ratio`), turns that into a severity with `_severity()`
  (`< 1%` low, `< 5%` medium, otherwise high), and encodes the mask as base64 PNG.
  Good parts get a low anomaly score and `severity: none`.
- **`explain()`**: returns a fixed explanation marked `[STUB]`, with the severity mapped to a
  priority, a fake manual source, an answer if a question was asked, and
  `needs_human_review` when severity is high.

### `app/main.py`

The FastAPI app and its three endpoints.

- **`_device()`**: reports the GPU for `/health`. It tries to import torch; ROCm builds also use
  the `torch.cuda` API, and `torch.version.hip` tells ROCm apart from CUDA. Without torch it says
  so, which is the case in stub mode.
- **Two exception handlers**: turn FastAPI's validation errors (normally 422) and `HTTPException`s
  into the contract's `Error` shape with status 400 / the given status.
- **`GET /health`**: in stub mode reports everything loaded; otherwise everything false until the
  real status check is written (`TODO`).
- **`POST /inspect`**: reads the upload, rejects files over 10 MB, opens it with Pillow
  (rejects non-images with 400), then calls `stub.inspect()` in stub mode. The real pipeline is a
  `TODO`.
- **`POST /explain`**: validates the JSON into `ExplainRequest`, calls `stub.explain()` in stub
  mode; the agent is a `TODO` (returns 503 until then).

`Annotated[UploadFile, File(...)]` is FastAPI's way to declare "this parameter comes from a
multipart file field".

**One thing to change with real models:** `/inspect` is `async def`. Model inference is heavy
computation, and inside an `async def` it blocks the whole server. Make it a plain `def` (FastAPI
then runs it in a thread pool) or call the model with `run_in_threadpool`.

---

## 5. Backend (Node, Express, TypeScript)

### Project files

| File | What it does |
| --- | --- |
| `package.json` | Dependencies: **express** (web framework), **multer** (file uploads), **cors** (lets the browser call the API from another port), **postgres** (postgres.js database client). Dev dependencies: **typescript** (pinned to 5), **tsx** (runs TS directly in dev), **@types/…**, **openapi-typescript** (type generator). Scripts: `dev`, `build`, `start`, `typecheck`, `gen:types`. |
| `package-lock.json` | Exact package versions. |
| `tsconfig.json` | Compiles `src/` to `dist/` as modern ES modules (`NodeNext`), strict type checking on. |
| `Dockerfile` | Two stages: the first installs everything and compiles TypeScript; the second installs only production packages and copies the compiled `dist/`. Smaller, cleaner image. |
| `db/init.sql` | Database schema (below). |

Imports in `src/` end in `.js` (`from "./db.js"`) even though the files are `.ts`: with Node's
ES modules, you import the name of the *compiled* file.

### `src/api/types.ts` and `src/api/ml-types.ts` (generated)

Created by `npm run gen:types` from the two contracts. Never edit by hand; CI fails if they don't
match the contracts. Use them like `components["schemas"]["Inspection"]`.

### `src/ml-client.ts`

Typed functions for calling the ML service:

- Type aliases taken from the generated ML types (`InspectResult`, `Explanation`, …).
- `call()` is the shared helper: `fetch` with a timeout (`AbortSignal.timeout(ML_TIMEOUT_MS)`,
  default 30 s); on a non-2xx response it throws `MlError` with the status and the ML service's
  error message.
- `mlHealth()`, `mlInspect(image, filename, mimetype, partType)` (builds a multipart `FormData`
  with the image as a `Blob`), `mlExplain(req)` (JSON).

Node 18+ has `fetch`, `FormData` and `Blob` built in, so no HTTP library is needed.

### `src/db.ts`

Creates one shared database connection pool from `DATABASE_URL` (max 10 connections). Queries
are written as tagged templates, ``sql`select * from inspections where id = ${id}` ``; values
in `${}` are sent as parameters, which protects against SQL injection.

### `src/index.ts`

The Express app.

- **Setup:** `multer` with in-memory storage and a 10 MB limit; `cors()`; `express.json()` to
  parse JSON bodies; all routes on a router mounted at `/api`.
- **`GET /api/health`**: asks the ML service for its health and runs `select 1` on the database;
  `ok` only if both work, otherwise `degraded`. Also passes the ML service's GPU description through.
- **`POST /api/inspections`** (day-1 spike): takes the uploaded `image`, forwards it with
  `mlInspect`, returns `{ vision }`. Not saved to the database yet, and not yet the contract's
  `Inspection` shape. ML failures return 502.
- **Every other contract route** is registered and returns `501 Not implemented`, so the list of
  work is visible in one place.

### `src/docs.ts`

Interactive API docs at **`/docs`** (Swagger UI, like FastAPI's `/docs`) and the raw spec at
`/openapi.json`. It reads the **contract** (`contracts/backend.openapi.yaml`, path from
`OPENAPI_PATH`; docker compose mounts `contracts/` at `/contracts`), so the page shows the agreed
API including routes not built yet (they answer 501 in "Try it out"). FastAPI builds its docs
from the code; here the contract comes first, so the docs come from the contract. If the file
can't be read, the docs are skipped with a warning and the API still starts.

### `db/init.sql`

Three tables, mirroring the contract:

- **`inspections`**: one row per inspected part. `status` limited to the six contract values by
  a `check` constraint; file paths for image, mask and heatmap; `vision` and `explanation` stored
  as **`jsonb`** (the ML results as JSON, queryable); `created_at`. Indexes on time and line for
  the history and stats queries.
- **`decisions`**: one per inspection (primary key = `inspection_id`): decision, whether the
  operator followed the recommendation, note, operator, time, `time_to_decision_ms`.
- **`chat_messages`**: follow-up conversation per inspection, with sources.

`references inspections (id) on delete cascade` = deleting an inspection deletes its decision and chat too.

---

## 6. Frontend (React, Vite, TypeScript)

Created with `npm create vite` (React + TypeScript template), then trimmed and configured.

| File | What it does |
| --- | --- |
| `package.json` | React 19, TanStack Query (server data), openapi-fetch (typed API client), react-router-dom (pages), Recharts (charts); Tailwind v4 and the Vite plugins as dev tools. `gen:types` script. |
| `vite.config.ts` | Plugins: React and Tailwind. Alias `@` → `src/` (for shadcn/ui). **Dev proxy:** `/api` → `http://localhost:3000`, so the browser calls the same origin and no CORS setup is needed in dev. |
| `tsconfig*.json` | Vite's TypeScript settings, plus the `@/*` path alias. |
| `index.html` | The single HTML page; React mounts into `<div id="root">`. Title "Defect Copilot". |
| `Dockerfile` | Builds the app with Node (with `VITE_API_URL` baked in), then serves the static files with nginx. The nginx rule `try_files $uri /index.html` makes page routes work on reload. |
| `.oxlintrc.json` | Linter settings from the Vite template. |

### `src/index.css`

`@import "tailwindcss"` loads Tailwind v4. The `@theme` block adds three status colours,
`ok` (green), `review` (amber), `defect` (red), usable as classes like `text-defect` or
`bg-ok/15`. The page background is dark (`bg-zinc-950`), for factory screens.

### `src/main.tsx`

Entry point: creates one TanStack Query `QueryClient` and wraps the app in its provider, inside
React's `StrictMode` (which runs extra checks in development).

### `src/api/client.ts`

`createClient<paths>()` from openapi-fetch, typed with the generated `paths`. Calls like
`api.GET('/inspections/{id}', { params: { path: { id } } })` are checked against the contract
at compile time. Base URL is `VITE_API_URL`, or `/api` (the dev proxy). Also exports handy type
aliases: `Inspection`, `VisionResult`, `Explanation`, `Stats`.

### `src/App.tsx` (day-1 test screen, to be replaced)

- **Health badge:** `useQuery` fetches `/health` every 10 s and shows backend status, ML status
  and the GPU.
- **Upload:** a hidden file input inside a label styled as a drop zone. On change it shows a
  local preview (`URL.createObjectURL`) and runs a `useMutation` that posts the image as
  `FormData` to `/inspections`.
- **Result:** the image, and on top of it a red `div` that uses the mask PNG as a CSS
  **luminance mask** (`maskImage` + `maskMode: 'luminance'`): white mask pixels let the red
  through, black ones hide it, so only the defect area turns red. Next to it a status badge
  (green OK, amber low/medium, red high) and the numbers.
- It reads the backend spike's `{ vision }` shape through a local `SpikeResult` type. When the
  backend returns the full `Inspection`, switch to the typed client.

---

## 7. GitHub: CI and templates

### `.github/workflows/ci.yml`

Runs on every push to `main` and every pull request. Four independent jobs:

| Job | Checks |
| --- | --- |
| `contracts` | Both OpenAPI files are valid (`openapi-spec-validator`). |
| `ml-service` | `uv sync --locked` (lock file up to date), ruff lint + format check, regenerated `schemas.py` matches the committed one, then a smoke test: starts the app with FastAPI's `TestClient` in stub mode and calls `/health`, `/inspect` with a generated image, `/explain`. |
| `backend` | `npm ci`, regenerates the types and fails if they differ from the committed ones (`git diff --exit-code`), then `tsc --noEmit`. |
| `frontend` | `npm ci`, the same generated-types check, then a full production build. |

Together they catch: broken contracts, contract changes without updated types, type errors,
lint/format issues, and a service that doesn't start.

### Templates

- `ISSUE_TEMPLATE/task.md` and `bug.md`: forms for new issues (area, what, done when / steps to reproduce).
- `pull_request_template.md`: pre-fills every PR description with what / area / checklist.

---

## 8. What is real and what is a placeholder

| Real and working | Placeholder (an issue covers it) |
| --- | --- |
| Contracts, generated TypeScript types and Pydantic models | Vision models in `/inspect` (stub) |
| ML service API, validation, error shapes | Agent in `/explain` (stub) |
| Backend → ML call with timeout and error handling | `/health` real model status in the ML service |
| Database schema | Saving inspections; every backend route except health and the upload spike |
| Upload → mask overlay test screen | The three real screens |
| Docker setup for all services | Deployment, fallback mode |
| CI | Contract tests (Schemathesis), end-to-end test |

Outside the repo there is also `create-issues.sh`, the one-off script that created the 38
GitHub issues and labels and added them to the project board, with retries for unstable
connections. It isn't needed again.
