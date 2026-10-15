# Decisions

Short log of team decisions: what we chose, what else we considered, and why.
Newest at the bottom. Change a decision by adding a new entry, not by editing an old one.

---

## 1. Dataset: VisA, category `pcb1` (13 Oct 2026, issue #3)

**Chosen:** [VisA](https://github.com/amazon-science/spot-diff) (Amazon), category `pcb1`:
printed circuit boards, about 900 good and 100 defective images, with pixel masks.
Defect types: `bent`, `melt`, `scratch`, `missing`, plus `unknown`.

**Considered:**
- **MVTec AD** (`metal_nut`): the standard benchmark, easier, defect labels ready-made. Rejected
  because its licence is CC BY-NC-SA (non-commercial), which is unclear for a hackathon with
  prize money and a business pitch.
- **Severstal** steel defects: lots of labelled masks, but Kaggle competition terms we couldn't verify.
- MPDD, Real-IAD: licence not stated; Real-IAD is also far too large for the week.

**Why:** VisA is **CC BY 4.0**, so commercial use is allowed with attribution. PCB inspection in
electronics manufacturing is a strong, real use case. anomalib supports VisA directly.

**Consequences:**
- Defect type per image is read from the original multi-class masks (class with the most pixels).
  An image can contain several types; we keep the dominant one.
- Only ~25 defective images per type: split defects into validation and test with every type in
  both; the test part is never used for training or tuning. Report results with that caveat.
- Images are high-resolution and defects can be small: check the input size given to PatchCore.
- Attribution to VisA in the README; the data is never committed.

## 2. Vision models: pretrained PatchCore + classifier (13 Oct 2026, issue #3)

**Chosen:**
- **PatchCore** (anomalib) for detection and localisation: pretrained WideResNet-50 features
  compared with a memory bank built from good boards. Gives an anomaly score and a heatmap;
  the thresholded heatmap is the defect mask.
- **Defect classifier**: a small model (e.g. logistic regression) on pretrained features,
  trained on the validation defects. Below a confidence threshold → `unknown` + human review.

**Considered (original plan):** autoencoder trained from scratch for detection, U-Net
segmentation for the mask, a fine-tuned classifier for the type.

**Why:**
- The data can't support it: ~100 defect images and none in the training split is not enough
  to train a U-Net or fine-tune a classifier without overfitting.
- With little data, frozen pretrained features beat training from scratch; PatchCore is among
  the strongest methods on these benchmarks, and autoencoders tend to miss small defects.
- One pass to build the memory bank instead of three training runs leaves time for the agent.

**Kept:** the autoencoder as an optional **baseline** (issue: "Autoencoder baseline vs PatchCore"),
to show the comparison in the results.

**Contract changes:** `defect_type` and `part_type` are enums; `ModelVersions` / `ModelsLoaded`
use `anomaly_detector` + `classifier` instead of `autoencoder` + `segmentation`.

## 3. Severity rule (13 Oct 2026, issue #3)

- not defective → `none`
- `missing` → always `high` (a missing component means a dead board)
- other types by defect area: under 1% `low`, 1–5% `medium`, over 5% `high`
- defective but no area measured → `medium`

Implemented once in `ml-service/app/severity.py`, used by the stub and the real pipeline.

## 4. Explanations run in the background (14 Oct 2026, issue #4)

**Chosen:** `POST /inspections` answers as soon as the vision result is saved. For a defective
board the backend then calls the ML service's `/explain` in the background:
- status `explaining` → `explained`, event `inspection.explained`;
- on error or timeout → status `explain_failed` (+ `error`), event `inspection.explain_failed`;
- `POST /inspections/{id}/explain` is only a retry and answers `202 Accepted` at once.

The operator can decide at any time; a late explanation is still stored.
The ML service's `/explain` stays a normal synchronous request.

**Considered:** the frontend calling `POST /inspections/{id}/explain` and waiting several seconds
for the LLM.

**Why:** the operator sees the mask and defect type immediately instead of waiting for the LLM;
a slow or failed agent never blocks the inspection; the `explaining` status and events already
existed in the contract. No job queue: a background promise in the backend is enough for the demo
(an explanation in progress is lost if the backend restarts — acceptable this week).