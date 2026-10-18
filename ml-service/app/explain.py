"""Build the /explain response (contract: Explanation).

Step 1 (this file): a complete templated explanation from the decision table + manual, no LLM.
It is also the fallback when Gemma fails later. The action NEVER comes from the LLM.
"""

from __future__ import annotations

import logging
import time

from app import checks, config, llm, manual, tools
from app.qc_rules import decide, operator_checks

NAMES = {
    "bent": "Bent component lead",
    "melt": "Melted or burned area",
    "scratch": "Scratch",
    "missing": "Missing component",
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


def build_explanation(
    defect_type: str, severity: str, defect_area_ratio: float | None = None, question: str | None = None
) -> dict:
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
        "answer": None
        if question is None
        else (
            f"I can't give a checked answer to that. The decision comes from the QC manual: "
            f"{rule.action} ({rule.section}). Please ask a technician if you disagree."
        ),
        "sources": manual.sources_for(defect_type, severity),
        "needs_human_review": rule.needs_human_review,
        "model": "template",
        "latency_ms": int((time.perf_counter() - start) * 1000),
    }


log = logging.getLogger("uvicorn.error")


def agent_answer(facts: dict, question: str, history: list[dict] | None) -> llm.LLMOutput:
    """Chat with at most one tool call. A tool result is added to `facts`, so the number check
    accepts its figures; an unknown tool or a failed tool means answering without it."""
    first = llm.chat_turn(facts, question, history)
    if isinstance(first, llm.LLMOutput):
        return first
    result = tools.run_tool(first.tool, first.args)
    if result is not None:
        facts["tool_result"] = result
    return llm.rewrite(facts, question, history)  # second call offers no tools: max 1 tool call


def explain_with_llm(
    defect_type: str,
    severity: str,
    defect_area_ratio: float | None = None,
    question: str | None = None,
    history: list[dict] | None = None,
) -> dict:
    """Template first (always valid), then let Gemma reword it if its reply passes every check."""
    start = time.perf_counter()
    result = build_explanation(defect_type, severity, defect_area_ratio, question)
    rule = decide(defect_type, severity)
    facts = {
        "defect_type": defect_type,
        "severity": result["priority"],
        "area_percent": None if defect_area_ratio is None else round(defect_area_ratio * 100, 1),
        "action": rule.action,
        "checks": operator_checks(defect_type, severity) or [f"no further checks ({rule.section})"],
        "needs_human_review": rule.needs_human_review,
        "likely_causes": result["likely_causes"],
        "cited_sections": [{"section": s["section"], "snippet": s["snippet"]} for s in result["sources"]],
    }
    try:
        if question and config.AGENT_TOOLS:
            out = agent_answer(facts, question, history)
        else:
            out = llm.rewrite(facts, question, history)
        found = checks.problems(out, facts)
        if found:
            log.warning(
                "LLM reply rejected, using template: %s | Gemma's action was: %r",
                found,
                out.recommended_action[:150],
            )
        else:
            result.update(
                summary=out.summary,
                recommended_action=out.recommended_action,
                answer=out.answer if question else None,
                model=config.LLM_MODEL,
            )
    except Exception as e:  # noqa: BLE001 - any LLM failure falls back to the template
        log.warning("LLM failed, using template: %s: %s", type(e).__name__, e)
    result["latency_ms"] = int((time.perf_counter() - start) * 1000)
    return result
