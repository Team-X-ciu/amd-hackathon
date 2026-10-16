# GENERATED from contracts/ml-service.openapi.yaml by scripts/gen-schemas.sh. Do not edit by hand.

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    x: int
    """
    Left
    """
    y: int
    """
    Top
    """
    width: int
    height: int


class ModelVersions(BaseModel):
    anomaly_detector: str | None = Field(None, examples=["patchcore-wrn50-v1"])
    classifier: str | None = Field(None, examples=["logreg-wrn50-v1"])
    llm: str | None = Field(None, examples=["Qwen2.5-7B-Instruct"])


class InspectResult(BaseModel):
    anomaly_score: float = Field(..., examples=[0.87])
    """
    PatchCore anomaly score for the image, normalised to 0-1
    """
    anomaly_threshold: float = Field(..., examples=[0.5])
    is_defective: bool
    defect_type: Literal["bent", "melt", "scratch", "missing", "unknown"] | None = None
    """
    Null when not defective.
    """
    defect_confidence: float | None = Field(None, examples=[0.92])
    severity: Literal["none", "low", "medium", "high"]
    """
    none = not defective. `missing` is always high (a missing component means a dead board).
    Other defect types by defect_area_ratio: < 0.01 low, 0.01-0.03 medium, > 0.03 high (predicted mask area; set on val, DECISIONS 7).

    """
    defect_area_ratio: float | None = Field(None, examples=[0.031])
    """
    Fraction of the image's pixels covered by the defect mask (0-1)
    """
    bounding_boxes: list[BoundingBox] | None = None
    mask_png_base64: str | None = None
    """
    Binary defect mask (thresholded PatchCore heatmap), same size as input, base64 PNG. Null when not defective.
    """
    heatmap_png_base64: str | None = None
    """
    Optional PatchCore anomaly heatmap (grayscale PNG, base64) for the UI overlay
    """
    model_versions: ModelVersions
    latency_ms: int = Field(..., examples=[240])


class ChatTurn(BaseModel):
    role: Literal["operator", "assistant"]
    content: str


class Source(BaseModel):
    document: str = Field(..., examples=["QC Manual v1"])
    section: str = Field(..., examples=["3 Scratch"])
    snippet: str | None = None
    """
    Short retrieved passage shown to the operator
    """


class Explanation(BaseModel):
    summary: str = Field(
        ..., examples=["Scratch across two traces near the connector, about 2% of the board."]
    )
    likely_causes: list[str] | None = Field(
        None, examples=[["Board scraped by the handling fixture", "Debris on the conveyor"]]
    )
    recommended_action: str = Field(
        ..., examples=["Send the board to rework and check the handling fixture before the next batch."]
    )
    priority: Literal["low", "medium", "high", "stop_line"]
    answer: str | None = None
    """
    Answer to `question`, when one was asked
    """
    sources: list[Source]
    """
    Manual sections used. Empty means the agent found no source and must say so.
    """
    needs_human_review: bool
    """
    True when confidence is low or no source was found
    """
    model: str | None = Field(None, examples=["Qwen2.5-7B-Instruct"])
    latency_ms: int | None = None


class ModelsLoaded(BaseModel):
    anomaly_detector: bool
    classifier: bool
    llm_reachable: bool


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    models_loaded: ModelsLoaded
    device: str | None = None
    """
    e.g. "cuda:0 (AMD Instinct MI300X, ROCm)" -- useful to show AMD usage in the demo
    """
    stub: bool | None = None
    """
    True when the service returns fake results (ML_STUB=1)
    """


class Error(BaseModel):
    error: str
    detail: str | None = None


class ExplainRequest(BaseModel):
    defect_type: Literal["bent", "melt", "scratch", "missing", "unknown"]
    """
    Defect classes of VisA pcb1, plus `unknown` when the classifier is not confident
    (the case then also gets needs_human_review).

    """
    severity: Literal["none", "low", "medium", "high"]
    """
    none = not defective. `missing` is always high (a missing component means a dead board).
    Other defect types by defect_area_ratio: < 0.01 low, 0.01-0.03 medium, > 0.03 high (predicted mask area; set on val, DECISIONS 7).

    """
    anomaly_score: float | None = Field(None, examples=[0.87])
    defect_area_ratio: float | None = Field(None, examples=[0.031])
    part_type: Literal["pcb1"] | None = None
    """
    Product being inspected. One product for the hackathon.
    """
    question: str | None = Field(None, examples=["Can this part be reworked?"])
    """
    Operator follow-up question; null for the first explanation
    """
    history: list[ChatTurn] | None = None
    """
    Previous turns for follow-up questions
    """
