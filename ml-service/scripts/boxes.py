"""#8: anomaly maps -> defect mask -> bounding boxes, and check they hit the real defect.

Mask rule: pixels with map >= the image threshold. That is consistent with the image
decision, because image score = max of the map: a board is flagged exactly when
its mask is non-empty.

Boxes are scaled from the 256 map back to the original image size, so the frontend
can draw them on the real photo and #9 can crop with them.

Check (localisation): for each defective board we flag, does at least one box
overlap the ground-truth defect? And how many boxes per flagged board?

Inputs:  out/patchcore/{scores,maps}_{val,test}.*, models/patchcore_pcb1_threshold.json
Output:  out/patchcore/boxes_{val,test}.csv   one row per box (original-image pixels)

Run from ml-service/:
  uv run --with numpy --with pandas --with pillow --with scipy python scripts/boxes.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out/patchcore"
MIN_AREA = 16        # map pixels (of 256x256); smaller blobs are ignored

t = json.loads((ROOT / "models/patchcore_pcb1_threshold.json").read_text())["threshold"]
anno = pd.read_csv(ROOT / "data/pcb1/image_anno.csv").set_index("image")
print(f"threshold {t:.4f}")


def boxes_from_map(m, t):
    """Connected regions of (m >= t) -> list of (y0, x0, y1, x1, peak).
    Small regions are dropped, except the one holding the map's maximum: that pixel
    is what flagged the board, so a flagged board always gets at least one box."""
    comp, _ = ndimage.label(m >= t, structure=np.ones((3, 3)))
    top = comp[np.unravel_index(np.argmax(m), m.shape)]  # label of the peak region (0 if not flagged)
    out = []
    for k, sl in enumerate(ndimage.find_objects(comp), start=1):
        region = comp[sl] == k
        if region.sum() < MIN_AREA and k != top:
            continue
        out.append((sl[0].start, sl[1].start, sl[0].stop, sl[1].stop, float(m[sl][region].max())))
    return out


summary = {"threshold": t}
for name in ["val", "test"]:
    scores = pd.read_csv(OUT / f"scores_{name}.csv")
    maps = np.load(OUT / f"maps_{name}.npy").astype(np.float32)
    size = maps.shape[-1]
    rows, hits, flagged_defective, n_boxes = [], 0, 0, []

    for i, r in scores.iterrows():
        W, H = Image.open(ROOT / "data" / r.path).size
        sx, sy = W / size, H / size                       # map pixel -> original pixel
        bxs = boxes_from_map(maps[i], t)
        for y0, x0, y1, x1, peak in bxs:
            rows.append(dict(path=r.path, x0=round(x0 * sx), y0=round(y0 * sy),
                             x1=round(x1 * sx), y1=round(y1 * sy), peak=round(peak, 4)))

        if r.is_defective and r.score >= t:              # a defect we caught: did a box find it?
            flagged_defective += 1
            n_boxes.append(len(bxs))
            gt = np.asarray(Image.open(ROOT / "data" / anno.loc[r.path, "mask"])) > 0
            hit = any(gt[round(y0 * sy):round(y1 * sy), round(x0 * sx):round(x1 * sx)].any()
                      for y0, x0, y1, x1, _ in bxs)
            hits += hit

    pd.DataFrame(rows, columns=["path", "x0", "y0", "x1", "y1", "peak"]).to_csv(OUT / f"boxes_{name}.csv", index=False)
    summary[name] = {
        "caught_defective": flagged_defective,
        "box_hits_gt": hits,
        "hit_rate": round(hits / max(flagged_defective, 1), 3),
        "boxes_per_caught_board": round(float(np.mean(n_boxes)) if n_boxes else 0.0, 2),
    }

print(json.dumps(summary, indent=2))
(OUT / "boxes_summary.json").write_text(json.dumps(summary, indent=2))