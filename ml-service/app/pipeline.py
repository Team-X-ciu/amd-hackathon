"""Real /inspect pipeline: PatchCore detection -> defect classifier -> contract-shaped InspectResult.

The classifier names the defect in PatchCore's main box (the one holding the peak).
When it is unsure, or not loaded, the type is "unknown": a valid answer in the contract,
and the agent then asks for a human review instead of guessing a procedure.
"""

import base64
import io
import time

import numpy as np
from PIL import Image

from .classifier import DefectClassifier
from .patchcore import PatchCore
from .schemas import BoundingBox, InspectResult, ModelVersions
from .severity import severity_for

# Normalised score scale (see PatchCore.normalise): the decision threshold is always 0.5
NORMALISED_THRESHOLD = 0.5


def _png_b64(a: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(a).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def inspect(
    img: Image.Image, detector: PatchCore, classifier: DefectClassifier | None = None
) -> InspectResult:
    t0 = time.perf_counter()
    det = detector.detect(img)
    versions = ModelVersions(
        anomaly_detector=detector.version, classifier=classifier.version if classifier else "not loaded"
    )

    # heatmap for every board (the UI can show why a good board was close to the line)
    common = {
        "anomaly_score": round(det.score, 4),
        "anomaly_threshold": NORMALISED_THRESHOLD,
        "heatmap_png_base64": _png_b64(det.heatmap),
        "model_versions": versions,
    }
    if not det.is_defective:
        return InspectResult(
            **common,
            is_defective=False,
            severity="none",
            latency_ms=round((time.perf_counter() - t0) * 1000),
        )

    defect_type, confidence = "unknown", None
    if classifier is not None and det.main_box is not None:
        defect_type, confidence = classifier.classify(img, det.main_box)
    return InspectResult(
        **common,
        is_defective=True,
        defect_type=defect_type,
        defect_confidence=round(confidence, 3) if confidence is not None else None,
        severity=severity_for(True, defect_type, det.area_ratio),
        defect_area_ratio=round(det.area_ratio, 5),
        bounding_boxes=[BoundingBox(x=x, y=y, width=w, height=h) for x, y, w, h in det.boxes],
        mask_png_base64=_png_b64(det.mask.astype(np.uint8) * 255),
        latency_ms=round((time.perf_counter() - t0) * 1000),
    )
