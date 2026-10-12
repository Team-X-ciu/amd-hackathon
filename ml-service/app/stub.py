"""Fake results that match the contract, for building the app before the models exist.

Deterministic: the same image always gives the same result, which makes
frontend and backend bugs reproducible.
"""

import base64
import hashlib
import io
import random

from PIL import Image, ImageDraw

from . import config
from .schemas import (
    BoundingBox,
    ExplainRequest,
    Explanation,
    InspectResult,
    ModelVersions,
    Source,
)

STUB_VERSIONS = ModelVersions(autoencoder="stub", segmentation="stub", classifier="stub", llm="stub")


def _severity(area_ratio: float) -> str:
    if area_ratio < 0.01:
        return "low"
    if area_ratio < 0.05:
        return "medium"
    return "high"


def _png_b64(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def inspect(image: Image.Image, raw: bytes) -> InspectResult:
    rng = random.Random(hashlib.sha256(raw).hexdigest())
    width, height = image.size

    is_defective = rng.random() < 0.35
    if not is_defective:
        return InspectResult(
            anomaly_score=round(rng.uniform(0.05, config.ANOMALY_THRESHOLD - 0.05), 3),
            anomaly_threshold=config.ANOMALY_THRESHOLD,
            is_defective=False,
            severity="none",
            model_versions=STUB_VERSIONS,
            latency_ms=rng.randint(80, 200),
        )

    # One elliptical "defect" somewhere on the part
    bw = rng.randint(width // 12, width // 4)
    bh = rng.randint(height // 12, height // 4)
    x = rng.randint(0, width - bw)
    y = rng.randint(0, height - bh)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse([x, y, x + bw, y + bh], fill=255)
    area_ratio = round(sum(1 for p in mask.getdata() if p) / (width * height), 4)

    return InspectResult(
        anomaly_score=round(rng.uniform(config.ANOMALY_THRESHOLD + 0.05, 0.99), 3),
        anomaly_threshold=config.ANOMALY_THRESHOLD,
        is_defective=True,
        defect_type=rng.choice(config.DEFECT_TYPES),
        defect_confidence=round(rng.uniform(0.6, 0.98), 3),
        severity=_severity(area_ratio),
        defect_area_ratio=area_ratio,
        bounding_boxes=[BoundingBox(x=x, y=y, width=bw, height=bh)],
        mask_png_base64=_png_b64(mask),
        model_versions=STUB_VERSIONS,
        latency_ms=rng.randint(150, 400),
    )


def explain(req: ExplainRequest) -> Explanation:
    priority = {"none": "low", "low": "low", "medium": "medium", "high": "high"}[req.severity]
    return Explanation(
        summary=f"[STUB] {req.severity} {req.defect_type} detected on the part.",
        likely_causes=["[STUB] Worn tooling", "[STUB] Debris on the conveyor"],
        recommended_action=f"[STUB] Set the part aside and follow the {req.defect_type} procedure in the QC manual.",
        priority=priority,
        answer=f"[STUB] Answer to: {req.question}" if req.question else None,
        sources=[
            Source(
                document="QC Manual (stub)",
                section=f"{req.defect_type.title()} defects",
                snippet="[STUB] Placeholder passage until the RAG index exists.",
            )
        ],
        needs_human_review=req.severity == "high",
        model="stub",
        latency_ms=50,
    )
