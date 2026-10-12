"""ML service: vision pipeline (/inspect) and defect agent (/explain).

Contract: contracts/ml-service.openapi.yaml
Stateless: no database. Called only by the backend.
"""

import io
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from . import config, stub
from .schemas import Error, ExplainRequest, Explanation, Health, InspectResult, ModelsLoaded

app = FastAPI(
    title="ML Service (FastAPI)",
    version="0.1.0",
    description="Vision pipeline and defect agent. Runs on AMD GPUs (ROCm).",
)


def _device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu (torch not installed)"
    if torch.cuda.is_available():  # ROCm builds of PyTorch also use the torch.cuda API
        name = torch.cuda.get_device_name(0)
        backend = "ROCm" if getattr(torch.version, "hip", None) else "CUDA"
        return f"cuda:0 ({name}, {backend})"
    return "cpu"


@app.exception_handler(RequestValidationError)
async def validation_error(_, exc: RequestValidationError):
    # Contract: invalid input is a 400 with the Error shape
    return JSONResponse(
        status_code=400, content=Error(error="Invalid input", detail=str(exc.errors())).model_dump()
    )


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=Error(error=str(exc.detail)).model_dump())


@app.get("/health", response_model=Health)
def health() -> Health:
    if config.STUB:
        loaded = ModelsLoaded(autoencoder=True, segmentation=True, classifier=True, llm_reachable=True)
    else:
        # TODO: report real model / LLM status
        loaded = ModelsLoaded(autoencoder=False, segmentation=False, classifier=False, llm_reachable=False)
    status = "ok" if all(loaded.model_dump().values()) else "degraded"
    return Health(status=status, models_loaded=loaded, device=_device(), stub=config.STUB)


@app.post(
    "/inspect",
    response_model=InspectResult,
    responses={400: {"model": Error}, 500: {"model": Error}},
)
async def inspect(
    image: Annotated[UploadFile, File(description="PNG or JPEG of one part")],
    part_type: Annotated[str | None, Form()] = None,
) -> InspectResult:
    raw = await image.read()
    if len(raw) > config.MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image too large (max 10 MB)")
    try:
        img = Image.open(io.BytesIO(raw)).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(400, "Not a valid PNG or JPEG image")

    if config.STUB:
        return stub.inspect(img, raw)

    # TODO: autoencoder gate -> segmentation + classification
    raise HTTPException(500, "Models not loaded yet; run with ML_STUB=1")


@app.post(
    "/explain",
    response_model=Explanation,
    responses={400: {"model": Error}, 503: {"model": Error}},
)
def explain(req: ExplainRequest) -> Explanation:
    if config.STUB:
        return stub.explain(req)

    # TODO: RAG over manuals/ + LangGraph agent on the vLLM endpoint
    raise HTTPException(503, "Agent not available yet; run with ML_STUB=1")
