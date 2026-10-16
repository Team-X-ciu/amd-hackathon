"""PatchCore for one image at a time, as /inspect needs it.

Same maths as scripts/patchcore_pcb1.py (which fits the memory bank offline):
  image -> resize -> WRN-50 layer2+3 features -> distance to the nearest memory
  vector per patch -> anomaly map -> score = max of the map.
Then, if the score passes the threshold: mask, boxes, area ratio.

Files (built offline by scripts/patchcore_pcb1.py and scripts/threshold.py):
  models/patchcore_pcb1.pt               memory bank + settings
  models/patchcore_pcb1_threshold.json   decision threshold (chosen on val)
"""

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from scipy import ndimage
from torchvision.models import Wide_ResNet50_2_Weights, wide_resnet50_2

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)
MIN_BOX_AREA = 16  # map pixels; smaller blobs dropped (except the peak one)


@dataclass
class Detection:
    raw_score: float  # PatchCore distance, same scale as scores_*.csv
    score: float  # normalised to 0-1: threshold -> 0.5
    is_defective: bool
    mask: np.ndarray | None = None  # bool, original image size (H x W); None if good
    heatmap: np.ndarray = field(repr=False, default=None)  # uint8, original size
    boxes: list[tuple[int, int, int, int]] = field(default_factory=list)  # (x, y, w, h), original px
    main_box: tuple[int, int, int, int] | None = None  # box holding the map's peak: what gets classified
    area_ratio: float | None = None  # share of image pixels in the mask


class _Features(torch.nn.Module):
    """WideResNet-50 up to layer3 -> 1536-d patch features (identical to the fit script)."""

    def __init__(self, pretrained=True):
        super().__init__()
        net = wide_resnet50_2(weights=Wide_ResNet50_2_Weights.IMAGENET1K_V1 if pretrained else None)
        self.stem = torch.nn.Sequential(net.conv1, net.bn1, net.relu, net.maxpool, net.layer1)
        self.layer2, self.layer3 = net.layer2, net.layer3
        self.eval()

    @torch.no_grad()
    def forward(self, x):
        x = (x - MEAN.to(x.device)) / STD.to(x.device)
        f2 = self.layer2(self.stem(x))
        f3 = self.layer3(f2)
        f2 = F.avg_pool2d(f2, 3, 1, 1)
        f3 = F.avg_pool2d(f3, 3, 1, 1)
        f3 = F.interpolate(f3, size=f2.shape[-2:], mode="bilinear", align_corners=False)
        return torch.cat([f2, f3], 1)


def _gaussian_blur(maps, sigma=4.0):
    r = int(4 * sigma + 0.5)
    t = torch.arange(-r, r + 1, dtype=maps.dtype, device=maps.device)
    k = torch.exp(-(t**2) / (2 * sigma**2))
    k = k / k.sum()
    maps = F.conv2d(F.pad(maps, (r, r, 0, 0), mode="reflect"), k.view(1, 1, 1, -1))
    return F.conv2d(F.pad(maps, (0, 0, r, r), mode="reflect"), k.view(1, 1, -1, 1))


class PatchCore:
    """Load once at startup, then call .detect(image) per request."""

    def __init__(self, models_dir="models", device=None, pretrained=True):
        models_dir = Path(models_dir)
        ckpt = torch.load(models_dir / "patchcore_pcb1.pt", map_location="cpu")
        self.threshold = json.loads((models_dir / "patchcore_pcb1_threshold.json").read_text())["threshold"]
        self.size = ckpt["size"]
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.bank = ckpt["bank"].float().to(self.device)
        self.features = _Features(pretrained).to(self.device)
        self.version = f"patchcore-wrn50-c{ckpt['coreset']}-{self.size}px"

    def normalise(self, raw):
        """Contract wants 0-1. Map raw / (2 * threshold), clipped: the threshold lands at 0.5,
        good boards below it, defective above. Monotonic, so the decision is unchanged."""
        return float(min(max(raw / (2 * self.threshold), 0.0), 1.0))

    def anomaly_map(self, image: Image.Image) -> np.ndarray:
        """size x size float map for one RGB image (same preprocessing as the fit script)."""
        x = np.array(image.convert("RGB").resize((self.size, self.size), Image.BILINEAR))
        x = torch.from_numpy(x).permute(2, 0, 1)[None].float().div(255).to(self.device)
        f = self.features(x)  # 1 x C x h x w
        _, c, h, w = f.shape
        d = torch.cdist(f.permute(0, 2, 3, 1).reshape(-1, c), self.bank).min(1).values
        m = F.interpolate(
            d.view(1, 1, h, w), size=(self.size, self.size), mode="bilinear", align_corners=False
        )
        return _gaussian_blur(m)[0, 0].cpu().numpy()

    def detect(self, image: Image.Image) -> Detection:
        W, H = image.size
        m = self.anomaly_map(image)
        raw = float(m.max())

        # heatmap for the UI: map scaled so the threshold is mid-grey, at original size
        hm = np.clip(m / (2 * self.threshold), 0, 1)
        heat = np.asarray(Image.fromarray((hm * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR))

        det = Detection(
            raw_score=raw, score=self.normalise(raw), is_defective=raw >= self.threshold, heatmap=heat
        )
        if not det.is_defective:
            return det

        # mask + boxes, same rule as scripts/boxes.py
        small = m >= self.threshold
        comp, _ = ndimage.label(small, structure=np.ones((3, 3)))
        top = comp[np.unravel_index(np.argmax(m), m.shape)]
        sx, sy = W / self.size, H / self.size
        keep = np.zeros_like(small)
        for k, sl in enumerate(ndimage.find_objects(comp), start=1):
            region = comp[sl] == k
            if region.sum() < MIN_BOX_AREA and k != top:
                continue
            keep[sl] |= region
            x0, y0 = math.floor(sl[1].start * sx), math.floor(sl[0].start * sy)
            x1, y1 = math.ceil(sl[1].stop * sx), math.ceil(sl[0].stop * sy)
            det.boxes.append((x0, y0, x1 - x0, y1 - y0))
            if k == top:
                det.main_box = det.boxes[-1]

        det.mask = np.asarray(Image.fromarray(keep).resize((W, H), Image.NEAREST))
        det.area_ratio = float(keep.mean())  # same share at any scale
        return det
