"""ML service: vision pipeline (/inspect) and defect agent (/explain).

Contract: contracts/ml-service.openapi.yaml
Stateless: no database. Called only by the backend.
"""

import io
import logging
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError

from . import config, stub
from .schemas import Error, ExplainRequest, Explanation, Health, InspectResult, ModelsLoaded

log = logging.getLogger("uvicorn.error")

# Loaded once at startup in real mode (ML_STUB=0); None in stub mode or if loading failed.
detector = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global detector
    if not config.STUB:
        try:
            from .patchcore import PatchCore  # torch import only in real mode

            detector = PatchCore(config.MODELS_DIR)
            detector.detect(Image.new("RGB", (detector.size, detector.size)))  # warm-up: first call is slow
            log.info("PatchCore loaded: %s on %s", detector.version, detector.device)
        except Exception as e:  # noqa: BLE001 -- keep serving /health so the failure is visible
            log.error("PatchCore failed to load from %s: %s", config.MODELS_DIR, e)
    yield


# Responses leave out fields that are None: the contract allows optional fields to be
# absent, but not to be null unless it says so.
app = FastAPI(
    title="ML Service (FastAPI)",
    version="0.1.0",
    description="Vision pipeline and defect agent. Runs on AMD GPUs (ROCm).",
    lifespan=lifespan,
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


@app.get("/health", response_model=Health, response_model_exclude_none=True)
def health() -> Health:
    if config.STUB:
        loaded = ModelsLoaded(anomaly_detector=True, classifier=True, llm_reachable=True)
    else:
        # TODO: classifier (#9) and LLM status
        loaded = ModelsLoaded(anomaly_detector=detector is not None, classifier=False, llm_reachable=False)
    status = "ok" if all(loaded.model_dump().values()) else "degraded"
    return Health(status=status, models_loaded=loaded, device=_device(), stub=config.STUB)


@app.post(
    "/inspect",
    response_model=InspectResult,
    response_model_exclude_none=True,
    responses={400: {"model": Error}, 500: {"model": Error}},
)
async def inspect(
    image: Annotated[UploadFile, File(description="PNG or JPEG of one part")],
    part_type: Annotated[Literal["pcb1"] | None, Form()] = None,
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

    if detector is None:
        raise HTTPException(500, f"PatchCore not loaded from {config.MODELS_DIR}; see service logs")

    from . import pipeline

    # torch work is blocking: run it in a worker thread so the event loop stays free
    return await run_in_threadpool(pipeline.inspect, img, detector)


@app.post(
    "/explain",
    response_model=Explanation,
    response_model_exclude_none=True,
    responses={400: {"model": Error}, 503: {"model": Error}},
)
def explain(req: ExplainRequest) -> Explanation:
    if config.STUB:
        return stub.explain(req)

    # TODO: RAG over manuals/ + LangGraph agent on the vLLM endpoint
    raise HTTPException(503, "Agent not available yet; run with ML_STUB=1")
