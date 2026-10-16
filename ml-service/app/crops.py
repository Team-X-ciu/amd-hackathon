"""Crop policies for a defect box, shared by the training scripts and /inspect.

Policy "bbox":  square around the box (+ context), resized to 224. The defect fills the
                frame; its real size is lost.
Policy "fixed": 224x224 window at full resolution, centred on the box. Real scale kept.
                If the box doesn't fit, the window grows to fit it and is resized to 224.

#9 step 5 measured both on PatchCore's own (loose) boxes: "fixed" 0.786 macro-F1,
"bbox" 0.496, because "fixed" barely depends on how big the box is. /inspect uses "fixed".
"""

from PIL import Image

SIZE = 224  # network input size (ImageNet convention)
CONTEXT = 0.5  # bbox policy: add 50% of the defect's side on each side
MIN_SIDE = 32  # bbox policy: never crop smaller than this (limits blow-up of tiny defects)


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
        side = max(SIZE, int(max(h, w) * 1.2))  # grow only if the defect doesn't fit
    else:
        raise ValueError(f"unknown policy {policy!r}")
    box = square_box(cy, cx, side, img.width, img.height)
    return img.crop(box).resize((SIZE, SIZE), Image.BILINEAR), box
