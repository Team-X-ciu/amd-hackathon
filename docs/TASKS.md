# Plan and tasks

Online build: **12–18 October 2026**. Turn each line into a GitHub issue on the project board.
Rule: always keep a working end-to-end demo; if time runs out, drop a layer, not the product.

Owners: **ML** = ML + agent (tech lead) · **BE** = backend · **FE** = frontend

## Day 1 — Tue 13 Oct: agree and connect

- [ ] ALL — Agree the contracts; fill in "Open decisions" in `contracts/README.md`
- [ ] ML — Choose dataset (MVTec AD / Severstal / NEU), check its licence, fix the `defect_type` list
- [ ] ML — Get an AMD Developer Cloud GPU instance; confirm `torch.cuda.is_available()` on ROCm
- [ ] ML — Start the vLLM server with an open model; one test call works
- [ ] BE — `docker compose up` works; Postgres tables created from `db/init.sql`
- [ ] FE — shadcn/ui set up; layout for the three screens with mock data (Prism)

## Day 2 — Wed 14 Oct: first real model

- [ ] ML — Train the classifier (pretrained backbone, fine-tuned on AMD GPU); held-out test set + baseline
- [ ] ML — Write or collect the QC manual (one section per defect type)
- [ ] BE — `POST /inspections` saves image, mask and result; `GET /inspections`, `GET /inspections/{id}`
- [ ] FE — Inspection detail screen: image, mask overlay, defect, severity

## Day 3 — Thu 15 Oct: agent + full loop

- [ ] ML + BE — Agent session: RAG index over `manuals/`, LangGraph agent, `/explain`
- [ ] BE — `/explain`, `/chat`, `/decision` endpoints; timeout + fallback for a slow LLM
- [ ] FE — Agent panel: explanation, cited sources, accept / reject / rework, follow-up chat
- [ ] ALL — **End-to-end check: upload → mask → explanation → decision**

## Day 4 — Fri 16 Oct: segmentation + live line

- [ ] ML — Segmentation model (U-Net); Dice / IoU on test set
- [ ] BE — Line simulator + `GET /events` (SSE); `GET /stats`
- [ ] FE — Live line screen; history & stats page (Recharts)

## Day 5 — Sat 17 Oct: anomaly gate + deploy

- [ ] ML — Autoencoder gate trained on good parts; AUROC; pick threshold
- [ ] BE — Deploy: public URL, ML service on AMD, README run instructions
- [ ] FE — Polish: tablet layout, loading and error states

## Day 6 — Sun 18 Oct: submit

- [ ] ML — Results table in README (metrics vs baseline, latency, time to decision)
- [ ] FE — Cover image, slides, demo video (who uses it, what it improves, AMD part)
- [ ] ALL — Submit on lablab.ai: repo, app URL, video, slides, descriptions

## Cut list (if behind schedule)

1. Autoencoder gate → classifier + segmentation only
2. Segmentation → classifier + Grad-CAM heatmap, or no mask
3. Live simulator → upload only
4. Follow-up chat → single explanation
