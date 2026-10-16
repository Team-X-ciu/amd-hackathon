"""Defect-type classifier for one PatchCore box (#9).

Trained offline by scripts/train_classifier.py and saved as plain numbers in
models/classifier_pcb1.npz, so this runs with numpy alone:
  crop the box ("fixed" policy) -> WRN-50 layer2+3 features, averaged over the crop
  (the same network PatchCore already holds) -> standardise -> linear layer -> softmax.
Below the confidence chosen on val (0.9) the answer is "unknown".
Held-out test: macro-F1 0.777; answers 69% of boards, right on 94% of those.
"""

from pathlib import Path

import numpy as np
import torch
from PIL import Image

from .crops import crop_region


class DefectClassifier:
    def __init__(self, models_dir, features: torch.nn.Module, device: str):
        p = np.load(Path(models_dir) / "classifier_pcb1.npz")
        self.mean, self.scale = p["mean"], p["scale"]
        self.coef, self.intercept = p["coef"], p["intercept"]
        self.classes = [str(c) for c in p["classes"]]
        self.unknown_below = float(p["unknown_below"])
        self.policy = str(p["policy"])
        self.features, self.device = features, device  # shared with PatchCore: one backbone in memory
        self.version = f"logreg-wrn50-{self.policy}crop"

    def probabilities(self, image: Image.Image, box: tuple[int, int, int, int]) -> np.ndarray:
        """Class probabilities for one box (x, y, w, h) in original-image pixels."""
        x, y, w, h = box
        crop, _ = crop_region(image.convert("RGB"), y, x, y + h, x + w, self.policy)
        t = torch.from_numpy(np.array(crop)).permute(2, 0, 1)[None].float().div(255).to(self.device)
        f = self.features(t).mean(dim=(2, 3))[0].cpu().numpy()
        logits = ((f - self.mean) / self.scale) @ self.coef.T + self.intercept
        e = np.exp(logits - logits.max())
        return e / e.sum()

    def classify(self, image: Image.Image, box: tuple[int, int, int, int]) -> tuple[str, float]:
        """(defect type or "unknown", top probability)."""
        probs = self.probabilities(image, box)
        i = int(probs.argmax())
        conf = float(probs[i])
        return (self.classes[i] if conf >= self.unknown_below else "unknown"), conf
