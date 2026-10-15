"""#8: fit PatchCore on pcb1 (our split), score val + test, save what /inspect needs.

Plain PyTorch + torchvision, no anomalib, so the same code runs in the notebook,
on a laptop and later inside the ML service (#10). Steps:

  1. features   WideResNet-50 layer2 + layer3, 3x3 average pooling, layer3
                upsampled to layer2's grid -> one 1536-d vector per image patch
  2. memory     all patch vectors of the 904 good train images
  3. coreset    greedy coreset keeps CORESET (1%) of them: the memory bank
  4. score      patch score = distance to the nearest memory vector;
                anomaly map = patch scores upsampled + Gaussian blur;
                image score = max of the map

Run from the folder that holds data/pcb1 and splits/pcb1.csv
(ml-service/ on the laptop, ~/work on the notebook):

  python patchcore_pcb1.py                    # coreset 1%, image size 256
  python patchcore_pcb1.py --coreset 0.01 --size 256

Outputs (none of them go in git):
  models/patchcore_pcb1.pt          memory bank + settings (load this in #10)
  out/patchcore/scores_{val,test}.csv   path, is_defective, defect_type, score
  out/patchcore/maps_{val,test}.npy     anomaly maps, float16, same row order
  out/patchcore/summary.json            AUROCs and timings
"""
import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from PIL import Image
from sklearn.metrics import roc_auc_score
from torchvision.models import Wide_ResNet50_2_Weights, wide_resnet50_2

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)   # ImageNet stats
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


# ---------------------------------------------------------------- data -------
def load_images(root, paths, size):
    """Read images, resize to size x size, return float tensor N x 3 x H x W in [0, 1]."""
    out = np.stack([
        np.asarray(Image.open(root / "data" / p).convert("RGB").resize((size, size), Image.BILINEAR))
        for p in paths])
    return torch.from_numpy(out).permute(0, 3, 1, 2).float() / 255


def load_masks(root, mask_paths, size):
    """Binary GT masks resized to size x size (all zeros for good images)."""
    masks = []
    for m in mask_paths:
        if isinstance(m, str):
            img = Image.open(root / "data" / m).resize((size, size), Image.NEAREST)
            masks.append(np.asarray(img) > 0)
        else:
            masks.append(np.zeros((size, size), bool))
    return np.stack(masks)


# ------------------------------------------------------------ features -------
class Features(torch.nn.Module):
    """WideResNet-50 truncated after layer3; returns 1536-d patch features."""

    def __init__(self, pretrained=True):
        super().__init__()
        net = wide_resnet50_2(weights=Wide_ResNet50_2_Weights.IMAGENET1K_V1 if pretrained else None)
        self.stem = torch.nn.Sequential(net.conv1, net.bn1, net.relu, net.maxpool, net.layer1)
        self.layer2, self.layer3 = net.layer2, net.layer3
        self.eval()

    @torch.no_grad()
    def forward(self, x):                                  # x: B x 3 x S x S in [0, 1]
        x = (x - MEAN.to(x.device)) / STD.to(x.device)
        f2 = self.layer2(self.stem(x))                     # B x 512  x S/8  x S/8
        f3 = self.layer3(f2)                               # B x 1024 x S/16 x S/16
        f2 = F.avg_pool2d(f2, 3, 1, 1)                     # each patch sees its 3x3 neighbours
        f3 = F.avg_pool2d(f3, 3, 1, 1)
        f3 = F.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        return torch.cat([f2, f3], 1)                      # B x 1536 x S/8 x S/8


def extract(model, images, device, batch=16):
    """Run the feature model in batches; returns N x 1536 x h x w on the CPU."""
    return torch.cat([model(images[i:i + batch].to(device)).cpu()
                      for i in range(0, len(images), batch)])


# ------------------------------------------------------------- coreset -------
def greedy_coreset(x, ratio, device, proj_dim=128, seed=0):
    """Pick ratio*N rows of x that cover x well (each new pick = the point
    farthest from everything picked so far). Distances are computed on a random
    projection to proj_dim dims, which is much faster and nearly as good."""
    g = torch.Generator().manual_seed(seed)
    n = len(x)
    k = max(1, int(n * ratio))
    proj = torch.randn(x.shape[1], proj_dim, generator=g) / math.sqrt(proj_dim)
    z = (x @ proj).to(device)                              # N x proj_dim
    picked = [int(torch.randint(n, (1,), generator=g))]
    min_d = torch.cdist(z, z[picked[-1]][None]).squeeze(1)
    for _ in range(k - 1):
        i = int(torch.argmax(min_d))
        picked.append(i)
        min_d = torch.minimum(min_d, torch.cdist(z, z[i][None]).squeeze(1))
    return x[picked]


