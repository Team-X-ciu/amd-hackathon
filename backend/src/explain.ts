// Background explanations (DECISIONS 4, #21). After a defective inspection is saved, the backend
// calls ML /explain without making the client wait; the result lands on the row as
// `explained` or `explain_failed`. A job in progress is lost if the backend restarts:
// recoverInterrupted() marks those rows so the operator can retry.
import type { JSONValue } from "postgres";

import type { components } from "./api/types.js";
import { sql } from "./db.js";
import { mlExplain, type ExplainRequest } from "./ml-client.js";

type VisionResult = components["schemas"]["VisionResult"];

/** Starts one explanation and returns at once. Never throws: failures are stored on the row. */
export function startExplanation(id: string): void {
  void explain(id).catch((e) => console.error(`explanation for ${id} could not be stored:`, e));
}

async function explain(id: string): Promise<void> {
  const [row] = await sql<{ vision: VisionResult | null; part_type: string | null }[]>`
    select vision, part_type from inspections where id = ${id}`;
  if (!row?.vision) return;
  const v = row.vision;
  const request: ExplainRequest = {
    defect_type: v.defect_type ?? "unknown",
    severity: v.severity,
    anomaly_score: v.anomaly_score,
    ...(v.defect_area_ratio != null && { defect_area_ratio: v.defect_area_ratio }),
    ...(row.part_type === "pcb1" && { part_type: row.part_type }),
  };

  // The operator may decide while the agent runs: `decided` stays final, the explanation is still stored.
  try {
    const { answer: _answer, ...explanation } = await mlExplain(request); // `answer` is for chat follow-ups
    await sql`
      update inspections
      set explanation = ${sql.json(explanation as unknown as JSONValue)},
          error = null,
          status = case when status = 'decided' then status else 'explained' end
      where id = ${id}`;
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    await sql`
      update inspections
      set error = case when status = 'decided' then error else ${`Explanation failed: ${message}`} end,
          status = case when status = 'decided' then status else 'explain_failed' end
      where id = ${id}`;
  }
}

/** On startup: explanations that were running when the backend stopped will never finish. */
export async function recoverInterrupted(): Promise<void> {
  const rows = await sql`
    update inspections
    set status = 'explain_failed', error = 'The backend restarted before the explanation finished; retry it.'
    where status = 'explaining'
    returning id`;
  if (rows.length) console.log(`${rows.length} interrupted explanation(s) marked explain_failed`);
}
