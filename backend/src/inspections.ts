// /inspections routes. Contract: contracts/backend.openapi.yaml
import { randomUUID } from "node:crypto";

import { Router, type Request, type Response } from "express";
import multer from "multer";
import type { JSONValue } from "postgres";

import type { components } from "./api/types.js";
import { sql } from "./db.js";
import { startExplanation } from "./explain.js";
import { MlError, mlInspect } from "./ml-client.js";
import { filePath, removeFiles, saveFile, sniffImage } from "./storage.js";

type Inspection = components["schemas"]["Inspection"];
type VisionResult = components["schemas"]["VisionResult"];
type PartType = components["schemas"]["PartType"];
type DecisionInput = components["schemas"]["DecisionInput"];
type ChatMessage = components["schemas"]["ChatMessage"];

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024; // contract: 413 above this
const PART_TYPES: PartType[] = ["pcb1"];

/** One row of the `inspections` table (backend/db/init.sql). */
interface InspectionRow {
  id: string;
  status: Inspection["status"];
  line_id: string | null;
  part_type: PartType | null;
  source: "upload" | "simulator";
  image_path: string;
  mask_path: string | null;
  heatmap_path: string | null;
  vision: Omit<VisionResult, "mask_url" | "heatmap_url"> | null;
  explanation: Inspection["explanation"];
  error: string | null;
  created_at: Date;
}

/** One row of the `decisions` table. */
interface DecisionRow {
  inspection_id: string;
  decision: DecisionInput["decision"];
  followed_recommendation: boolean | null;
  note: string | null;
  operator: string | null;
  decided_at: Date;
  time_to_decision_ms: number;
}

/** One row of the `chat_messages` table (only the columns the contract shows). */
interface ChatRow {
  role: ChatMessage["role"];
  content: string;
  sources: ChatMessage["sources"];
  created_at: Date;
}

/**
 * Row -> contract shape. File URLs are derived from the id, so only paths are stored.
 * `decision` and `chat` come from their own tables; callers that don't read them get null / [].
 */
export function toInspection(row: InspectionRow, decision: DecisionRow | null = null, chat: ChatRow[] = []): Inspection {
  const base = `/api/inspections/${row.id}`;
  return {
    id: row.id,
    status: row.status,
    line_id: row.line_id ?? undefined,
    part_type: row.part_type ?? undefined,
    source: row.source,
    image_url: `${base}/image`,
    created_at: row.created_at.toISOString(),
    vision: row.vision && {
      ...row.vision,
      mask_url: row.mask_path ? `${base}/mask` : null,
      heatmap_url: row.heatmap_path ? `${base}/heatmap` : null,
    },
    explanation: row.explanation,
    decision: decision && {
      decision: decision.decision,
      followed_recommendation: decision.followed_recommendation ?? undefined,
      note: decision.note ?? undefined,
      operator: decision.operator ?? undefined,
      decided_at: decision.decided_at.toISOString(),
      time_to_decision_ms: decision.time_to_decision_ms,
    },
    chat: chat.map((m) => ({ role: m.role, content: m.content, sources: m.sources, created_at: m.created_at.toISOString() })),
    error: row.error,
  };
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const notFound = (res: Response, what = "inspection") => res.status(404).json({ error: `${what} not found` });

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: MAX_IMAGE_BYTES } });

export const inspectionsRouter = Router();

