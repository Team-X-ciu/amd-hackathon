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
- other types by defect area: under 1% `low`, 1–5% `medium`, over 5% `high` (replaced by entry 7: 1% / 3% on the predicted area)
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

## 5. Agent LLM: Gemma via AMD Token Factory (15 Oct 2026, issue #17)

**Chosen:** `Gemma-4-31B-IT` served by **AMD Token Factory** (notebooks.amd.com/tokenfactory),
called through its OpenAI-compatible API (`LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`).

**Considered:**
- **Self-hosted vLLM on AMD Developer Cloud** (the original plan): full control and a strong
  "we run it on ROCm" story, but it needs credits (2–3 days to arrive) or a card, plus a day of
  setup (ROCm image, GPU memory settings, private port).
- **Qwen2.5-7B-Instruct**: the original default model; smaller and not eligible for the Google prize.

**Why:**
- The organizers confirmed that ACT III runs on Token Factory and that the API key is all you need
  to participate (lablab Discord, 14 Oct 2026).
- The model runs on AMD GPUs with no infrastructure for us to manage, which leaves time for the agent itself.
- Gemma is Google DeepMind's model: building with it makes us eligible for the Google prize.
- First test completion worked (15 Oct).

**Consequences:**
- The API key lives only in `.env`, never in the repo; `.env.example` lists the variable names.
- Usage is metered: check Model Usage in Token Factory before the demo.
- The vision model (PatchCore) runs separately; where it runs is recorded with issue #6.

## 6. Data findings for pcb1 (15 Oct 2026, issue #7)

Correction to entry 1, from the actual masks (`ml-service/scripts/make_split.py`):
- **Per-type counts are unbalanced, not ~25 each:** melt 50, missing 20, bent 15, scratch 15
  (9 boards have several types; the type with the most mask pixels wins).
- **Split:** train = VisA's official 904 good boards; the official test set (100 good + 100 defective)
  is split 50/50 into val/test, stratified by type, seed 42 → bent and scratch have only 7–8 boards
  per half, so per-type results are noisy. The classifier is judged by **macro-F1** (baseline: always
  "melt").
- **Defects are tiny:** median 0.2% of the image, 90th percentile 2.1%. With the 1% / 5% rule from
  entry 3 almost every board would be "low". New severity thresholds will be set on the **val** split
  using PatchCore's predicted masks (with the real `/inspect`).

## 7. Severity cut-offs from predicted masks (16 Oct 2026, issue #10)

`defect_area_ratio` comes from PatchCore's mask, which is blurrier and larger than the real defect
(Anomaly/000: 1.6% predicted). So the cut-offs are set on what `/inspect` actually measures:
`ml-service/scripts/severity_cutoffs.py` splits the predicted area of the 48 defective val boards
PatchCore catches into thirds (0.97% / 3.21%), rounded to **under 1% `low`, 1–3% `medium`, over 3% `high`**.

- Predicted area by true type (val median): scratch 0.7%, melt 1.3%, bent 4.4%, missing 10.8%,
  so size alone already ranks the types sensibly; `missing` stays always `high` once #9 names it.
- False alarms are small: none of the 9 on val (or 4 on test) lands in `high`.
- Test, counted once (unrounded cut-offs): 9 low / 20 medium / 16 high on caught defective boards.

## 8. The agent: rules decide, Gemma explains, code checks (17 Oct 2026, issues #11, #20)

- **The action is never the LLM's.** `qc_rules.py` turns the QC manual into a decision table:
  `decide(defect_type, severity)` → `accept` / `rework` / `reject` / `review`, whether a human must
  review, the extra checks the camera cannot see, and the manual section the rule comes from.
- **No vector RAG.** The manual is 1,155 words. `manual.py` splits it by section ID and the defect
  type selects the section to cite; the full manual also goes into the prompt. A wrong retrieval
  would mean a wrong citation, and a lookup cannot retrieve the wrong section.
- **Gemma only rewords.** `llm.py` sends the facts (action, checks, causes, cited sections) to
  Gemma-4-31B-IT on AMD Token Factory and asks for a summary, an action text that starts with the
  decided action, and an answer if the operator asked a question.
- **Code checks every reply** (`checks.py`): the action prefix matches the table, every number
  appears in the facts, and there is no order to stop the line. Any failure, timeout or provider
  error returns the templated explanation (`build_explanation`), which has the same action.
- **Judgement calls in the table:** melt · medium → reject (the surface can't be verified from the
  image); scratch · low → accept, with the high-severity checks always listed.
- **Known gaps:** severity is area-based while the manual's "high" is functional; the stop-line check
  is a text match ("stop the line … QC-6.1" would pass).
- **Evidence:** 50 offline tests; live golden set 7/7 actions correct, including a prompt injection.
- `LLM_TIMEOUT_S=40` with one retry stays under the backend's `ML_EXPLAIN_TIMEOUT_MS=90000`.
