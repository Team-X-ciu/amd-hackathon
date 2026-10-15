import numpy as np
import pandas as pd
from PIL import Image

D = "data/"
anno = pd.read_csv(D + "pcb1/image_anno.csv")
print(anno.columns.tolist())
print(anno.head(3))
print(anno["label"].value_counts())

bad = anno[anno["label"] != "normal"]
for _, row in bad.head(3).iterrows():
    m = np.array(Image.open(D + row["mask"]))
    print(row["image"], row["label"], m.shape, np.unique(m, return_counts=True))