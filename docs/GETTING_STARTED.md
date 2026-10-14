# Getting started

Read this once on day one. It takes about 20 minutes, then you can build.

- [The idea in one minute](#the-idea-in-one-minute)
- [Everyone: install the tools](#everyone-install-the-tools)
- [Everyone: setup](#everyone-setup)
- [The contracts, and how to use them](#the-contracts-and-how-to-use-them)
- [Backend: first steps](#backend-first-steps)
- [Frontend: first steps](#frontend-first-steps)
- [ML and tech lead: first steps](#ml-and-tech-lead-first-steps)
- [Daily routine](#daily-routine)

---

## The idea in one minute

An operator on a factory line uploads (or the camera sends) an image of a part. The app:

1. **Inspects it** — ML models decide if the part is defective, mark *where* the defect is
   (a mask) and *what* it is (bent, melt, scratch, missing component…).
2. **Explains it** — an AI agent reads the plant's QC manual and says what probably caused the
   defect and what to do, citing the manual section.
3. **Records the decision** — the operator accepts, rejects or sends the part to rework.

Three parts, one owner each:

```
Frontend (React)  ──►  Backend (Node/Express)  ──►  ML service (FastAPI, AMD GPU)
                          │
                          ▼
                       Postgres
```

The frontend never calls the ML service directly. Everything goes through the backend.

---

## Everyone: install the tools

| Tool | Who needs it | Why |
| --- | --- | --- |
| Git | everyone | clone, branch, push |
| Docker + Docker Compose | everyone | run the whole app (Postgres, ML stub, backend, frontend) with one command |
| Node 22 (+ npm) | backend, frontend | run and build the TypeScript code |
| uv | ML | Python packages and Python itself for `ml-service` |

You don't need to install Python: uv downloads the right version (3.12) by itself.
With only Git and Docker you can already run the full app.

### Ubuntu / Debian (and Windows via WSL)

```bash
# Git
sudo apt update && sudo apt install -y git curl

# Docker Engine + Compose plugin
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER      # run docker without sudo; log out and back in after this

# Node 22 via nvm (lets you switch Node versions per project)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
source ~/.bashrc
nvm install 22

# uv (ML only)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### macOS

```bash
# Homebrew first, if you don't have it: https://brew.sh
brew install git node@22 uv
brew install --cask docker         # Docker Desktop; open it once so it starts
```

### Windows

Use **WSL2 with Ubuntu**, then follow the Ubuntu steps inside it. Install it from PowerShell
(as administrator): `wsl --install`, restart, open "Ubuntu" from the Start menu.

- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) on Windows and turn on
  *Settings → Resources → WSL integration* for Ubuntu. Then skip the Docker step inside Ubuntu.
- Clone the repo **inside** the Ubuntu home folder (`~/`), not under `/mnt/c/...`;
  it's much faster and avoids line-ending problems.

### Check everything

```bash
git --version
docker --version && docker compose version
docker run --rm hello-world        # Docker works without sudo
node -v                            # v22.x
npm -v
uv --version                       # ML only
```

Also set your Git name and email once, so commits show who made them:

```bash
git config --global user.name "Your Name"
git config --global user.email "you@example.com"   # the email on your GitHub account
```

Pushing over HTTPS asks for a **personal access token**, not your GitHub password
(GitHub → Settings → Developer settings → Personal access tokens), or log in once with the
[GitHub CLI](https://cli.github.com/): `gh auth login`.

---

## Everyone: setup

```bash
git clone https://github.com/Team-X-ciu/amd-hackathon.git
cd amd-hackathon
cp .env.example .env
docker compose up --build
```

Check it works:

| Open | You should see |
| --- | --- |
| http://localhost:5173 | the upload screen; upload any PNG/JPEG → a result appears |
| http://localhost:3000/api/health | `"ml_service": "ok"` |
| http://localhost:8000/docs | the ML service's interactive API docs |

The ML service runs in **stub mode**: it returns fake but realistic results, so nobody waits for
the models. Same image → same result, which makes bugs reproducible.

Then read [`CONTRIBUTING.md`](../CONTRIBUTING.md) (branches, commits, PRs) and pick your first
issue from the project board.

---

## The contracts, and how to use them

### What a contract is

A contract is a file that describes an API exactly: which URLs exist, what you send, and what
you get back, field by field. We have two, in [`contracts/`](../contracts/):

| File | Describes | Provider (implements it) | Consumer (calls it) |
| --- | --- | --- | --- |
| `backend.openapi.yaml` | the backend API | Backend | Frontend |
| `ml-service.openapi.yaml` | the ML service API | ML | Backend |

They are written in **OpenAPI**, the standard format for this. Any tool that understands OpenAPI
can turn them into docs, TypeScript types or a fake server.

**Why it matters:** we agree on the data shapes *before* writing code, so each person can build
their part alone and the parts fit together on the first try.

### How to read one

Open `backend.openapi.yaml`. It has two big sections:

- **`paths`** — every endpoint. For example `POST /inspections`: takes an image, returns `201`
  with an `Inspection`.
- **`components/schemas`** — every data shape. For example `Inspection` has `id`, `status`,
  `vision`, `explanation`, `decision`…

Easier: paste the file into https://editor.swagger.io to see it as clickable docs.

### The flow through both contracts

```
Frontend                    Backend                         ML service
POST /inspections  ───────► saves image ──────────────────► POST /inspect
                            saves result ◄───────────────── InspectResult (score, mask, type)
◄─── Inspection (status: explaining)        good board: status inspected, done here

                            in the background:
                            ───────────────────────────────► POST /explain
                            saves explanation ◄──────────── Explanation (summary, action, sources)
◄─── event inspection.explained  (status: explained)
     or inspection.explain_failed (status: explain_failed → POST /inspections/{id}/explain retries)

POST /inspections/{id}/decision ─► saves decision
◄─── Inspection (status: decided)
```

### How each person uses them

| You are | You do |
| --- | --- |
| **Frontend** | Generate types from `backend.openapi.yaml`. Build against a mock server until the backend is ready. |
| **Backend** | Implement `backend.openapi.yaml` exactly. Generate types from both files; use the ML types to call the ML service. |
| **ML** | Implement `ml-service.openapi.yaml` exactly. The Pydantic models in `ml-service/app/schemas.py` are generated from it. |

**Generate types** (run after every contract change):

```bash
cd backend  && npm run gen:types   # → src/api/types.ts and src/api/ml-types.ts
cd frontend && npm run gen:types   # → src/api/types.ts
cd ml-service && ./scripts/gen-schemas.sh   # → app/schemas.py (Pydantic)
```

Never edit the generated files by hand. CI fails if they don't match the contracts.

### Changing a contract

Contracts will change; that's normal. The rules:

1. **Contract first, code second.** Open a PR that changes only `contracts/`.
2. **All three people review it**, because it changes everyone's code.
3. After merging, each person regenerates types and fixes what breaks.
4. Prefer **adding an optional field** over renaming or removing one; adding breaks nobody.

If you find the contract is wrong or missing something, don't work around it in code. Tell the
team and change the contract.

---

## Backend: first steps

**Your job:** the API the frontend uses, the database, the line simulator, Docker and deployment.
Contract: `backend.openapi.yaml`.

**What's already there** (`backend/`):

- `src/index.ts` — Express app. `GET /api/health` works. `POST /api/inspections` is a
  **day-1 spike**: it forwards the image to the ML service and returns the raw result as
  `{ vision }`. Every other route returns `501 Not implemented`.
- `src/ml-client.ts` — typed functions to call the ML service: `mlInspect`, `mlExplain`, `mlHealth`.
- `src/db.ts` — Postgres connection ([postgres.js](https://github.com/porsager/postgres), plain SQL).
- `db/init.sql` — the tables: `inspections`, `decisions`, `chat_messages`. Runs when the
  Postgres container first starts. After changing it: `docker compose down -v && docker compose up`.

**Run only the backend** (faster than rebuilding Docker):

```bash
docker compose up db ml-service     # database + ML stub in Docker
cd backend && npm install && npm run dev
```

**Suggested order:**

1. `POST /inspections` for real: save the image to disk, decode `mask_png_base64` from the ML
   result and save it as a PNG, insert a row, return the full `Inspection` shape from the contract.
   (The frontend's test screen reads the spike's `{ vision }` shape; tell the frontend dev when you
   switch, so it's updated in the same PR or right after.)
2. `GET /inspections`, `GET /inspections/{id}`, `GET /inspections/{id}/image`, `.../mask`.
3. Explanations in the background: after saving a defective inspection, call `mlExplain`
   without making the request wait (status `explaining`). On success save it, set `explained`
   and send the `inspection.explained` event; on error or timeout set `explain_failed`, fill
   `error` and send `inspection.explain_failed`. `POST /inspections/{id}/explain` restarts it
   and answers `202`. Then `/chat` and `/decision`.
4. `GET /stats`, the simulator (`/simulator/*`) and live updates (`GET /events`, Server-Sent Events).

**Tips:** type your route responses with the generated types
(`components["schemas"]["Inspection"]`) so TypeScript catches mismatches. Prisma is optional;
only switch if you already know it well.

---

## Frontend: first steps

**Your job:** the operator dashboard, and the visual parts of the submission (cover image, slides,
demo video). Contract: `backend.openapi.yaml`.

**What's already there** (`frontend/`): React 19 + Vite + TypeScript + TanStack Query +
Tailwind v4. `src/App.tsx` is a test screen (upload → red mask overlay → result) that proves the
three parts connect. Replace it with the real screens. `src/api/client.ts` is a typed API client
(`openapi-fetch`) generated from the contract.

**Work without waiting for the backend** — run a mock server from the contract:

```bash
npx @stoplight/prism-cli mock contracts/backend.openapi.yaml -p 4010 --dynamic
cd frontend && VITE_API_URL=http://localhost:4010 npm run dev
```

The mock answers every endpoint with data in the right shape (`--dynamic` makes it random each
time). Note: the mock serves paths without `/api`, so `VITE_API_URL` is just `http://localhost:4010`.
When the backend is ready, run `npm run dev` without `VITE_API_URL`; the dev server proxies
`/api` to the backend on port 3000.

**Set up components:**

```bash
cd frontend
npx shadcn@latest init        # the @/ path alias is already configured
npx shadcn@latest add card table badge dialog tabs button
```

**Screens** (details in [`frontend/README.md`](../frontend/README.md)):

1. **Live line** — newest inspection large, status colour, feed from the simulator.
2. **Inspection detail** — image with mask overlay, defect type, severity, the agent's explanation
   with cited manual sections, accept / reject / rework buttons, follow-up chat.
3. **History & stats** — table with filters, defects by type, time to decision (Recharts).

**Design rules:** dark theme, large text, readable at a glance on a tablet. Green, amber and red
are only for status (OK / review / defect), never decoration.

**Use the typed client** so contract changes show up as compile errors:

```ts
const { data, error } = await api.GET('/inspections/{id}', { params: { path: { id } } })
```

---

## ML and tech lead: first steps

**Your job:** the models, the agent, the AMD setup, and owning the contracts.

### Owning the contracts

You wrote them, so you keep them right. In practice:

1. **Day-1 kickoff (15 minutes):** walk both teammates through the flow diagram above and the
   `Inspection` schema. Ask: "is anything missing for your screen / your routes?"
2. **Close the open decisions** in [`contracts/README.md`](../contracts/README.md):
   - the final `defect_type` list (from your dataset) — then make it an `enum` in both contracts
     and update `DEFECT_TYPES` in `ml-service/app/config.py`;
   - `part_type` values (one product or several);
   - severity thresholds (defect area → low / medium / high), now in `ml-service/app/stub.py`.
   Do this as one contract PR on day 1, before people build on the placeholders.
3. **Review every contract PR.** Check: is the change needed, does it break anyone, is it
   optional where it can be?
4. **Keep your service honest.** When you replace the stub with real models, the response must
   keep the same shape. Two checks:
   - `app/schemas.py` is generated from the contract, so the response models can't drift;
     CI checks it. What can still go wrong is the *values* (e.g. a model returning a defect type
     that isn't in the enum), which Pydantic rejects at runtime.
   - Later: add [Schemathesis](https://schemathesis.readthedocs.io/) to CI. It calls the running
     service using the contract and fails if any response doesn't match.

### Your build order

1. **Dataset** — VisA `pcb1` (see [`DECISIONS.md`](DECISIONS.md)): download on the GPU machine,
   keep the original masks for the defect types, never commit the data.
2. **AMD** — GPU instance on AMD Developer Cloud; check `torch.version.hip` (see
   [`ml-service/README.md`](../ml-service/README.md)). Use `Dockerfile.rocm`, not
   `uv sync --extra ml`, on the GPU machine.
3. **vLLM** — serve an open model (e.g. Qwen2.5-7B-Instruct) with the ROCm vLLM image; one test call.
4. **PatchCore, then the classifier** — PatchCore gives detection and the mask; the classifier on
   pretrained features gives the defect type. Report both on the held-out test split; the
   autoencoder is an optional baseline.
5. **Agent** — RAG over `ml-service/manuals/` + LangGraph, behind `/explain`.

Switch from stub to real per endpoint: keep `ML_STUB=1` until a model is ready, so teammates are
never blocked by a half-trained model.

---

## Daily routine

- **10-minute check-in** each day: done, next, blocked.
- **Small PRs, merged daily.** Integrate early; by day 3 the whole loop should run end to end.
- **If a day slips**, use the cut list at the bottom of [`TASKS.md`](TASKS.md): drop a layer,
  not the product.
