// Typed client for the ML service. Types are generated from
// contracts/ml-service.openapi.yaml with `npm run gen:types`.
import type { components } from "./api/ml-types.js";

export type InspectResult = components["schemas"]["InspectResult"];
export type ExplainRequest = components["schemas"]["ExplainRequest"];
export type Explanation = components["schemas"]["Explanation"];
export type MlHealth = components["schemas"]["Health"];

const BASE = process.env.ML_SERVICE_URL ?? "http://localhost:8000";
const TIMEOUT_MS = Number(process.env.ML_TIMEOUT_MS ?? 30000);

export class MlError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function call<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { ...init, signal: AbortSignal.timeout(TIMEOUT_MS) });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new MlError(res.status, body.error ?? `ML service returned ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function mlHealth() {
  return call<MlHealth>("/health", { method: "GET" });
}

export function mlInspect(image: Buffer, filename: string, mimetype: string, partType?: string) {
  const form = new FormData();
  form.append("image", new Blob([new Uint8Array(image)], { type: mimetype }), filename);
  if (partType) form.append("part_type", partType);
  return call<InspectResult>("/inspect", { method: "POST", body: form });
}

export function mlExplain(req: ExplainRequest) {
  return call<Explanation>("/explain", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(req),
  });
}
