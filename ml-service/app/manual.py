"""The QC manual, split into sections by ID (QC-1, QC-1.3, ...).

Everything here is deterministic: /explain cites sections and lists likely causes
straight from the manual text, so the LLM can never invent a source.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.qc_rules import TYPE_SECTION, decide

MANUAL_PATH = Path(__file__).resolve().parent.parent / "manuals" / "pcb_qc_manual.md"
DOCUMENT_NAME = "PCB QC Manual (Line PCB1)"

# Matches "## QC-1 Bent component lead (`bent`)" and "### QC-1.3 Action by severity"
_HEADING = re.compile(r"^#{2,3}\s+(QC-\d+(?:\.\d+)?)\s+(.+)$")


@lru_cache(maxsize=1)
def load_sections() -> dict[str, dict[str, str]]:
    """{"QC-1.3": {"title": "Action by severity", "text": "..."}, ...}"""
    sections: dict[str, dict] = {}
    current: str | None = None
    for line in MANUAL_PATH.read_text(encoding="utf-8").splitlines():
        m = _HEADING.match(line)
        if m:
            current = m.group(1)
            sections[current] = {"title": m.group(2).strip(), "lines": []}
        elif line.startswith("#"):
            current = None                       # a heading without an ID (e.g. the title)
        elif current and line.strip() != "---":  # skip horizontal rules between sections
            sections[current]["lines"].append(line)
    return {sid: {"title": s["title"], "text": "\n".join(s["lines"]).strip()}
            for sid, s in sections.items()}


def manual_text() -> str:
    """The whole manual, for the LLM prompt (about 1.5k tokens, so no retrieval needed)."""
    return MANUAL_PATH.read_text(encoding="utf-8")


def section_exists(section_id: str) -> bool:
    return section_id in load_sections()


def _table_row(text: str, severity: str) -> str | None:
    """The action cell of the '| severity | action |' row, if the section has one."""
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == severity:
            return cells[1]
    return None

def _plain(s: str) -> str:
    """Strip markdown for display: bold, code ticks, and leading bullet dashes."""
    return s.replace("**", "").replace("`", "").replace(" - ", " ").lstrip("- ").strip()

def snippet(section_id: str, severity: str | None = None, max_chars: int = 300) -> str:
    """Short passage shown to the operator: the exact table row for this severity if
    there is one, otherwise the start of the section with whitespace collapsed."""
    text = load_sections()[section_id]["text"]
    if severity:
        row = _table_row(text, severity)
        if row:
            return _plain(row)
    flat = _plain(" ".join(text.split()))
    return flat if len(flat) <= max_chars else flat[:max_chars].rsplit(" ", 1)[0] + "…"

def source(section_id: str, severity: str | None = None) -> dict[str, str]:
    """One contract `Source` object."""
    s = load_sections()[section_id]
    return {
        "document": DOCUMENT_NAME,
        "section": f"{section_id} {s['title']}",
        "snippet": snippet(section_id, severity),
    }


def sources_for(defect_type: str, severity: str) -> list[dict[str, str]]:
    """Sections cited for this defect: the action rule, then who to call. Never empty."""
    rule = decide(defect_type, severity)
    prefix = TYPE_SECTION[defect_type]
    who = f"{prefix}.3" if defect_type == "unknown" else f"{prefix}.4"
    # missing is forced to high in decide(); cite the row the decision actually used
    row_severity = "high" if defect_type == "missing" else severity
    return [source(rule.section, row_severity), source(who)]


def likely_causes(defect_type: str) -> list[str]:
    """Bullet points of QC-N.2 'Likely causes on the line'. Empty for unknown."""
    if defect_type == "unknown":
        return []
    text = load_sections()[f"{TYPE_SECTION[defect_type]}.2"]["text"]
    return [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]
