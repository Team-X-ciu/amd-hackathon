"""#8: pick the PatchCore decision threshold on val, then check it once on test.

Rule: the highest threshold that still catches at least RECALL_TARGET of the
defective val boards. In QC a missed defect (false negative) costs more than an
extra look by the operator (false positive), so we fix recall and accept the
false-positive rate that comes with it.

Inputs:  out/patchcore/scores_{val,test}.csv  (from patchcore_pcb1.py)
Output:  models/patchcore_pcb1_threshold.json  (read by /inspect in #10)

Run from ml-service/:
  uv run --with numpy --with pandas python scripts/threshold.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RECALL_TARGET = 0.95

val = pd.read_csv(ROOT / "out/patchcore/scores_val.csv")
test = pd.read_csv(ROOT / "out/patchcore/scores_test.csv")

for name, d in [("val", val), ("test", test)]:
    g, b = d.loc[~d.is_defective, "score"], d.loc[d.is_defective, "score"]
    print(f"{name}: good {g.min():.2f}..{g.max():.2f}   defective {b.min():.2f}..{b.max():.2f}")


def pick_threshold(scores_defective, target):
    """Highest t such that at least `target` of the defective scores are >= t."""
    s = np.sort(scores_defective) 
    k = int(np.floor((1 - target) * len(s)))   # boards we may miss: 0.05 * 50 = 2.5 -> 2
    return s[k]                                # 3rd-lowest defective score (index 2)


def report(d, t):
    """Confusion counts and rates for 'defective if score >= t'."""
    pred = d["score"] >= t
    y = d["is_defective"]
    tp = int((pred & y).sum())      # defective, flagged       (caught)
    fn = int((~pred & y).sum())     # defective, not flagged   (missed: the bad one)
    fp = int((pred & ~y).sum())     # good, flagged            (false alarm)
    tn = int((~pred & ~y).sum())    # good, not flagged
    recall = tp / (tp + fn)         # share of defective boards we catch
    fpr = fp / (fp + tn)            # share of good boards we wrongly flag
    precision = tp / (tp + fp)      # of flagged boards, how many are really defective
    return dict(tp=tp, fn=fn, fp=fp, tn=tn,
                recall=round(recall, 3), fpr=round(fpr, 3), precision=round(precision, 3))


t = pick_threshold(val.loc[val.is_defective, "score"].to_numpy(), RECALL_TARGET)
res = {"threshold": float(t), "recall_target": RECALL_TARGET,
       "val": report(val, t), "test": report(test, t)}      # test: looked at once, never tuned on
print(json.dumps(res, indent=2))
(ROOT / "models/patchcore_pcb1_threshold.json").write_text(json.dumps(res, indent=2))