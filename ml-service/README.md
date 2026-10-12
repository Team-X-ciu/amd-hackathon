# ML service

FastAPI service with the vision pipeline and the defect agent.
Contract: [`../contracts/ml-service.openapi.yaml`](../contracts/ml-service.openapi.yaml).

| Endpoint | What it does |
| --- | --- |
| `GET /health` | model status and the GPU in use |
| `POST /inspect` | autoencoder gate → segmentation + classification (fast, no LLM) |
| `POST /explain` | RAG over `manuals/` + LLM agent: explanation, action, sources |

Dependencies are managed with [uv](https://docs.astral.sh/uv/): `pyproject.toml` + `uv.lock`.

## Run in stub mode (no models)

```bash
uv sync
ML_STUB=1 uv run uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. Stub results are deterministic per image.

```bash
uv add <package>             # API dependency
uv add --optional ml <pkg>   # model / agent dependency
uv run ruff check app && uv run ruff format app
```

Commit `uv.lock` with every dependency change.

## Run on AMD Developer Cloud

**torch must be the ROCm build.** `timm`, `segmentation-models-pytorch` and
`sentence-transformers` depend on torch, so `uv sync --extra ml` would install the
CUDA build from PyPI, which can't use AMD GPUs. Keep the ROCm torch from AMD's image instead:

```bash
# Option A: Docker (recommended)
docker build -f Dockerfile.rocm -t ml-service-rocm .
docker run --device=/dev/kfd --device=/dev/dri --group-add video -p 8000:8000 ml-service-rocm

# Option B: directly inside a rocm/pytorch container or instance
uv pip install --system -r pyproject.toml --extra ml
python -c "import torch; print(torch.cuda.is_available(), torch.version.hip, torch.cuda.get_device_name(0))"
ML_STUB=0 uvicorn app.main:app --host 0.0.0.0 --port 8000
```

`torch.version.hip` must print a version, not `None`. Then:

1. Serve the LLM with vLLM's ROCm image, OpenAI-compatible, for example on port 8001.
   Set `LLM_BASE_URL`, `LLM_MODEL`.
2. Put trained weights in `models/` and run with `ML_STUB=0`.

On a laptop without an AMD GPU (CPU or NVIDIA), `uv sync --extra ml` is fine for development.

## Layout

```
app/
  main.py      endpoints
  schemas.py   Pydantic models (must match the contract)
  config.py    env settings, defect types
  stub.py      fake results for stub mode
  # to add:
  vision.py    autoencoder, segmentation, classifier
  rag.py       chunking, embeddings, FAISS index over manuals/
  agent.py     LangGraph agent calling the vLLM endpoint
training/      notebooks / scripts for training (to add)
manuals/       QC manual sources for RAG
models/        weights (git-ignored)
data/          datasets (git-ignored)
```

## Results to report

- Autoencoder: image-level AUROC on the held-out test set
- Segmentation: Dice / IoU
- Classifier: per-class recall and confusion matrix, against a simple baseline
