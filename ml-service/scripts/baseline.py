import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, f1_score

SEED = 42

df = pd.read_csv("splits/pcb1.csv")
val = df[(df["split"] == "val") & df["is_defective"]]
X, y = [[0]] * len(val), val["defect_type"]     

clf = DummyClassifier(strategy="most_frequent", random_state=SEED).fit(X, y)
pred = clf.predict(X)
metrics = {
    "accuracy": round(accuracy_score(y, pred), 3),
    "macro_f1": round(f1_score(y, pred, average="macro"), 3),
    "n": len(val),
}
print("predicts always:", pred[0], metrics)

commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
log = Path("runs.csv")
new = not log.exists()
with log.open("a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["date", "commit", "run", "split", "seed", "metrics"])
    w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), commit,
                "dummy_most_frequent", "val", SEED, json.dumps(metrics)])