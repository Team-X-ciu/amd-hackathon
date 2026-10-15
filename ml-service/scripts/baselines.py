"""#9 step 3: baselines on the val regions, scored with repeated grouped CV.

Two models:
  dummy           always predicts the most common class (melt): the floor
  handcrafted_lr  logistic regression on 5 shape numbers per region: the real bar
                  the WRN-50 features in step 4 must beat

CV: StratifiedGroupKFold groups by image, so regions of one board never sit in
both train and eval. Repeated with 10 shuffles because 138 regions is small and
one split alone is noisy: we report mean ± std of macro-F1.

Run from ml-service/:
  uv run --with numpy --with pandas --with scikit-learn python scripts/baselines.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
d = pd.read_csv(ROOT / "splits/pcb1_components_val.csv")

y = d["cls"].to_numpy()
groups = d["image"].to_numpy()        # one group = one board image
print("regions per class:", d["cls"].value_counts().to_dict(), "| images:", d["image"].nunique())


def handcrafted(d):
    """Shape-only features from the bbox and area. No pixels, no network."""
    h = d.y1 - d.y0
    w = d.x1 - d.x0
    return pd.DataFrame({
        "log_area": np.log1p(d.area_px),
        "h": h,
        "w": w,
        "aspect": np.maximum(h, w) / np.minimum(h, w),
        "fill": d.area_px / (h * w),
        })


def evaluate(model, X, n_repeats=10):
    """Grouped 5-fold CV, repeated with different shuffles.
    Returns macro-F1 of each repeat and the predictions of the first repeat."""
    scores, first = [], None
    for seed in range(n_repeats):
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        pred = cross_val_predict(model, X, y, groups=groups, cv=cv)   # every region predicted once, by a model that never saw its image
        scores.append(f1_score(y, pred, average="macro"))
        if first is None:
            first = pred
    return np.array(scores), first


X = handcrafted(d)
print("features:", list(X.columns))

models = {
    "dummy": DummyClassifier(strategy="most_frequent"),
    "handcrafted_lr": make_pipeline(StandardScaler(),
                                    LogisticRegression(class_weight="balanced", max_iter=1000)),
}


for name, model in models.items():
    s, pred = evaluate(model, X)
    print(f"\n{name:15s} macro-F1 {s.mean():.3f} ± {s.std():.3f}   (10 repeats)")
    print(pd.crosstab(pd.Series(y, name="true"), pd.Series(pred, name="pred")))