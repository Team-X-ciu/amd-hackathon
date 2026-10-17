// Golden-path contract smoke test.
// Calls every backend endpoint in contracts/backend.openapi.yaml in golden-path order and
// validates each real response against the contract. Keeps going after a failure, prints a
// table, exits 1 if anything failed. This is the definition of done for the golden path.
//
//   cd scripts/smoke && npm install && node smoke.mjs
//   BASE_URL=http://localhost:3000/api TEST_IMAGE=/path/to/045.JPG node smoke.mjs
import { readFile } from "node:fs/promises";
import { basename, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";
import { parse } from "yaml";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "../..");
const BASE_URL = (process.env.BASE_URL ?? "http://localhost:3000/api").replace(/\/$/, "");
const TEST_IMAGE = process.env.TEST_IMAGE ?? resolve(root, "ml-service/data/pcb1/Data/Images/Anomaly/045.JPG");
const EXPLAIN_TIMEOUT_MS = Number(process.env.EXPLAIN_TIMEOUT_MS ?? 60_000);
const NIL_ID = "00000000-0000-0000-0000-000000000000";

// --- contract ---------------------------------------------------------------------------
const doc = parse(await readFile(resolve(root, "contracts/backend.openapi.yaml"), "utf8"));
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addFormat("binary", true);
ajv.addSchema(doc, "backend");

const ptr = (...segs) => segs.map((s) => encodeURIComponent(String(s).replace(/~/g, "~0").replace(/\//g, "~1"))).join("/");
const deref = (obj) => {
  if (!obj?.$ref) return obj;
  return obj.$ref.slice(2).split("/").reduce((o, k) => o[k.replace(/~1/g, "/").replace(/~0/g, "~")], doc);
};

/** Validate status, content-type and body against paths[path][method].responses. Returns error strings. */
function checkContract(method, path, res, body) {
  const op = doc.paths[path]?.[method.toLowerCase()];
  if (!op) return [`${method} ${path} is not in the contract`];
  const status = String(res.status);
  const response = deref(op.responses[status]);
  if (!response) return [`status ${res.status} not documented (expected ${Object.keys(op.responses).join("/")})`];
  if (!response.content) return [];
  const ct = (res.headers.get("content-type") ?? "").split(";")[0].trim();
  const media = response.content[ct];
  if (!media) return [`content-type "${ct}" not documented (expected ${Object.keys(response.content).join(", ")})`];
  if (!media.schema || ct !== "application/json") return [];
  // Response objects may be inline or a $ref to components/responses: point at whichever holds the schema.
  const responsePtr = op.responses[status].$ref
    ? op.responses[status].$ref.slice(1)
    : `/${ptr("paths", path, method.toLowerCase(), "responses", status)}`;
  const ref = `backend#${responsePtr}/${ptr("content", ct, "schema")}`;
  const validate = ajv.getSchema(ref) ?? (ajv.addSchema({ $ref: ref }, ref), ajv.getSchema(ref));
  if (validate(body)) return [];
  return validate.errors.slice(0, 5).map((e) => `schema: ${e.instancePath || "(root)"} ${e.message}${e.params?.allowedValues ? ` ${JSON.stringify(e.params.allowedValues)}` : ""}`);
}

// --- runner -----------------------------------------------------------------------------
const results = [];
const short = (v) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s === undefined ? "" : s.length > 140 ? `${s.slice(0, 140)}…` : s;
};

/** One request: call, validate against the contract, run extra checks. Never throws. */
async function step(name, method, path, { params = {}, query, body, form, extra, raw = false } = {}) {
  let url = BASE_URL + path.replace(/\{(\w+)\}/g, (_, k) => params[k]);
  if (query) url += `?${new URLSearchParams(query)}`;
  const init = { method, signal: AbortSignal.timeout(30_000) };
  if (form) init.body = form;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "content-type": "application/json" };
  }
  const errors = [];
  let res, data;
  try {
    res = await fetch(url, init);
    const ct = res.headers.get("content-type") ?? "";
    if (raw) data = undefined;
    else if (ct.includes("json")) data = await res.json().catch(() => (errors.push("body is not valid JSON"), undefined));
    else data = (await res.text()).slice(0, 200);
    errors.push(...checkContract(method, path, res, data));
    if (extra) errors.push(...(await extra(res, data)).filter(Boolean));
  } catch (e) {
    errors.push(`request failed: ${e.cause?.code ?? e.name}: ${e.message}`);
  }
  const ok = errors.length === 0;
  results.push({ name, call: `${method} ${path}`, status: res?.status ?? "—", ok, errors, body: data });
  console.log(`${ok ? "PASS" : "FAIL"}  ${name}  [${method} ${path} -> ${res?.status ?? "no response"}]`);
  for (const e of errors) console.log(`        - ${e}`);
  if (!ok && data !== undefined) console.log(`        body: ${short(data)}`);
  return { res, data, ok };
}

