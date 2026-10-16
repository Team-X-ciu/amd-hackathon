"""#9 step 2: two crop policies for a defect region, plus a sheet to compare them.

Policy "bbox":  square around the region's bounding box (+ context), resized to 224.
                The defect fills the frame; its real size is lost.
Policy "fixed": 224x224 window at full resolution, centred on the region.
                Real scale kept: small defects stay small. If the region doesn't
                fit, the window grows to fit it and is then resized to 224.

Both only need a bbox (y0, x0, y1, x1), so at inference the same function
works on boxes from PatchCore's predicted mask.

Run from ml-service/:
  uv run --with pandas --with pillow python scripts/crops.py
"""

import sys
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]  # ml-service/
DATA = ROOT / "data"
COMPONENTS = ROOT / "splits/pcb1_components_val.csv"
OUT = ROOT / "out/crop_policies.png"

# The crop code lives in app/crops.py so /inspect and these scripts use exactly the same crops.
sys.path.insert(0, str(ROOT))
from app.crops import SIZE, crop_region


def draw_bbox(tile, box, y0, x0, y1, x1):
    """Draw the defect's bbox on a 224 crop (for viewing only, never for training)."""
    s = SIZE / (box[2] - box[0])  # how much the crop was scaled
    ImageDraw.Draw(tile).rectangle(
        ((x0 - box[0]) * s, (y0 - box[1]) * s, (x1 - box[0]) * s, (y1 - box[1]) * s), outline="red"
    )


if __name__ == "__main__":
    d = pd.read_csv(COMPONENTS)

    # per class: smallest, median and largest region -> 12 rows
    picks = []
    for cls, g in d.groupby("cls"):
        g = g.sort_values("area_px").reset_index(drop=True)
        picks += [g.iloc[0], g.iloc[len(g) // 2], g.iloc[-1]]

    ROW = SIZE + 20
    sheet = Image.new("RGB", (2 * SIZE + 10, len(picks) * ROW), "white")
    for i, r in enumerate(picks):
        img = Image.open(DATA / r.image).convert("RGB")
        y = i * ROW
        ImageDraw.Draw(sheet).text(
            (2, y + 3), f"{r.cls} {Path(r.image).stem}_{r.k}  {r.area_px} px", fill="black"
        )
        for j, policy in enumerate(["bbox", "fixed"]):
            tile, box = crop_region(img, r.y0, r.x0, r.y1, r.x1, policy)
            draw_bbox(tile, box, r.y0, r.x0, r.y1, r.x1)
            sheet.paste(tile, (j * (SIZE + 10), y + 18))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"saved {OUT}  (left: bbox policy, right: fixed policy)")
