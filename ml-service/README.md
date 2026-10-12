# ML service

FastAPI service with the vision pipeline and the defect agent.
Contract: [`../contracts/ml-service.openapi.yaml`](../contracts/ml-service.openapi.yaml).

| Endpoint | What it does |
| --- | --- |
| `GET /health` | model status and the GPU in use |
| `POST /inspect` | autoencoder gate → segmentation + classification (fast, no LLM) |
| `POST /explain` | RAG over `manuals/` + LLM agent: explanation, action, sources |

## Run in stub mode (no models)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ML_STUB=1 uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. Stub results are deterministic per image.

## Run on AMD Developer Cloud

1. Start a GPU instance with a ROCm PyTorch image and check the GPU:
   ```bash
   python -c "import torch; print(torch.cuda.is_available(), torch.version.hip, torch.cuda.get_device_name(0))"
   ```
2. `pip install -r requirements-ml.txt` (torch is already in the image — don't reinstall it).
3. Serve the LLM with vLLM's ROCm image, OpenAI-compatible, for example on port 8001.
   Set `LLM_BASE_URL`, `LLM_MODEL`.
4. Put trained weights in `models/` and run with `ML_STUB=0`.

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