# --------------------------------------------------------------- score -------
def gaussian_blur(maps, sigma=4.0):
    """Blur N x 1 x H x W maps with a Gaussian (same kernel size rule as anomalib)."""
    r = int(4 * sigma + 0.5)
    t = torch.arange(-r, r + 1, dtype=maps.dtype, device=maps.device)
    k = torch.exp(-t ** 2 / (2 * sigma ** 2))
    k = k / k.sum()
    maps = F.conv2d(F.pad(maps, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1))
    return F.conv2d(F.pad(maps, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1))


def score(feats, bank, size, device, batch=8):
    """feats: N x C x h x w. Returns (image scores N, anomaly maps N x size x size)."""
    bank = bank.to(device)
    scores, maps = [], []
    for i in range(0, len(feats), batch):
        f = feats[i:i + batch].to(device)
        b, c, h, w = f.shape
        patches = f.permute(0, 2, 3, 1).reshape(-1, c)                 # (b*h*w) x C
        d = torch.cdist(patches, bank).min(1).values                   # nearest memory vector
        m = d.view(b, 1, h, w)
        m = F.interpolate(m, size=(size, size), mode="bilinear", align_corners=False)
        m = gaussian_blur(m).squeeze(1)
        maps.append(m.cpu())
        scores.append(m.flatten(1).max(1).values.cpu())
    return torch.cat(scores).numpy(), torch.cat(maps).numpy()


# ---------------------------------------------------------------- main -------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--coreset", type=float, default=0.01)
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--random-weights", action="store_true", help="smoke test only")
    args = ap.parse_args()
    root = args.root
    device = "cuda" if torch.cuda.is_available() else "cpu"    # ROCm GPUs also show up as "cuda"
    print("device:", device, torch.cuda.get_device_name(0) if device == "cuda" else "")

    split = pd.read_csv(root / "splits/pcb1.csv")
    anno = pd.read_csv(root / "data/pcb1/image_anno.csv")
    split = split.merge(anno[["image", "mask"]], left_on="path", right_on="image", how="left")
    print(split["split"].value_counts().to_dict())

    t0 = time.time()
    model = Features(pretrained=not args.random_weights).to(device)
    train = split[split["split"] == "train"]
    assert not train["is_defective"].any(), "defective image in train"

    # 1-2. features of all train patches
    feats = extract(model, load_images(root, train["path"], args.size), device)
    memory = feats.permute(0, 2, 3, 1).reshape(-1, feats.shape[1])
    print(f"train patches: {tuple(memory.shape)}  ({time.time() - t0:.0f} s)")
    del feats

    # 3. coreset
    t1 = time.time()
    bank = greedy_coreset(memory, args.coreset, device)
    del memory
    t_fit = time.time() - t0
    print(f"memory bank: {tuple(bank.shape)}  coreset {time.time() - t1:.0f} s, fit total {t_fit:.0f} s")

    out = root / "out/patchcore"
    out.mkdir(parents=True, exist_ok=True)
    (root / "models").mkdir(exist_ok=True)
    torch.save({"bank": bank.half(), "size": args.size, "coreset": args.coreset,
                "backbone": "wide_resnet50_2/IMAGENET1K_V1", "layers": ["layer2", "layer3"]},
               root / "models/patchcore_pcb1.pt")

    # 4. score val and test
    summary = {"coreset": args.coreset, "size": args.size, "bank": list(bank.shape),
               "fit_s": round(t_fit), "device": device}
    all_y, all_s = [], []
    for name in ["val", "test"]:
        t2 = time.time()
        part = split[split["split"] == name].reset_index(drop=True)
        s, maps = score(extract(model, load_images(root, part["path"], args.size), device),
                        bank, args.size, device)
        y = part["is_defective"].astype(bool).to_numpy()
        gt = load_masks(root, part["mask"], args.size)
        summary[f"{name}_image_auroc"] = round(roc_auc_score(y, s), 4)
        summary[f"{name}_pixel_auroc"] = round(roc_auc_score(gt.ravel(), maps.ravel()), 4)
        summary[f"{name}_score_s"] = round(time.time() - t2)
        part.assign(score=s)[["path", "is_defective", "defect_type", "score"]].to_csv(
            out / f"scores_{name}.csv", index=False)
        np.save(out / f"maps_{name}.npy", maps.astype(np.float16))
        all_y.append(y)
        all_s.append(s)

    # val + test = the official test set -> comparable with the Colab run (0.934)
    summary["official_test_image_auroc"] = round(roc_auc_score(np.concatenate(all_y), np.concatenate(all_s)), 4)
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()