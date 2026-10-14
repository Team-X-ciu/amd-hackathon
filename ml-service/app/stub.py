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
from .severity import severity_for

STUB_VERSIONS = ModelVersions(anomaly_detector="stub", classifier="stub", llm="stub")

# Rough share of each outcome among defective boards, so the UI sees every case
_STUB_DEFECTS = config.DEFECT_TYPES + ["unknown"]


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

    # One elliptical "defect" somewhere on the board
    bw = rng.randint(width // 12, width // 4)
    bh = rng.randint(height // 12, height // 4)
    x = rng.randint(0, width - bw)
    y = rng.randint(0, height - bh)

    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).ellipse([x, y, x + bw, y + bh], fill=255)
    area_ratio = round(sum(1 for p in mask.getdata() if p) / (width * height), 4)

    defect_type = rng.choice(_STUB_DEFECTS)
    if defect_type == "unknown":
        confidence = round(rng.uniform(0.3, config.CLASSIFIER_MIN_CONFIDENCE - 0.05), 3)
    else:
        confidence = round(rng.uniform(config.CLASSIFIER_MIN_CONFIDENCE + 0.05, 0.98), 3)

    return InspectResult(
        anomaly_score=round(rng.uniform(config.ANOMALY_THRESHOLD + 0.05, 0.99), 3),
        anomaly_threshold=config.ANOMALY_THRESHOLD,
        is_defective=True,
        defect_type=defect_type,
        defect_confidence=confidence,
        severity=severity_for(True, defect_type, area_ratio),
        defect_area_ratio=area_ratio,
        bounding_boxes=[BoundingBox(x=x, y=y, width=bw, height=bh)],
        mask_png_base64=_png_b64(mask),
        model_versions=STUB_VERSIONS,
        latency_ms=rng.randint(150, 400),
    )


def explain(req: ExplainRequest) -> Explanation:
    priority = {"none": "low", "low": "low", "medium": "medium", "high": "high"}[req.severity]
    unknown = req.defect_type == "unknown"
    return Explanation(
        summary=f"[STUB] {req.severity} {req.defect_type} defect detected on the board.",
        likely_causes=[] if unknown else ["[STUB] Handling damage", "[STUB] Soldering process drift"],
        recommended_action=(
            "[STUB] Hold the board for a quality engineer: defect type not recognised."
            if unknown
            else f"[STUB] Follow the {req.defect_type} procedure in the QC manual."
        ),
        priority=priority,
        answer=f"[STUB] Answer to: {req.question}" if req.question else None,
        sources=[]
        if unknown
        else [
            Source(
                document="QC Manual (stub)",
                section=f"{req.defect_type.title()} defects",
                snippet="[STUB] Placeholder passage until the RAG index exists.",
            )
        ],
        needs_human_review=unknown or req.severity == "high",
        model="stub",
        latency_ms=50,
    )