const expect = (cond, msg) => (cond ? null : msg);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- golden path ------------------------------------------------------------------------
console.log(`Backend: ${BASE_URL}\nImage:   ${TEST_IMAGE}\n`);

await step("1 health", "GET", "/health", {
  extra: async (_r, d) => [expect(d?.status === "ok", `status is ${d?.status}`), expect(d?.ml_service === "ok", `ml_service is ${d?.ml_service}`)],
});

const image = await readFile(TEST_IMAGE);
const form = new FormData();
form.append("image", new Blob([image], { type: "image/jpeg" }), basename(TEST_IMAGE));
form.append("part_type", "pcb1");
form.append("line_id", "line-1");
const created = await step("2 upload board 045", "POST", "/inspections", {
  form,
  extra: async (r, d) => {
    const v = d?.vision;
    return [
      expect(r.status === 201, `expected 201, got ${r.status}`),
      expect(typeof d?.id === "string", "no inspection id"),
      expect(d?.status === "explaining", `status is ${d?.status}, expected explaining (defective board)`),
      expect(v?.is_defective === true, `vision.is_defective is ${v?.is_defective}`),
      expect(v?.defect_type === "missing", `vision.defect_type is ${v?.defect_type}, expected missing`),
      expect(v?.severity === "high", `vision.severity is ${v?.severity}, expected high`),
      expect(Array.isArray(v?.bounding_boxes) && v.bounding_boxes.length > 0, "no bounding_boxes"),
      expect(typeof v?.mask_url === "string", "no vision.mask_url"),
      expect(typeof v?.heatmap_url === "string", "no vision.heatmap_url"),
      expect(typeof d?.image_url === "string", "no image_url"),
    ];
  },
});
const id = typeof created.data?.id === "string" ? created.data.id : NIL_ID;
if (id === NIL_ID) console.log(`        (no id returned; the next calls use ${NIL_ID} so their real responses are still recorded)`);

// Explanation runs in the background (DECISIONS 4): poll until it settles.
let detail = await step("3 get inspection", "GET", "/inspections/{id}", { params: { id } });
const deadline = Date.now() + EXPLAIN_TIMEOUT_MS;
while (detail.res?.ok && detail.data?.status === "explaining" && Date.now() < deadline) {
  await sleep(2000);
  detail = { res: await fetch(`${BASE_URL}/inspections/${id}`), data: undefined };
  if (detail.res.ok) detail.data = await detail.res.json();
}
await step("4 explanation arrived", "GET", "/inspections/{id}", {
  params: { id },
  extra: async (_r, d) => [
    expect(d?.status === "explained", `status is ${d?.status}, expected explained${d?.error ? ` (error: ${d.error})` : ""}`),
    expect(typeof d?.explanation?.summary === "string" && d.explanation.summary.length > 0, "no explanation.summary"),
    expect(Array.isArray(d?.explanation?.sources) && d.explanation.sources.length > 0, "explanation has no sources"),
  ],
});