inspectionsRouter.post("/inspections", upload.single("image"), async (req: Request, res: Response) => {
  if (!req.file) return res.status(400).json({ error: "image is required" });
  const image = req.file.buffer;
  const type = sniffImage(image);
  if (!type) return res.status(400).json({ error: "image must be a PNG or JPEG" });
  const partType = req.body.part_type as PartType | undefined;
  if (partType !== undefined && !PART_TYPES.includes(partType)) {
    return res.status(400).json({ error: `unknown part_type: ${partType}` });
  }
  const lineId = typeof req.body.line_id === "string" && req.body.line_id !== "" ? req.body.line_id : null;

  const id = randomUUID();
  const ext = type === "png" ? "png" : "jpg";
  const written: string[] = [];
  let imagePath = "";
  const save = async (name: string, data: Buffer) => {
    const path = await saveFile(name, data);
    written.push(path);
    return path;
  };
  const insert = async (row: Pick<InspectionRow, "status" | "mask_path" | "heatmap_path" | "vision" | "error">) => {
    const [saved] = await sql<InspectionRow[]>`
      insert into inspections (id, status, line_id, part_type, source, image_path, mask_path, heatmap_path, vision, error)
      values (${id}, ${row.status}, ${lineId}, ${partType ?? null}, 'upload', ${imagePath},
              ${row.mask_path}, ${row.heatmap_path}, ${row.vision && sql.json(row.vision as unknown as JSONValue)}, ${row.error})
      returning *`;
    return saved;
  };

  try {
    imagePath = await save(`${id}.${ext}`, image);

    let result;
    try {
      result = await mlInspect(image, `${id}.${ext}`, `image/${type}`, partType);
    } catch (e) {
      if (!(e instanceof MlError)) throw e;
      // Contract: the inspection is still saved, with status `failed`.
      await insert({ status: "failed", mask_path: null, heatmap_path: null, vision: null, error: e.message });
      return res.status(502).json({ error: "ML service failed", detail: e.message });
    }

    const { mask_png_base64, heatmap_png_base64, model_versions: _versions, ...vision } = result;
    const maskPath = mask_png_base64 ? await save(`${id}-mask.png`, Buffer.from(mask_png_base64, "base64")) : null;
    const heatmapPath = heatmap_png_base64 ? await save(`${id}-heatmap.png`, Buffer.from(heatmap_png_base64, "base64")) : null;

    const row = await insert({
      // Defective boards are explained in the background (DECISIONS 4, #21).
      status: vision.is_defective ? "explaining" : "inspected",
      mask_path: maskPath,
      heatmap_path: heatmapPath,
      vision,
      error: null,
    });
    res.status(201).json(toInspection(row));
    if (row.status === "explaining") startExplanation(row.id);
  } catch (e) {
    await removeFiles(written).catch(() => {});
    res.status(500).json({ error: "Could not save the inspection", detail: String(e) });
  }
});

inspectionsRouter.get("/inspections/:id", async (req: Request<{ id: string }>, res: Response) => {
  const { id } = req.params;
  if (!UUID.test(id)) return notFound(res); // a malformed id would make Postgres throw on the uuid cast
  const [row] = await sql<InspectionRow[]>`select * from inspections where id = ${id}`;
  if (!row) return notFound(res);
  const [decision] = await sql<DecisionRow[]>`select * from decisions where inspection_id = ${id}`;
  const chat = await sql<ChatRow[]>`
    select role, content, sources, created_at from chat_messages
    where inspection_id = ${id} order by created_at, id`;
  res.json(toInspection(row, decision ?? null, chat));
});

// Retry (or re-run) the explanation. Answers at once; the result lands on the row like the first run.
inspectionsRouter.post("/inspections/:id/explain", async (req: Request<{ id: string }>, res: Response) => {
  const { id } = req.params;
  if (!UUID.test(id)) return notFound(res);
  // One atomic update, so two clicks can't start two runs.
  const [row] = await sql<InspectionRow[]>`
    update inspections set status = 'explaining', error = null
    where id = ${id} and vision->>'is_defective' = 'true' and status not in ('explaining', 'decided')
    returning *`;
  if (!row) {
    const [current] = await sql<{ status: string; defective: string | null }[]>`
      select status, vision->>'is_defective' as defective from inspections where id = ${id}`;
    if (!current) return notFound(res);
    const reason =
      current.defective !== "true" ? "the board is not defective"
      : current.status === "explaining" ? "an explanation is already running"
      : "the operator has already decided";
    return res.status(409).json({ error: `Nothing to start: ${reason}` });
  }
  startExplanation(id);
  res.status(202).json(toInspection(row));
});

