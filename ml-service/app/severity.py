"""Severity rule, shared by the stub and the real pipeline.

Described in contracts/ml-service.openapi.yaml (Severity):
- not defective -> none
- missing       -> always high (a missing component means a dead board)
- otherwise by predicted defect area: < 1% low, 1-3% medium, > 3% high
  (set on val from PatchCore masks: scripts/severity_cutoffs.py, docs/DECISIONS.md entry 7)
"""

from typing import Literal

Severity = Literal["none", "low", "medium", "high"]

ALWAYS_HIGH = {"missing"}
LOW_BELOW = 0.01
MEDIUM_BELOW = 0.03


def severity_for(is_defective: bool, defect_type: str | None, area_ratio: float | None) -> Severity:
    if not is_defective:
        return "none"
    if defect_type in ALWAYS_HIGH:
        return "high"
    if area_ratio is None:
        return "medium"  # defective but no area measured: middle, so it still gets attention
    if area_ratio < LOW_BELOW:
        return "low"
    if area_ratio < MEDIUM_BELOW:
        return "medium"
    return "high"
