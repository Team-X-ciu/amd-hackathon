"""#9 step 7 check: app/classifier.py must reproduce the offline classifier exactly.

Two checks on 10 val boards PatchCore flags:
  same box  : module on the box from out/patchcore/boxes_val.csv vs the offline
              probabilities (cached features + models/classifier_pcb1.npz). Expect ~0 difference.
  full path : PatchCore.detect -> main_box -> classify, as /inspect does. Its box can differ
              from the csv box by a pixel (rounding), so expect the same type, near-equal confidence.

Run from ml-service/:
  uv run --no-project --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
      --with torch --with torchvision --with scipy --with numpy --with pandas --with pillow \
      python scripts/check_classifier_module.py
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.classifier import DefectClassifier
from app.patchcore import PatchCore

OUT = ROOT / "out"
pc = PatchCore(ROOT / "models")
clf = DefectClassifier(ROOT / "models", pc.features, pc.device)
print(f"{clf.version}, classes {clf.classes}, unknown below {clf.unknown_below}")

# offline: the main boxes and their cached features from classifier_eval.py (same row order)
t = json.loads((ROOT / "models/patchcore_pcb1_threshold.json").read_text())["threshold"]
scores = pd.read_csv(OUT / "patchcore/scores_val.csv")
boxes = pd.read_csv(OUT / "patchcore/boxes_val.csv")
flagged = scores[scores.score >= t]
main = boxes[boxes.path.isin(flagged.path)].sort_values("peak").groupby("path").tail(1).reset_index(drop=True)
feats = np.load(OUT / f"features_mainbox_val_{clf.policy}.npy")
assert len(feats) == len(main), "cache doesn't match: rerun classifier_eval.py with POLICY='fixed'"
logits = ((feats - clf.mean) / clf.scale) @ clf.coef.T + clf.intercept
offline = np.exp(logits - logits.max(1, keepdims=True))
offline /= offline.sum(1, keepdims=True)

worst_same, agree, times = 0.0, 0, []
sample = main.head(10)
for i, r in sample.iterrows():
    img = Image.open(ROOT / "data" / r.path)
    p_same = clf.probabilities(img, (r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0))
    worst_same = max(worst_same, float(np.abs(p_same - offline[i]).max()))

    t0 = time.perf_counter()
    det = pc.detect(img)
    kind, conf = clf.classify(img, det.main_box)
    times.append(time.perf_counter() - t0)
    off_kind = clf.classes[offline[i].argmax()] if offline[i].max() >= clf.unknown_below else "unknown"
    agree += kind == off_kind
    print(
        f"{Path(r.path).stem}  offline {off_kind:8s} {offline[i].max():.3f}   /inspect path {kind:8s} {conf:.3f}"
        f"   box csv {(r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0)} vs module {det.main_box}"
    )

print(f"\nsame box: max |probability difference| {worst_same:.6f}   (expect < 0.001)")
print(f"full path: same type on {agree}/{len(sample)} boards   (expect all, or all but a borderline one)")
print(f"detect + classify per board: median {np.median(times):.2f} s")
