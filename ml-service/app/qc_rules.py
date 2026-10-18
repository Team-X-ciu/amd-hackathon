"""Deterministic QC decision table, transcribed from manuals/pcb_qc_manual.md (QC-1 to QC-5).

The LLM never decides the action: /explain looks it up here and the LLM only phrases it.
If the manual changes, change this table too (tests check every type x severity pair).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

DefectType = Literal["bent", "melt", "scratch", "missing", "unknown"]
Severity = Literal["low", "medium", "high"]
# "review" = hold for a technician; it maps to needs_human_review=True in the response.
Action = Literal["accept", "rework", "reject", "review"]


@dataclass(frozen=True)
class Rule:
    action: Action              # default action; also the prefix of recommended_action
    needs_human_review: bool
    checks: tuple[str, ...]     # things the camera cannot see that can change the action
    section: str                # manual section the action comes from (cited in sources)


# Manual section per type: action is <prefix>.3 (QC-5.2 for unknown), causes <prefix>.2, who to call <prefix>.4.
TYPE_SECTION: dict[str, str] = {
    "bent": "QC-1", "melt": "QC-2", "scratch": "QC-3", "missing": "QC-4", "unknown": "QC-5",
}

# The manual's "high" is functional; our severity is estimated from defect area.
# So for low/medium we ALWAYS add a check for that type's high-severity conditions.
HIGH_CONDITIONS: dict[str, str] = {
    "bent": "a lead touches a neighbouring lead or pad, or a lead is cracked or lifted",
    "melt": "the board itself is heat-damaged",
    "scratch": "a trace is cut or damaged, or the scratch crosses several traces",
}

TABLE: dict[tuple[str, str], Rule] = {
    ("bent", "low"): Rule("rework", False,
        ("If the lead is cracked, treat as high and reject.",), "QC-1.3"),
    ("bent", "medium"): Rule("rework", False,
        ("Re-inspect the board on the camera station after rework.",), "QC-1.3"),
    ("bent", "high"): Rule("reject", False, (), "QC-1.3"),

    ("melt", "low"): Rule("review", True,
        ("A technician checks whether the damage is only cosmetic: if so accept, "
         "otherwise rework by replacing the component.",), "QC-2.3"),
    # Judgement call: the manual says rework only if the part is replaceable AND the surface is intact.
    # The camera cannot confirm either, so the safe default is reject.
    ("melt", "medium"): Rule("reject", False,
        ("Rework instead only if the damaged component can be replaced and the board surface is intact.",),
        "QC-2.3"),
    ("melt", "high"): Rule("reject", False, (), "QC-2.3"),

    ("scratch", "low"): Rule("accept", False,
        ("Accept only if purely cosmetic: no exposed copper and no damage to markings needed for assembly.",),
        "QC-3.3"),
    ("scratch", "medium"): Rule("rework", False,
        ("Touch up the solder mask if copper is exposed; accept after re-inspection.",), "QC-3.3"),
    ("scratch", "high"): Rule("reject", False, (), "QC-3.3"),

    ("missing", "high"): Rule("reject", False,
        ("Rework instead only if the rework station can place and solder the part; re-inspect afterwards.",),
        "QC-4.3"),
}

UNKNOWN = Rule("review", True,
    ("Never accept automatically: a technician inspects the board and records what the defect actually was.",),
    "QC-5.2")


def decide(defect_type: str, severity: str) -> Rule:
    """Look up the default action. Raises ValueError for a type/severity the manual doesn't cover."""
    if defect_type == "unknown":
        return UNKNOWN                    # QC-5.2, whatever the severity
    if defect_type == "missing":
        severity = "high"                 # QC-4.3: missing is always high
    rule = TABLE.get((defect_type, severity))
    if rule is None:
        raise ValueError(f"No QC rule for defect_type={defect_type!r}, severity={severity!r}")
    return rule


def operator_checks(defect_type: str, severity: str) -> list[str]:
    """Checks the explanation must always show: the rule's own checks, plus the type's
    high-severity conditions when our area-based severity says low or medium."""
    rule = decide(defect_type, severity)
    checks = list(rule.checks)
    if defect_type in HIGH_CONDITIONS and severity != "high":
        checks.append(f"Treat as high severity and reject if {HIGH_CONDITIONS[defect_type]}.")
    return checks
