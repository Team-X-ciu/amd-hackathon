from pathlib import Path

from sklearn.model_selection import train_test_split

import numpy as np
import pandas as pd
from PIL import Image

DATA = Path("data")
ID2CLASS = {1: "bent", 2: "melt", 3: "scratch", 4: "missing"}
SEED = 42

def mask_info(mask_path: Path) -> tuple[str, int, float]:
    """Return (defect_type, n_types, area_ratio) for one defect mask."""
    mask = np.array(Image.open(mask_path))
    values, counts = np.unique(mask, return_counts=True)

    valid = values != 0
    values = values[valid]
    counts = counts[valid]
    i = np.argmax(counts)
    defect_type = ID2CLASS[int(values[i])]
    n_types = len(values)
    area_ratio = counts.sum() / mask.size
    return defect_type, n_types, area_ratio

def build_labels() -> pd.DataFrame:
    anno = pd.read_csv(DATA / "pcb1" / "image_anno.csv")
    rows = []
    for r in anno.itertuples():
        row = {"path": r.image, "csv_label": r.label, "is_defective": r.label != "normal",
               "defect_type": None, "n_types": 0, "area_ratio": 0.0}
        if row["is_defective"]:
            # TODO: call mask_info(DATA / r.mask) and put the 3 results into row
            defect_type, n_types, area_ratio = mask_info(DATA / r.mask)
            row["defect_type"] = defect_type
            row["n_types"] = n_types
            row["area_ratio"] = area_ratio 
        rows.append(row)
    return pd.DataFrame(rows)




def add_split(df: pd.DataFrame) -> pd.DataFrame:
    """Official VisA split for train; official test split 50/50 into val/test, stratified by type."""
    official = pd.read_csv(DATA / "split_csv" / "1cls.csv")
    official = official[official["object"] == "pcb1"]

    # TODO: merge official[["image", "split"]] into df on path == image
    df = df.merge(official[["image", "split"]], left_on="path", right_on="image",
              how="left", validate="one_to_one")
    assert len(df) == 1104, "merge changed the number of rows"
    assert df["split"].notna().all(), "some images have no official split"

    strata = df["defect_type"].fillna("good")
    test_rows = df[df["split"] == "test"]

    val_idx, test_idx = train_test_split(
    test_rows.index,                      # split the row labels, not the whole table
    test_size=0.5,                        # 50/50
    stratify=strata[test_rows.index],     # every defect type in both halves
    random_state=SEED,                    # same split every run
    )   

    df.loc[val_idx, "split"] = "val"

    assert df["path"].is_unique, "an image appears twice"
    assert not df[df["split"] == "train"]["is_defective"].any(), "defective board in train"
    return df

if __name__ == "__main__":
    df = build_labels()
    bad = df[df.is_defective]

    print(df.is_defective.value_counts())
    print(bad.defect_type.value_counts())
    print(bad.n_types.value_counts())
    print(bad.area_ratio.describe(percentiles=[.25, .5, .75, .9]))

    # sanity check: for single-type boards, mask class must equal the CSV label
    single = bad[~bad.csv_label.str.contains(",")]
    wrong = single[single.defect_type != single.csv_label]
    print("mismatches:", len(wrong))
    print(wrong[["path", "csv_label", "defect_type"]])

    df = add_split(df)
    print(pd.crosstab(df["split"], df["defect_type"].fillna("good")))

    Path("splits").mkdir(exist_ok=True)
    df.drop(columns=["image"]).to_csv("splits/pcb1.csv", index=False)   # "image" is the duplicate column from the merge

