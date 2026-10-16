"""#10 step 1 check: app/patchcore.py must give the same scores as the offline run.

Runs the module on 10 val images and compares with out/patchcore/scores_val.csv.
Also times one call on this machine (the /inspect target is under 1 s).

Run from ml-service/:
  uv run --with torch --with torchvision --with scipy --with numpy --with pandas --with pillow \
      python scripts/check_patchcore_module.py
"""
import sys
import time
from pathlib import Path

import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.patchcore import PatchCore  # noqa: E402

t0 = time.time()
pc = PatchCore(ROOT / "models")
print(f"loaded {pc.version} on {pc.device} in {time.time() - t0:.1f} s, threshold {pc.threshold:.4f}")

val = pd.read_csv(ROOT / "out/patchcore/scores_val.csv")
sample = pd.concat([val[val.is_defective].head(5), val[~val.is_defective].head(5)])

worst, times = 0.0, []
for r in sample.itertuples():
    img = Image.open(ROOT / "data" / r.path)
    t1 = time.time()
    d = pc.detect(img)
    times.append(time.time() - t1)
    worst = max(worst, abs(d.raw_score - r.score))
    print(f"{Path(r.path).stem}  offline {r.score:.4f}  module {d.raw_score:.4f}  "
          f"norm {d.score:.3f}  defective {d.is_defective!s:5}  boxes {d.boxes}")

print(f"\nmax |difference| {worst:.5f}   (expect < 0.001: the bank is stored as float16)")
print(f"time per image: first {times[0]:.2f} s, then median {sorted(times[1:])[len(times) // 2]:.2f} s")