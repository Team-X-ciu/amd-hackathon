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
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]           # ml-service/
DATA = ROOT / "data"
COMPONENTS = ROOT / "splits/pcb1_components_val.csv"
OUT = ROOT / "out/crop_policies.png"

SIZE = 224        # network input size (ImageNet convention)
CONTEXT = 0.5     # bbox policy: add 50% of the defect's side on each side
MIN_SIDE = 32     # bbox policy: never crop smaller than this (limits blow-up of tiny defects)


def square_box(cy, cx, side, W, H):
    """Square of `side` px centred at (cy, cx), shifted to stay inside the image.
    Returns PIL order: (left, top, right, bottom)."""
    side = min(side, W, H)
    x0 = min(max(int(cx - side / 2), 0), W - side)
    y0 = min(max(int(cy - side / 2), 0), H - side)
    return (x0, y0, x0 + side, y0 + side)


def crop_region(img, y0, x0, y1, x1, policy):
    """Cut one region out of a PIL image with the given policy. Returns (224x224 crop, box used)."""
    h, w = y1 - y0, x1 - x0
    cy, cx = (y0 + y1) / 2, (x0 + x1) / 2
    if policy == "bbox":
        side = max(int(max(h, w) * (1 + 2 * CONTEXT)), MIN_SIDE)
    elif policy == "fixed":
        side = max(SIZE, int(max(h, w) * 1.2))    # grow only if the defect doesn't fit
    else:
        raise ValueError(f"unknown policy {policy!r}")
    box = square_box(cy, cx, side, img.width, img.height)
    return img.crop(box).resize((SIZE, SIZE), Image.BILINEAR), box


def draw_bbox(tile, box, y0, x0, y1, x1):
    """Draw the defect's bbox on a 224 crop (for viewing only, never for training)."""
    s = SIZE / (box[2] - box[0])                  # how much the crop was scaled
    ImageDraw.Draw(tile).rectangle(
        ((x0 - box[0]) * s, (y0 - box[1]) * s, (x1 - box[0]) * s, (y1 - box[1]) * s),
        outline="red")


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
            (2, y + 3), f"{r.cls} {Path(r.image).stem}_{r.k}  {r.area_px} px", fill="black")
        for j, policy in enumerate(["bbox", "fixed"]):
            tile, box = crop_region(img, r.y0, r.x0, r.y1, r.x1, policy)
            draw_bbox(tile, box, r.y0, r.x0, r.y1, r.x1)
            sheet.paste(tile, (j * (SIZE + 10), y + 18))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(OUT)
    print(f"saved {OUT}  (left: bbox policy, right: fixed policy)")