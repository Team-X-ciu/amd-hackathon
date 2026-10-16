"""#9 step 4: WRN-50 features on defect crops vs the shape baseline (0.761 macro-F1).

For each defect region (splits/pcb1_components_val.csv) and each crop policy
(scripts/crops.py: "bbox" and "fixed"), take the crop, run the SAME backbone as
PatchCore (app/patchcore.py: WRN-50 layer2+3), average over the crop -> 1536 numbers.
Then logistic regression, scored with the same repeated grouped CV as baselines.py.

Compared:
  shape_lr          the 5 shape numbers (baseline to beat)
  wrn_<policy>      WRN-50 features only
  wrn_<policy>+shape  both together

Features are cached in out/features_<policy>.npy (delete to recompute).

Run from ml-service/ (CPU torch, a few minutes the first time):
  uv run --no-project --index https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match \
      --with torch --with torchvision --with scipy --with numpy --with pandas --with pillow --with scikit-learn \
      python scripts/features.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
from crops import SIZE, crop_region

from app.patchcore import _Features  # same backbone + layers as PatchCore

d = pd.read_csv(ROOT / "splits/pcb1_components_val.csv")
y, groups = d["cls"].to_numpy(), d["image"].to_numpy()
print(f"{len(d)} regions in {d.image.nunique()} images:", d.cls.value_counts().to_dict())


def shape(d):
    h, w = d.y1 - d.y0, d.x1 - d.x0
    return np.column_stack(
        [
            np.log1p(d.area_px),
            h,
            w,
            np.maximum(h, w) / np.minimum(h, w),
            d.area_px / (h * w),
        ]
    )


@torch.no_grad()
def wrn_features(policy):
    cache = ROOT / f"out/features_{policy}.npy"
    if cache.exists():
        return np.load(cache)
    model = _Features()
    feats, images = [], {}
    for r in d.itertuples():
        if r.image not in images:  # each board image read once
            images = {r.image: Image.open(ROOT / "data" / r.image).convert("RGB")}
        crop, _ = crop_region(images[r.image], r.y0, r.x0, r.y1, r.x1, policy)
        x = torch.from_numpy(np.array(crop)).permute(2, 0, 1)[None].float().div(255)
        feats.append(model(x).mean(dim=(2, 3))[0].numpy())  # 1536-d: average over the crop
    feats = np.stack(feats)
    cache.parent.mkdir(exist_ok=True)
    np.save(cache, feats)
    return feats


def evaluate(model, X, n_repeats=10):
    """Same harness as baselines.py: grouped 5-fold CV by image, 10 shuffles."""
    scores, first = [], None
    for seed in range(n_repeats):
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        pred = cross_val_predict(model, X, y, groups=groups, cv=cv)
        scores.append(f1_score(y, pred, average="macro"))
        first = pred if first is None else first
    return np.array(scores), first


def lr(C):
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(C=C, class_weight="balanced", max_iter=5000),
    )


S = shape(d)
X = {"shape": S}
for policy in ["bbox", "fixed"]:
    print(f"extracting WRN-50 features, policy {policy} (crops {SIZE}x{SIZE}) ...")
    F = wrn_features(policy)
    X[f"wrn_{policy}"] = F
    X[f"wrn_{policy}+shape"] = np.hstack([F, S])

results = []
for name, Xi in X.items():
    # C = regularisation strength; small C = simpler model. 1536 features vs 138 regions -> try small ones
    for C in [1.0] if name == "shape" else [0.001, 0.01, 0.1, 1.0]:
        s, pred = evaluate(lr(C), Xi)
        results.append((name, C, s.mean(), s.std(), pred))
        print(f"{name:18s} C={C:<6} macro-F1 {s.mean():.3f} ± {s.std():.3f}")

best = max(results, key=lambda r: r[2])
print(f"\nbest: {best[0]} C={best[1]}  macro-F1 {best[2]:.3f} ± {best[3]:.3f}   (shape baseline 0.761)")
print(pd.crosstab(pd.Series(y, name="true"), pd.Series(best[4], name="pred")))
