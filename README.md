# Factory Defect Copilot

> Working name — rename when the team picks one.

AI visual inspection for manufacturing lines. A camera image of a part goes through an
anomaly detector, a segmentation model and a defect classifier; an LLM agent then explains
the defect from the plant's QC manual and recommends an action. The operator accepts,
rejects or sends the part to rework.

Built for **AMD Developer Hackathon: ACT III** (lablab.ai), Track 1 — *Intelligent Industry*.
Models and the LLM run on **AMD GPUs (AMD Developer Cloud, ROCm)**.

**Who uses it:** line operators and quality technicians.
**What it improves:** defects caught before shipping, and time from detection to decision.

## Architecture

```
Frontend (React)  ──►  Backend (Node/Express)  ──►  ML service (FastAPI, AMD GPU)
                          │                            ├─ autoencoder  (anomaly gate)
                          ▼                            ├─ segmentation (defect mask)
                       Postgres                        ├─ classifier   (defect type)
                                                       └─ agent: RAG over QC manual + LLM (vLLM)
```

- The **frontend** talks only to the backend.
- The **backend** owns all state (inspections, decisions, stats) and the line simulator.
- The **ML service** is stateless: image in, result out.

The API contracts in [`contracts/`](contracts/) are the source of truth between the three parts.
Change them through a pull request that all three people review.

| Contract | Between |
| --- | --- |
| [`backend.openapi.yaml`](contracts/backend.openapi.yaml) | frontend ↔ backend |
| [`ml-service.openapi.yaml`](contracts/ml-service.openapi.yaml) | backend ↔ ML service |

## Repository layout

```
contracts/    OpenAPI contracts (source of truth)
ml-service/   FastAPI + PyTorch (ROCm) models + agent
backend/      Node + Express + TypeScript, Postgres
frontend/     React 19 + Vite + TanStack Query + Tailwind + shadcn/ui
docs/         Plan, tasks, decisions
```

## Team

| Area | Owner | Scope |
| --- | --- | --- |
| ML + agent, tech lead | @Abrik-Ai | models, RAG agent, AMD setup, contracts |
| Backend | _tbd_ | API, database, simulator, Docker, deployment |
| Frontend | _tbd_ | operator dashboard, cover image, slides, demo video |

## Quick start

Requires Docker and Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:3000/api/health |
| ML service docs | http://localhost:8000/docs |

The ML service starts in **stub mode** (`ML_STUB=1`): it returns realistic fake results
that match the contract, so the frontend and backend can be built before the models exist.

### Run parts without Docker

```bash
# ML service
cd ml-service && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Backend
cd backend && npm install && npm run dev

# Frontend
cd frontend && npm install && npm run dev
```

### Generate TypeScript types from the contracts

```bash
cd backend  && npm run gen:types   # ml-service contract -> src/api/ml-types.ts
cd frontend && npx openapi-typescript ../contracts/backend.openapi.yaml -o src/api/types.ts
```

## AMD

- Vision models are trained and served with PyTorch on ROCm (AMD Instinct GPUs, AMD Developer Cloud).
- The LLM is an open model served with vLLM on ROCm, reached through an OpenAI-compatible endpoint.
- `GET /health` on the ML service reports the GPU in use.

Details: [`ml-service/README.md`](ml-service/README.md).

## Results

_To be filled in: dataset, held-out test metrics (image AUROC, Dice/IoU, per-class recall)
against a baseline, and time from detection to decision._

## License

[MIT](LICENSE)
