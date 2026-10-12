"""Pydantic models for the ML service.

Must match contracts/ml-service.openapi.yaml. If you change a field here,
change the contract in the same pull request.
"""

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["none", "low", "medium", "high"]
Priority = Literal["low", "medium", "high", "stop_line"]


class BoundingBox(BaseModel):
    x: int = Field(description="Left, in pixels")
    y: int = Field(description="Top, in pixels")
    width: int
    height: int


class ModelVersions(BaseModel):
    autoencoder: str | None = None
    segmentation: str | None = None
    classifier: str | None = None
    llm: str | None = None


class InspectResult(BaseModel):
    anomaly_score: float = Field(description="Autoencoder reconstruction error, normalised to 0-1")
    anomaly_threshold: float
    is_defective: bool
    defect_type: str | None = None
    defect_confidence: float | None = None
    severity: Severity
    defect_area_ratio: float | None = None
    bounding_boxes: list[BoundingBox] = []
    mask_png_base64: str | None = None
    heatmap_png_base64: str | None = None
    model_versions: ModelVersions
    latency_ms: int


class ChatTurn(BaseModel):
    role: Literal["operator", "assistant"]
    content: str


class ExplainRequest(BaseModel):
    defect_type: str
    severity: Severity
    anomaly_score: float | None = None
    defect_area_ratio: float | None = None
    part_type: str | None = None
    question: str | None = None
    history: list[ChatTurn] = []


class Source(BaseModel):
    document: str
    section: str
    snippet: str | None = None


class Explanation(BaseModel):
    summary: str
    likely_causes: list[str] = []
    recommended_action: str
    priority: Priority
    answer: str | None = None
    sources: list[Source]
    needs_human_review: bool
    model: str | None = None
    latency_ms: int | None = None


class ModelsLoaded(BaseModel):
    autoencoder: bool
    segmentation: bool
    classifier: bool
    llm_reachable: bool


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    models_loaded: ModelsLoaded
    device: str | None = None
    stub: bool = False


class Error(BaseModel):
    error: str
    detail: str | None = None
