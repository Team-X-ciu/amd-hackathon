"""#9 step 6: fit the final defect-type classifier, save it, and run test ONCE.

Choice (step 5, out/classifier_choice.json): WRN-50 layer2+3 features of the "fixed"
crop -> StandardScaler -> LogisticRegression(C=1, balanced), "unknown" below 0.9.

Fit on all 138 val ground-truth regions. Saved as plain numbers (scaler mean/scale,
weights, bias, classes) in models/classifier_pcb1.npz: /inspect runs it with numpy,
so the file does not depend on the scikit-learn version.

Test (used once, nothing is tuned on it): for each test board PatchCore flags, classify
its main box, exactly as /inspect will.

Run from ml-service/:
  uv run --no-project --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
      --with torch --with torchvision --with scipy --with numpy --with pandas --with pillow --with scikit-learn \
      python scripts/train_classifier.py
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from crops import crop_region

from app.patchcore import _Features

OUT = ROOT / "out"
choice = json.loads((OUT / "classifier_choice.json").read_text())
POLICY, C, T_UNKNOWN = choice["policy"], choice["C"], choice["unknown_below"]
assert POLICY == "fixed", "step 5 chose 'fixed'; rerun classifier_eval.py with POLICY='fixed'"

# ---- fit on all val GT regions -----------------------------------------------------
regions = pd.read_csv(ROOT / "splits/pcb1_components_val.csv")
X = np.load(OUT / f"features_{POLICY}.npy")
y = regions["cls"].to_numpy()
model = make_pipeline(StandardScaler(), LogisticRegression(C=C, class_weight="balanced", max_iter=5000)).fit(
    X, y
)
scaler, lr = model.named_steps["standardscaler"], model.named_steps["logisticregression"]

params = {
    "mean": scaler.mean_,
    "scale": scaler.scale_,
    "coef": lr.coef_,
    "intercept": lr.intercept_,
    "classes": lr.classes_.astype(str),
    "unknown_below": np.float64(T_UNKNOWN),
    "policy": np.array(POLICY),
}


def predict_proba_numpy(p, feats):
    """What /inspect runs: no scikit-learn, just numpy."""
    logits = ((feats - p["mean"]) / p["scale"]) @ p["coef"].T + p["intercept"]
    e = np.exp(logits - logits.max(1, keepdims=True))
    return e / e.sum(1, keepdims=True)


assert np.allclose(predict_proba_numpy(params, X), model.predict_proba(X), atol=1e-6), "numpy != sklearn"
(ROOT / "models").mkdir(exist_ok=True)
np.savez(ROOT / "models/classifier_pcb1.npz", **params)
print(f"saved models/classifier_pcb1.npz: classes {params['classes'].tolist()}, unknown below {T_UNKNOWN}")

# ---- test, once: main box of each board PatchCore flags -----------------------------
t_pc = json.loads((ROOT / "models/patchcore_pcb1_threshold.json").read_text())["threshold"]
scores = pd.read_csv(OUT / "patchcore/scores_test.csv")
boxes = pd.read_csv(OUT / "patchcore/boxes_test.csv")
flagged = scores[scores.score >= t_pc]
main = boxes[boxes.path.isin(flagged.path)].sort_values("peak").groupby("path").tail(1).reset_index(drop=True)
truth = pd.read_csv(ROOT / "splits/pcb1.csv").set_index("path")
main["true"] = [truth.loc[p, "defect_type"] if truth.loc[p, "is_defective"] else "good" for p in main.path]

net = _Features()
feats = []
with torch.no_grad():
    for r in main.itertuples():
        img = Image.open(ROOT / "data" / r.path).convert("RGB")
        crop, _ = crop_region(img, r.y0, r.x0, r.y1, r.x1, POLICY)
        x = torch.from_numpy(np.array(crop)).permute(2, 0, 1)[None].float().div(255)
        feats.append(net(x).mean(dim=(2, 3))[0].numpy())
probs = predict_proba_numpy(params, np.stack(feats))
top = params["classes"][probs.argmax(1)].astype(object)
pred = top.copy()
pred[probs.max(1) < T_UNKNOWN] = "unknown"

d = (main.true != "good").to_numpy()
ans = d & (pred != "unknown")
f1 = f1_score(main.true[d], top[d], average="macro")
print(f"\nTEST: {d.sum()} defective boards PatchCore caught (+{(~d).sum()} false alarms)")
print(f"  no unknown rule: macro-F1 {f1:.3f}   (val end to end: 0.786)")
print(
    f"  with unknown below {T_UNKNOWN}: answers {ans.sum() / d.sum():.0%} of boards, "
    f"right on {(pred[ans] == main.true[ans]).mean():.0%} of those   (val: 75%, 91%)"
)
print(f"  false alarms -> unknown: {(pred[~d] == 'unknown').sum()} of {(~d).sum()}")
print(pd.crosstab(main.true.rename("true"), pd.Series(pred, name="pred")))
