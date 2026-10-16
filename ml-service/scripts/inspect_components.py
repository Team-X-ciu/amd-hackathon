"""#9 step 1: list every defect region (connected component) in the val masks.

Same five blocks as the one-mask version, wrapped in a loop over val images.
Outputs:
  splits/pcb1_components_val.csv   one row per region
  out/components_val/<class>/      one crop per region, to look at (add out/ to .gitignore)
Reads data/ only; never modifies it.

Run from ml-service/:
  uv run --with numpy --with pandas --with pillow --with scipy python scripts/inspect_components.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]            # ml-service/
DATA = ROOT / "data"                                  # VisA root: contains pcb1/
SPLIT = ROOT / "splits/pcb1.csv"
ANNO = DATA / "pcb1/image_anno.csv"                   # columns: image, label, mask
OUT_CSV = ROOT / "splits/pcb1_components_val.csv"
PREVIEW = ROOT / "out/components_val"

# Check these two against your split file (the script prints its columns first).
SPLIT_IMAGE_COL = "path"
SPLIT_SPLIT_COL = "split"

CLASSES = {1: "bent", 2: "melt", 3: "scratch", 4: "missing"}
PAD = 20                                              # pixels of context around each crop
MIN_AREA = 20
# ---- 0. Which images are val + defective? ---------------------------------
split = pd.read_csv(SPLIT)
print("split columns:", list(split.columns))
assert SPLIT_IMAGE_COL in split and SPLIT_SPLIT_COL in split, "edit SPLIT_*_COL above"

anno = pd.read_csv(ANNO)
val = split[split[SPLIT_SPLIT_COL] == "val"].merge(
    anno, left_on=SPLIT_IMAGE_COL, right_on="image", suffixes=("", "_anno"))
val = val[val["label"] != "normal"]                   # keep defective only (normal has no mask)
print("val defective images:", len(val))              # expect 50
assert len(val) == 50, "join failed: compare image paths in both CSVs"

rows = []
for r in val.itertuples():
    # ---- 1. load the mask and the real image -------------------------------
    mask = np.array(Image.open(DATA / r.mask))
    img = Image.open(DATA / r.image)
    assert set(np.unique(mask)) <= {0, 1, 2, 3, 4}, (r.mask, np.unique(mask))
    assert mask.shape == (img.height, img.width), r.image

    for cid, cname in CLASSES.items():
        # ---- 2. pixels of this class ---------------------------------------
        binary = mask == cid
        if not binary.any():
            continue

        # ---- 3. split into separate regions --------------------------------
        comp, n = ndimage.label(binary)              # 4-connectivity (default)

        # ---- 4. bbox + area of each region ---------------------------------
        for k, sl in enumerate(ndimage.find_objects(comp), start=1):
            y, x = sl
            area = int((comp[sl] == k).sum())
            if area < MIN_AREA:
                continue                             # skip specks
            rows.append(dict(
                image=r.image, cls=cname, k=k,
                area_px=area, area_frac=area / mask.size,
                y0=y.start, x0=x.start, y1=y.stop, x1=x.stop,
            ))

            # ---- 5. save a crop to look at ---------------------------------
            box = (max(x.start - PAD, 0), max(y.start - PAD, 0),
                   min(x.stop + PAD, img.width), min(y.stop + PAD, img.height))
            out = PREVIEW / cname / f"{Path(r.image).stem}_{k}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            img.crop(box).save(out)

comp_df = pd.DataFrame(rows)
comp_df.to_csv(OUT_CSV, index=False)

print("\nregions per class:\n", comp_df["cls"].value_counts())
print("\narea in pixels, per class:\n", comp_df.groupby("cls")["area_px"].describe().round(0))
print("\nregions per image (how many images have 1, 2, 3... regions):\n",
      comp_df.groupby("image").size().value_counts().sort_index())
print(f"\nwrote {OUT_CSV} and crops in {PREVIEW}")