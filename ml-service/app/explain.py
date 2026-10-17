"""Build the /explain response (contract: Explanation).

Step 1 (this file): a complete templated explanation from the decision table + manual, no LLM.
It is also the fallback when Gemma fails later. The action NEVER comes from the LLM.
"""

from __future__ import annotations

import time

from app import manual
from app.qc_rules import decide, operator_checks

NAMES = {
    "bent": "Bent component lead",
    "melt": "Melted or burned area",
    "scratch": "Scratch",
    "missing": "Missing component"
}

def templated_summary(defect_type: str, severity: str, area_ratio: float | None) -> str:
    if defect_type == "unknown":
        text = "Anomaly found, but its type could not be classified with enough confidence"
    else:
        text = f"{NAMES[defect_type]}, {severity} severity"

    if area_ratio is not None:
        text += f", about {area_ratio * 100:.1f}% of the image"

    return text + "."

def templated_action(defect_type: str, severity: str) -> str:
    rule = decide(defect_type, severity)
    checks = operator_checks(defect_type, severity)

    if checks:
        return f"{rule.action}: " + " ".join(checks)
    return f"{rule.action}: no further checks ({rule.section})."


def build_explanation(defect_type: str, severity: str,
                      defect_area_ratio: float | None = None,
                      question: str | None = None) -> dict:
    """Templated Explanation dict matching the contract."""
    start = time.perf_counter()
    rule = decide(defect_type, severity)
    if defect_type == "missing":
        severity = "high"  # QC-4.3, keep priority consistent with the rule

    return {
        "summary": templated_summary(defect_type, severity, defect_area_ratio),
        "likely_causes": manual.likely_causes(defect_type),
        "recommended_action": templated_action(defect_type, severity),
        "priority": severity,
        "answer": None if question is None else (
            "Answering questions needs the AI model, which is not available right now. "
            "Please ask a technician."
        ),
        "sources": manual.sources_for(defect_type, severity),
        "needs_human_review": rule.needs_human_review,
        "model": "template",
        "latency_ms": int((time.perf_counter() - start) * 1000),
    }