await step("5 original image", "GET", "/inspections/{id}/image", {
  params: { id }, raw: true,
  extra: async (r) => [expect(r.ok, `got ${r.status}`)],
});
await step("6 defect mask", "GET", "/inspections/{id}/mask", {
  params: { id }, raw: true,
  extra: async (r) => [expect(r.headers.get("content-type")?.startsWith("image/png"), "mask is not image/png")],
});
await step("7 explain retry (202, or 409 when already explained)", "POST", "/inspections/{id}/explain", {
  params: { id },
  extra: async (r) => [expect(r.status === 202 || r.status === 409, `expected 202/409, got ${r.status}`)],
});
await step("8 operator chat", "POST", "/inspections/{id}/chat", {
  params: { id }, body: { message: "Can this board be reworked instead of scrapped?" },
  extra: async (r, d) => [expect(r.status === 200, `got ${r.status}`), expect(d?.role === "assistant", `role is ${d?.role}`)],
});
await step("9 operator decision", "POST", "/inspections/{id}/decision", {
  params: { id }, body: { decision: "reject", followed_recommendation: true, operator: "smoke-test" },
  extra: async (r, d) => [
    expect(r.status === 200, `got ${r.status}`),
    expect(d?.status === "decided", `status is ${d?.status}`),
    expect(d?.decision?.decision === "reject", `decision is ${short(d?.decision)}`),
  ],
});
await step("10 history list shows the decision", "GET", "/inspections", {
  query: { limit: "50" },
  extra: async (r, d) => {
    const row = d?.items?.find?.((i) => i.id === id);
    return [expect(r.status === 200, `got ${r.status}`), expect(row, `inspection ${id} not in list`), expect(!row || row.status === "decided", `listed status is ${row?.status}`)];
  },
});
await step("11 history filter defective=true", "GET", "/inspections", {
  query: { defective: "true", defect_type: "missing" },
  extra: async (r, d) => [expect(r.status === 200, `got ${r.status}`), expect(d?.items?.some?.((i) => i.id === id), "filtered list misses the inspection")],
});
await step("12 stats", "GET", "/stats", { extra: async (r, d) => [expect(r.status === 200, `got ${r.status}`), expect((d?.total ?? 0) >= 1, `total is ${d?.total}`)] });

await step("13 simulator status", "GET", "/simulator", { extra: async (r) => [expect(r.status === 200, `got ${r.status}`)] });
await step("14 simulator start", "POST", "/simulator/start", {
  body: { interval_ms: 60_000, defect_rate: 0.2, line_id: "smoke" },
  extra: async (r, d) => [expect(r.status === 200, `got ${r.status}`), expect(d?.running === true, `running is ${d?.running}`)],
});
await step("15 simulator stop", "POST", "/simulator/stop", {
  extra: async (r, d) => [expect(r.status === 200, `got ${r.status}`), expect(d?.running === false, `running is ${d?.running}`)],
});

// SSE: open the stream, check the content-type, then close it.
{
  const errors = [];
  let status = "—";
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const res = await fetch(`${BASE_URL}/events`, { signal: ctrl.signal });
    status = res.status;
    clearTimeout(timer);
    const ct = res.headers.get("content-type") ?? "";
    if (res.status !== 200) errors.push(`expected 200, got ${res.status}: ${short(await res.text())}`);
    else if (!ct.startsWith("text/event-stream")) errors.push(`content-type is "${ct}", expected text/event-stream`);
    ctrl.abort();
  } catch (e) {
    if (e.name !== "AbortError") errors.push(`request failed: ${e.message}`);
  }
  results.push({ name: "16 live events stream", call: "GET /events", status, ok: errors.length === 0, errors });
  console.log(`${errors.length ? "FAIL" : "PASS"}  16 live events stream  [GET /events -> ${status}]`);
  for (const e of errors) console.log(`        - ${e}`);
}

// --- error cases ------------------------------------------------------------------------
await step("17 unknown id -> 404", "GET", "/inspections/{id}", {
  params: { id: "11111111-1111-4111-8111-111111111111" },
  extra: async (r) => [expect(r.status === 404, `expected 404, got ${r.status}`)],
});
await step("18 upload without image -> 400", "POST", "/inspections", {
  form: new FormData(),
  extra: async (r) => [expect(r.status === 400, `expected 400, got ${r.status}`)],
});

// --- summary ----------------------------------------------------------------------------
const failed = results.filter((r) => !r.ok);
console.log(`\n${results.length - failed.length}/${results.length} passed`);
if (failed.length) {
  console.log("\n| step | call | HTTP | first error |\n| --- | --- | --- | --- |");
  for (const r of failed) console.log(`| ${r.name} | ${r.call} | ${r.status} | ${r.errors[0].replace(/\|/g, "\\|")} |`);
}
process.exit(failed.length ? 1 : 0);