const STATUSES: Inspection["status"][] = ["inspected", "explaining", "explained", "explain_failed", "decided", "failed"];
const DEFECT_TYPES = ["bent", "melt", "scratch", "missing", "unknown"];

/** A query parameter that fails the contract; message = parameter name. */
class BadParam extends Error {}

inspectionsRouter.get("/inspections", async (req: Request, res: Response) => {
  // Express gives string | string[] | undefined; a repeated parameter is a 400 like any bad value.
  const q = (name: string) => {
    const v = req.query[name];
    if (v === undefined) return null;
    if (typeof v !== "string") throw new BadParam(name);
    return v;
  };
  let status, defective, defectType, lineId, limit, cursor;
  try {
    status = q("status");
    if (status !== null && !STATUSES.includes(status as Inspection["status"])) throw new BadParam("status");
    defective = q("defective");
    if (defective !== null && defective !== "true" && defective !== "false") throw new BadParam("defective");
    defectType = q("defect_type");
    if (defectType !== null && !DEFECT_TYPES.includes(defectType)) throw new BadParam("defect_type");
    lineId = q("line_id");
    const rawLimit = q("limit") ?? "50";
    limit = Number(rawLimit);
    if (!/^\d+$/.test(rawLimit) || limit < 1 || limit > 200) throw new BadParam("limit");
    cursor = q("cursor");
    if (cursor !== null && !UUID.test(cursor)) throw new BadParam("cursor");
  } catch (e) {
    if (e instanceof BadParam) return res.status(400).json({ error: `invalid ${e.message}` });
    throw e;
  }
  if (cursor !== null) {
    const [exists] = await sql`select 1 from inspections where id = ${cursor}`;
    if (!exists) return res.status(400).json({ error: "invalid cursor" });
  }

  // Keyset paging on (created_at, id): the cursor row's values stay inside Postgres, so the
  // microsecond timestamps are compared exactly (a JS Date would round them to ms).
  const rows = await sql<InspectionRow[]>`
    select * from inspections
    where (${status}::text is null or status = ${status})
      and (${defective}::text is null or vision->>'is_defective' = ${defective})
      and (${defectType}::text is null or vision->>'defect_type' = ${defectType})
      and (${lineId}::text is null or line_id = ${lineId})
      and (${cursor}::uuid is null or (created_at, id) < (select created_at, id from inspections where id = ${cursor}))
    order by created_at desc, id desc
    limit ${limit + 1}`;
  const page = rows.slice(0, limit);

  const decisions = page.length
    ? await sql<DecisionRow[]>`select * from decisions where inspection_id in ${sql(page.map((r) => r.id))}`
    : [];
  const byId = new Map(decisions.map((d) => [d.inspection_id, d]));

  res.json({
    // `chat` is optional in the contract and not read here, so leave it out rather than claim [].
    items: page.map((r) => {
      const { chat: _chat, ...item } = toInspection(r, byId.get(r.id) ?? null);
      return item;
    }),
    next_cursor: rows.length > limit ? page[page.length - 1].id : null,
  });
});


// Files are written once and never change, so the browser may cache them for good.
const FILE_ROUTES = { image: "image_path", mask: "mask_path", heatmap: "heatmap_path" } as const;

for (const [kind, column] of Object.entries(FILE_ROUTES)) {
  inspectionsRouter.get(`/inspections/:id/${kind}`, async (req: Request<{ id: string }>, res: Response) => {
    const { id } = req.params;
    if (!UUID.test(id)) return notFound(res);
    const [row] = await sql<{ path: string | null }[]>`select ${sql(column)} as path from inspections where id = ${id}`;
    if (!row) return notFound(res);
    // No mask/heatmap for a good board; neither for a failed one.
    if (!row.path) return notFound(res, kind);
    // Content-Type comes from the extension we chose (.jpg / .png).
    res.sendFile(filePath(row.path), { maxAge: "1y", immutable: true }, (err) => {
      if (err && !res.headersSent) notFound(res, `${kind} file`);
    });
  });
}
