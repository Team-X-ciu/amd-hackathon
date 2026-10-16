"""#9 step 5: the `unknown` rule, and the end-to-end number on PatchCore's boxes.

Model (step 4 winner): WRN-50 layer2+3 features of the "bbox" crop -> StandardScaler
-> LogisticRegression(C=1, class_weight="balanced").

1. Unknown rule, from CV probabilities on the 138 ground-truth regions:
   answer a type only when the top probability >= t, else "unknown".
   For each t: coverage (share answered) and accuracy on what is answered.
   Pick the lowest t whose answered accuracy reaches TARGET_ACC (more coverage = more useful).

2. End to end, which is what the UI shows: on each val board PatchCore flags, take its
   main box (highest peak, out/patchcore/boxes_val.csv), crop it, classify it with a
   model trained only on OTHER boards' ground-truth regions (grouped CV by image),
   and compare with the board's true type (splits/pcb1.csv). Good boards that
   PatchCore flagged (false alarms) should ideally come out "unknown".

Test is not touched here. Run from ml-service/:
  uv run --no-project --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
      --with torch --with torchvision --with scipy --with numpy --with pandas --with pillow --with scikit-learn \
      python scripts/classifier_eval.py
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
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from crops import crop_region

from app.patchcore import _Features

POLICY, C, N_REPEATS = "fixed", 1.0, 10
TARGET_ACC = 0.90  # answered predictions must be right at least 90% of the time
OUT = ROOT / "out"

# ---- ground-truth regions (training data) -------------------------------------------
regions = pd.read_csv(ROOT / "splits/pcb1_components_val.csv")
X = np.load(OUT / f"features_{POLICY}.npy")  # from scripts/features.py, same row order
y, groups = regions["cls"].to_numpy(), regions["image"].to_numpy()
assert len(X) == len(regions), "features cache doesn't match the regions csv: rerun features.py"


def model():
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, class_weight="balanced", max_iter=5000))


# ---- PatchCore's main box per flagged val board (what /inspect would crop) -----------
t_pc = json.loads((ROOT / "models/patchcore_pcb1_threshold.json").read_text())["threshold"]
scores = pd.read_csv(OUT / "patchcore/scores_val.csv")
boxes = pd.read_csv(OUT / "patchcore/boxes_val.csv")
flagged = scores[scores.score >= t_pc]
main = boxes[boxes.path.isin(flagged.path)].sort_values("peak").groupby("path").tail(1)  # highest peak
truth = pd.read_csv(ROOT / "splits/pcb1.csv").set_index("path")
main = main.assign(
    true=[truth.loc[p, "defect_type"] if truth.loc[p, "is_defective"] else "good" for p in main.path]
).reset_index(drop=True)


@torch.no_grad()
def box_features():
    cache = OUT / f"features_mainbox_val_{POLICY}.npy"
    if cache.exists():
        return np.load(cache)
    net = _Features()
    feats = []
    for r in main.itertuples():
        img = Image.open(ROOT / "data" / r.path).convert("RGB")
        crop, _ = crop_region(img, r.y0, r.x0, r.y1, r.x1, POLICY)
        x = torch.from_numpy(np.array(crop)).permute(2, 0, 1)[None].float().div(255)
        feats.append(net(x).mean(dim=(2, 3))[0].numpy())
    np.save(cache, np.stack(feats))
    return np.load(cache)


print(f"extracting features for {len(main)} PatchCore main boxes ...")
XB = box_features()
is_good = (main.true == "good").to_numpy()

# ---- grouped CV, repeated: probabilities for GT regions AND for main boxes ------------
reg_probs, box_probs = [], []
for seed in range(N_REPEATS):
    pr = np.zeros((len(X), 4))
    pb = np.zeros((len(XB), 4))
    filled = np.zeros(len(XB), bool)
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
    for tr, te in cv.split(X, y, groups):
        m = model().fit(X[tr], y[tr])
        pr[te] = m.predict_proba(X[te])
        held_out = set(groups[te])  # boards whose regions the model never saw
        b = main.path.isin(held_out).to_numpy() & ~is_good
        if b.any():
            pb[b] = m.predict_proba(XB[b])
            filled |= b
    # boards with no GT region in training (false alarms, or a board whose regions were all
    # specks) were never seen by any model, so the model fit on everything is fair for them
    m_all = model().fit(X, y)
    if (~filled).any():
        pb[~filled] = m_all.predict_proba(XB[~filled])
    reg_probs.append(pr)
    box_probs.append(pb)
classes = m_all.classes_


def apply(probs, t):
    """Top class, or 'unknown' when the top probability is below t."""
    pred = classes[probs.argmax(1)].astype(object)
    pred[probs.max(1) < t] = "unknown"
    return pred


# ---- 1. risk-coverage on GT regions -> choose t ------------------------------------
print(f"\n1. unknown rule on {len(X)} ground-truth regions (CV, {N_REPEATS} repeats)")
print("   t     coverage  accuracy-of-answered")
rows = []
for t in np.round(np.arange(0.30, 0.96, 0.05), 2):
    cov, acc = [], []
    for pr in reg_probs:
        pred = apply(pr, t)
        ans = pred != "unknown"
        cov.append(ans.mean())
        acc.append((pred[ans] == y[ans]).mean() if ans.any() else np.nan)
    rows.append((t, np.mean(cov), np.nanmean(acc)))
    print(f"  {t:.2f}   {np.mean(cov):6.1%}     {np.nanmean(acc):6.1%}")
ok = [r for r in rows if r[2] >= TARGET_ACC]
t_unknown = ok[0][0] if ok else rows[-1][0]
print(
    f"   -> chosen t = {t_unknown} "
    + (
        f"(lowest t with answered accuracy >= {TARGET_ACC:.0%})"
        if ok
        else f"(target {TARGET_ACC:.0%} never reached: highest t)"
    )
)

# ---- 2. end to end on PatchCore's main boxes --------------------------------------
defective = ~is_good
truth_def = main.true[defective].to_numpy()
f1_plain, f1_unk, cov_unk, acc_unk = [], [], [], []
for pb in box_probs:
    plain = classes[pb[defective].argmax(1)]
    f1_plain.append(f1_score(truth_def, plain, average="macro"))
    pred = apply(pb[defective], t_unknown)
    ans = pred != "unknown"
    cov_unk.append(ans.mean())
    acc_unk.append((pred[ans] == truth_def[ans]).mean())
print(f"\n2. end to end: {defective.sum()} defective boards PatchCore caught, main box only")
print(
    f"   no unknown rule: macro-F1 {np.mean(f1_plain):.3f} ± {np.std(f1_plain):.3f}   (GT-region CV: 0.822)"
)
print(
    f"   with t = {t_unknown}: answers {np.mean(cov_unk):.0%} of boards, right on {np.mean(acc_unk):.0%} of those"
)

first = apply(box_probs[0], t_unknown)
print("\n   first repeat, rows = true type of the board ('good' = PatchCore false alarm):")
print(pd.crosstab(main.true.rename("true"), pd.Series(first, name="pred")))

choice = {"policy": POLICY, "C": C, "unknown_below": float(t_unknown), "target_acc": TARGET_ACC}
(OUT / "classifier_choice.json").write_text(json.dumps(choice, indent=2))
print(f"\nsaved choice to {OUT / 'classifier_choice.json'}")
