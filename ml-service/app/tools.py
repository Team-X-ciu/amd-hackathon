"""Read-only tools the chat agent may call (only with AGENT_TOOLS=1, only for operator questions).

One tool for now: recent line history from the backend. Any failure returns None and the agent
answers without it; a tool can never change the decision, the sources or the review flag.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from collections import Counter

from app import config

TIMEOUT_S = 3.0
MAX_LIMIT = 20
DEFECT_TYPES = [*config.DEFECT_TYPES, "unknown"]

log = logging.getLogger("uvicorn.error")


def recent_inspections(defect_type: str, limit: int = 10) -> dict:
    """Summary of the latest inspections of one defect type: count, severities, decisions."""
    if defect_type not in DEFECT_TYPES:
        raise ValueError(f"unknown defect_type {defect_type!r}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    query = urllib.parse.urlencode({"defect_type": defect_type, "limit": limit})
    with urllib.request.urlopen(f"{config.BACKEND_URL}/api/inspections?{query}", timeout=TIMEOUT_S) as r:
        items = json.load(r)["items"]
    severities = Counter((i.get("vision") or {}).get("severity", "unknown") for i in items)
    decisions = Counter((i.get("decision") or {}).get("decision") for i in items if i.get("decision"))
    return {
        "tool": "recent_inspections",
        "defect_type": defect_type,
        "count": len(items),
        "severities": dict(severities),
        "accepted": decisions["accept"],
        "reworked": decisions["rework"],
        "rejected": decisions["reject"],
        "undecided": len(items) - sum(decisions.values()),
    }


TOOLS = {"recent_inspections": recent_inspections}


def run_tool(name: str, args: dict) -> dict | None:
    """Run one tool; None for an unknown tool, bad arguments, an error or a timeout."""
    tool = TOOLS.get(name)
    if tool is None:
        log.warning("Agent asked for unknown tool %r; answering without it", name)
        return None
    try:
        return tool(**args)
    except Exception as e:  # noqa: BLE001 -- any tool failure means "answer without it"
        log.warning("Tool %s failed, answering without it: %s: %s", name, type(e).__name__, e)
        return None
