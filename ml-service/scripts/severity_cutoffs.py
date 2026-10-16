"""#10: severity cut-offs from the PREDICTED defect area on val.

/inspect computes defect_area_ratio from PatchCore's mask, which is blurrier and
larger than the ground-truth defect (Anomaly/000: 1.6% predicted). The placeholder
cut-offs (1% / 5%) were written for ground-truth areas, so they don't fit.

Rule (Decision 6, set on val): among the defective val boards PatchCore catches,
split the predicted area into thirds -> low / medium / high. (`missing` stays always
high in severity.py once #9 names the type.) Test is only counted, never used to choose.

The mask is rebuilt from the saved maps with the same rule as app/patchcore.py, so
no torch is needed.

Run from ml-service/:
  uv run --no-project --with numpy --with pandas --with scipy python scripts/severity_cutoffs.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/patchcore"
MIN_BOX_AREA = 16  # same as app/patchcore.py

t = json.loads((ROOT / "models/patchcore_pcb1_threshold.json").read_text())["threshold"]


def predicted_area(m):
    """Share of the map kept as defect: regions >= MIN_BOX_AREA, plus the peak region."""
    comp, _ = ndimage.label(m >= t, structure=np.ones((3, 3)))
    if comp.max() == 0:
        return 0.0
    top = comp[np.unravel_index(np.argmax(m), m.shape)]
    sizes = np.bincount(comp.ravel())
    keep = [k for k in range(1, len(sizes)) if sizes[k] >= MIN_BOX_AREA or k == top]
    return float(sizes[keep].sum() / m.size)


def areas(name):
    s = pd.read_csv(OUT / f"scores_{name}.csv")
    maps = np.load(OUT / f"maps_{name}.npy").astype(np.float32)
    s["area"] = [predicted_area(m) for m in maps]
    return s[s.score >= t]  # only boards /inspect would flag


val, test = areas("val"), areas("test")
caught = val[val.is_defective]

print(f"flagged on val: {len(val)} ({len(caught)} defective, {len(val) - len(caught)} false alarms)")
print("\npredicted area on caught defective val boards (% of image), by true type:")
print((caught.groupby("defect_type")["area"].describe()[["count", "min", "50%", "max"]] * [1, 100, 100, 100]).round(2))
print("\nfalse alarms on val, predicted area %:", sorted((val[~val.is_defective].area * 100).round(2)))

low_below, medium_below = np.quantile(caught.area, [1 / 3, 2 / 3])
low_below, medium_below = round(float(low_below), 4), round(float(medium_below), 4)
print(f"\nproposed: LOW_BELOW = {low_below}   MEDIUM_BELOW = {medium_below}"
      f"   ({low_below:.2%} / {medium_below:.2%} of the image)")


def level(r):
    # area only: /inspect reports defect_type "unknown" until #9, so the
    # "missing is always high" rule can't fire yet
    return "low" if r.area < low_below else "medium" if r.area < medium_below else "high"


for name, d in [("val", val), ("test", test)]:
    d = d.assign(severity=[level(r) for r in d.itertuples()])
    print(f"\n{name}: severity of flagged boards (rows = truly defective?)")
    print(pd.crosstab(d.is_defective, d.severity).reindex(columns=["low", "medium", "high"], fill_value=0))
